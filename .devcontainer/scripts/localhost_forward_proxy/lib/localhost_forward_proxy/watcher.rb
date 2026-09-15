# frozen_string_literal: true

require_relative "docker"
require_relative "discovery"
require_relative "tcp_proxy"

module LocalhostForwardProxy
  # Watches workspace Compose stacks, attaches the parent container to their networks,
  # and mirrors published host ports onto 127.0.0.1 in the shared network namespace.
  class Watcher
    HEARTBEAT_SECONDS = 15

    def initialize(docker: Docker.new, env: ENV)
      @docker = docker
      @env = env
      @mutex = Mutex.new
      @proxies = {}
      @stop = false
      @last_status = nil
    end

    def run
      $stdout.sync = true
      @parent_id = parent_container_id
      raise "could not determine the parent devcontainer id" if @parent_id.nil?

      parent = @docker.inspect(@parent_id)
      @parent_compose_project = parent&.dig("Config", "Labels", "com.docker.compose.project")

      log("mirroring workspace Compose ports onto 127.0.0.1 (parent #{@parent_id[0, 12]})")
      install_signal_traps
      sync

      heartbeat = Thread.new { heartbeat_loop }
      events = Thread.new { events_loop }
      heartbeat.abort_on_exception = true
      events.abort_on_exception = true

      sleep 0.25 until @stop
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
        sleep HEARTBEAT_SECONDS
        sync unless @stop
      end
    end

    def events_loop
      until @stop
        @docker.stream_container_events { sync unless @stop }
        break if @stop

        log("docker events ended; retrying in 2s")
        sleep 2
      end
    end

    def install_signal_traps
      %w[INT TERM].each do |signal|
        Signal.trap(signal) { @stop = true }
      end
    end

    def sync_unlocked
      containers = @docker.running_containers
      parent = containers.find { |container| Discovery.same_container_id?(container["Id"], @parent_id) }
      parent ||= @docker.inspect(@parent_id)
      if parent.nil?
        log("parent container #{@parent_id[0, 12]} is not inspectable")
        return
      end

      @discovery = Discovery.new(
        workspace_prefixes: workspace_prefixes,
        reserved_ports: reserved_ports_for(parent),
        skip_networks: skip_networks,
        parent_compose_project: @parent_compose_project
      )

      desired = {}
      containers.each do |container|
        next if skip_container?(container)

        ports = @discovery.mirrorable_ports(container)
        next if ports.empty?

        name = Discovery.container_name(container)
        network = ensure_parent_on_child_network(container, parent)
        if network.nil?
          log("cannot reach #{name} (no attachable Docker network)")
          next
        end

        parent = @docker.inspect(@parent_id) || parent
        ip = ipv4_for(container, network)
        if ip.nil? || ip.empty?
          log("no IPv4 address for #{name} on #{network}")
          next
        end

        ports.each do |pair|
          listen_port = pair[:host_port]
          if desired.key?(listen_port)
            other = desired[listen_port]
            log("skipping #{name}:#{listen_port} (already used by #{other.container_name})")
            next
          end

          desired[listen_port] = Forward.new(
            listen_port: listen_port,
            target_ip: ip,
            target_port: pair[:private_port],
            container_id: container["Id"],
            container_name: name
          )
        end
      end

      (@proxies.keys - desired.keys).each { |port| stop_proxy(port) }

      desired.each do |port, forward|
        existing = @proxies[port]
        if existing&.alive? && existing.identity == forward.identity
          next
        end

        stop_proxy(port)
        start_proxy(forward)
      end

      report_status(desired)
    end

    def skip_container?(container)
      id = container["Id"]
      return true if Discovery.same_container_id?(id, @parent_id)
      return true if @discovery.parent_compose_project?(container)
      return true unless @discovery.workspace_container?(container)

      false
    end

    def ensure_parent_on_child_network(child, parent)
      child_nets = Discovery.network_names(child).reject { |net| @discovery.skip_network?(net) }
      parent_nets = Discovery.network_names(parent)
      shared = child_nets.find { |net| parent_nets.include?(net) }
      return shared if shared

      child_nets.each do |net|
        if @docker.connect_network(net, @parent_id)
          log("attached to network #{net}")
          return net
        end

        refreshed = @docker.inspect(@parent_id)
        return net if refreshed && Discovery.network_names(refreshed).include?(net)
      end

      nil
    end

    def ipv4_for(container, network)
      ip = Discovery.ipv4_on_network(container, network)
      return ip unless ip.empty?

      sleep 0.2
      refreshed = @docker.inspect(container["Id"])
      return "" if refreshed.nil?

      Discovery.ipv4_on_network(refreshed, network)
    end

    def start_proxy(forward)
      proxy = TcpProxy.new(
        listen_port: forward.listen_port,
        target_host: forward.target_ip,
        target_port: forward.target_port,
        identity: forward.identity
      )
      proxy.start
      sleep 0.05
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

    def report_status(desired)
      status = if desired.empty?
        "none (publish a port on a workspace Compose service)"
      else
        desired.keys.sort.map do |port|
          forward = desired[port]
          "#{port}→#{forward.container_name}:#{forward.target_port}"
        end.join(", ")
      end
      return if status == @last_status

      @last_status = status
      log(status)
    end

    def parent_container_id
      20.times do
        id = lookup_parent_container_id
        return id if id

        sleep 0.25
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

    def workspace_prefixes
      prefixes = [workspace_container_path]
      host_dir = @env["HOST_WORKSPACE_DIR"]
      if Discovery.blank?(host_dir)
        host_dir = host_workspace_dir_from_env_file
      end
      prefixes << host_dir unless Discovery.blank?(host_dir)
      prefixes << @env["LOCAL_WORKSPACE_FOLDER"] unless Discovery.blank?(@env["LOCAL_WORKSPACE_FOLDER"])

      parent = @docker.inspect(@parent_id)
      working_dir = Discovery.compose_working_dir(parent) if parent
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

    def reserved_ports
      extra = Discovery.parse_port_list(@env.fetch("LOCALHOST_FORWARD_RESERVED_PORTS", "6080,5900,9223"))
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
