# frozen_string_literal: true

require_relative "docker"
require_relative "discovery"
require_relative "tcp_proxy"

module LocalhostForwardProxy
  Forward = Struct.new(
    :listen_port,
    :target_ip,
    :target_port,
    :container_id,
    :container_name,
    keyword_init: true
  ) do
    def identity
      "#{target_ip} #{target_port} #{container_id} #{container_name}"
    end
  end

  # Watches workspace Compose stacks, attaches the parent container to their networks,
  # and mirrors published host ports onto 127.0.0.1 in the shared network namespace.
  class Watcher
    DEFAULT_HEARTBEAT_SECONDS = 15
    STOP_POLL_SECONDS = 0.25
    EVENTS_RETRY_SECONDS = 2
    IPV4_RETRY_SECONDS = 0.2
    PARENT_LOOKUP_ATTEMPTS = 20
    PARENT_LOOKUP_INTERVAL_SECONDS = 0.25

    def initialize(docker: Docker.new, env: ENV, parent_id: nil, proxy_class: TcpProxy)
      @docker = docker
      @env = env
      @parent_id = parent_id
      @proxy_class = proxy_class
      @mutex = Mutex.new
      @proxies = {}
      @stop = false
      @last_status = nil
    end

    def run
      $stdout.sync = true
      @parent_id ||= parent_container_id
      raise "could not determine the parent devcontainer id" if @parent_id.nil?

      log("mirroring workspace Compose ports onto 127.0.0.1 (parent #{@parent_id[0, 12]})")
      install_signal_traps
      sync

      heartbeat = Thread.new { heartbeat_loop }
      events = Thread.new { events_loop }
      heartbeat.abort_on_exception = true
      events.abort_on_exception = true

      sleep STOP_POLL_SECONDS until @stop
      @docker.stop_event_stream
      stop_all_proxies
      log("stopped")
    end

    def sync
      @mutex.synchronize { sync_unlocked }
    end

    private

    def heartbeat_loop
      until @stop
        sleep heartbeat_seconds
        sync unless @stop
      end
    end

    def events_loop
      until @stop
        @docker.stream_container_events { sync unless @stop }
        break if @stop

        log("docker events ended; retrying in #{EVENTS_RETRY_SECONDS}s")
        sleep EVENTS_RETRY_SECONDS
      end
    end

    def install_signal_traps
      %w[INT TERM].each do |signal|
        Signal.trap(signal) { @stop = true }
      end
    end

    def sync_unlocked
      containers = @docker.running_containers
      parent = find_parent(containers)
      if parent.nil?
        log("parent container #{@parent_id[0, 12]} is not inspectable")
        return
      end

      @discovery = discovery_for(parent)
      desired_forwards = collect_desired_forwards(containers, parent)
      reconcile_proxies(desired_forwards)
      report_status(desired_forwards)
    end

    def find_parent(containers)
      containers.find { |container| Discovery.same_container_id?(container["Id"], @parent_id) } ||
        @docker.inspect(@parent_id)
    end

    def discovery_for(parent)
      Discovery.new(
        workspace_prefixes: workspace_prefixes(parent),
        reserved_ports: reserved_ports_for(parent),
        skip_networks: skip_networks,
        parent_compose_project: Discovery.compose_project(parent)
      )
    end

    def collect_desired_forwards(containers, parent)
      desired_forwards = {}
      containers.each do |container|
        next if @discovery.skip_container?(container, parent_id: @parent_id)

        port_mappings = @discovery.mirrorable_ports(container)
        next if port_mappings.empty?

        container_name = Discovery.container_name(container)
        network_name = ensure_parent_on_child_network(container, parent)
        if network_name.nil?
          log("cannot reach #{container_name} (no attachable Docker network)")
          next
        end

        parent = @docker.inspect(@parent_id) || parent
        ipv4_address = ipv4_for(container, network_name)
        if ipv4_address.empty?
          log("no IPv4 address for #{container_name} on #{network_name}")
          next
        end

        port_mappings.each do |port_mapping|
          listen_port = port_mapping[:host_port]
          if desired_forwards.key?(listen_port)
            other = desired_forwards[listen_port]
            log("skipping #{container_name}:#{listen_port} (already used by #{other.container_name})")
            next
          end

          desired_forwards[listen_port] = Forward.new(
            listen_port: listen_port,
            target_ip: ipv4_address,
            target_port: port_mapping[:private_port],
            container_id: container["Id"],
            container_name: container_name
          )
        end
      end
      desired_forwards
    end

    def reconcile_proxies(desired_forwards)
      (@proxies.keys - desired_forwards.keys).each { |port| stop_proxy(port) }

      desired_forwards.each do |port, forward|
        existing = @proxies[port]
        next if existing&.alive? && existing.identity == forward.identity

        stop_proxy(port)
        start_proxy(forward)
      end
    end

    def ensure_parent_on_child_network(child, parent)
      shared_network = @discovery.shared_attachable_network(child, parent)
      return shared_network if shared_network

      @discovery.attachable_networks(child).each do |network_name|
        if @docker.connect_network(network_name, @parent_id)
          log("attached to network #{network_name}")
          return network_name
        end

        refreshed_parent = @docker.inspect(@parent_id)
        return network_name if refreshed_parent && Discovery.network_names(refreshed_parent).include?(network_name)
      end

      nil
    end

    def ipv4_for(container, network_name)
      ipv4_address = Discovery.ipv4_on_network(container, network_name)
      return ipv4_address unless ipv4_address.empty?

      sleep IPV4_RETRY_SECONDS
      refreshed = @docker.inspect(container["Id"])
      return "" if refreshed.nil?

      Discovery.ipv4_on_network(refreshed, network_name)
    end

    def start_proxy(forward)
      proxy = @proxy_class.new(
        listen_port: forward.listen_port,
        target_host: forward.target_ip,
        target_port: forward.target_port,
        identity: forward.identity
      )
      proxy.start
      unless proxy.alive?
        log("failed to listen on 127.0.0.1:#{forward.listen_port}")
        proxy.stop
        return
      end

      @proxies[forward.listen_port] = proxy
    rescue Errno::EADDRINUSE, Errno::EACCES => error
      log("failed to listen on 127.0.0.1:#{forward.listen_port} (#{error.message})")
    end

    def stop_proxy(port)
      @proxies.delete(port)&.stop
    end

    def stop_all_proxies
      @mutex.synchronize do
        @proxies.keys.each { |port| stop_proxy(port) }
      end
    end

    def report_status(desired_forwards)
      status = if desired_forwards.empty?
        "none (publish a port on a workspace Compose service)"
      else
        desired_forwards.keys.sort.map do |port|
          forward = desired_forwards[port]
          "#{port}→#{forward.container_name}:#{forward.target_port}"
        end.join(", ")
      end
      return if status == @last_status

      @last_status = status
      log(status)
    end

    def parent_container_id
      PARENT_LOOKUP_ATTEMPTS.times do
        id = lookup_parent_container_id
        return id if id

        sleep PARENT_LOOKUP_INTERVAL_SECONDS
      end
      nil
    end

    def lookup_parent_container_id
      hostname = File.read("/etc/hostname").strip
      service = @env.fetch("PARENT_COMPOSE_SERVICE", "devcontainer")

      named = @docker.inspect("#{hostname}-#{service}-1")
      return named["Id"] if named

      @docker.running_containers.find do |container|
        labels = container.dig("Config", "Labels") || {}
        container.dig("Config", "Hostname") == hostname &&
          labels["com.docker.compose.service"] == service
      end&.fetch("Id")
    end

    def workspace_prefixes(parent)
      prefixes = [workspace_container_path]
      host_dir = @env["HOST_WORKSPACE_DIR"]
      host_dir = host_workspace_dir_from_env_file if Discovery.blank?(host_dir)
      prefixes << host_dir unless Discovery.blank?(host_dir)
      prefixes << @env["LOCAL_WORKSPACE_FOLDER"] unless Discovery.blank?(@env["LOCAL_WORKSPACE_FOLDER"])

      working_dir = Discovery.compose_working_dir(parent)
      if working_dir.to_s.end_with?("/.devcontainer")
        prefixes << working_dir.delete_suffix("/.devcontainer")
      end

      prefixes.uniq
    end

    def workspace_container_path
      workdir = @env["SUPER_PROJECTS_WORKDIR"]
      workdir = "workspaces" if Discovery.blank?(workdir)
      "/#{workdir.to_s.delete_prefix("/")}"
    end

    def host_workspace_dir_from_env_file
      path = "#{workspace_container_path}/.devcontainer/.env"
      return nil unless File.readable?(path)

      File.readlines(path).reverse_each do |line|
        next unless line.start_with?("HOST_WORKSPACE_DIR=")

        value = line.split("=", 2)[1].to_s.strip
        return value.delete_prefix('"').delete_suffix('"').delete_prefix("'").delete_suffix("'")
      end
      nil
    end

    def heartbeat_seconds
      configured = @env["LOCALHOST_FORWARD_HEARTBEAT_SECONDS"]
      return DEFAULT_HEARTBEAT_SECONDS if Discovery.blank?(configured)

      seconds = Integer(configured)
      seconds.positive? ? seconds : DEFAULT_HEARTBEAT_SECONDS
    rescue ArgumentError
      DEFAULT_HEARTBEAT_SECONDS
    end

    def reserved_ports
      extra = Discovery.parse_port_list(@env["LOCALHOST_FORWARD_RESERVED_PORTS"])
      (Discovery::DEFAULT_RESERVED_PORTS + extra).uniq
    end

    def reserved_ports_for(parent)
      (reserved_ports + Discovery.parent_published_host_ports(parent)).uniq
    end

    def skip_networks
      extra = Discovery.parse_name_list(@env["LOCALHOST_FORWARD_SKIP_NETWORKS"])
      (Discovery::DEFAULT_SKIP_NETWORKS + extra).uniq
    end

    def log(message)
      $stdout.puts("localhost forwards: #{message}")
    end
  end
end
