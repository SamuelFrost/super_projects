# frozen_string_literal: true

require_relative "docker"
require_relative "tcp_proxy"

module LocalhostForwardProxy
  # Mirrors the published TCP `ports:` of docker compose stacks in the workspace onto super_projects default network localhost.
  #
  # Runs in the devcontainer's network namespace. Every sync inspects running containers, attaches the
  # devcontainer to a stack's compose network when needed so the sidecar can reach the container's private IP,
  # and keeps one TcpProxy per published host port.
  class Watcher
    HEARTBEAT_SECONDS = 15
    EVENTS_RETRY_SECONDS = 2
    DEVCONTAINER_SERVICE = "devcontainer"
    # Docker's built-in networks: skipped as attach targets. host/none cannot be used this way; default bridge is not a Compose project network.
    UNATTACHABLE_NETWORKS = %w[bridge host none].freeze

    Forward = Struct.new(:listen_port, :target_ip, :target_port, :container_name, keyword_init: true)

    def initialize(docker: Docker.new, env: ENV, proxy_class: TcpProxy)
      @docker = docker
      @env = env
      @proxy_class = proxy_class
      @proxies = {}
      @sync_mutex = Mutex.new
      @last_status = nil
    end

    def run
      $stdout.sync = true
      %w[INT TERM].each { |signal| Signal.trap(signal) { exit } }
      log("mirroring published ports of compose stacks under #{workspace_prefixes.join(" or ")} onto 127.0.0.1 and ::1")

      sync
      heartbeat = Thread.new do
        loop do
          sleep HEARTBEAT_SECONDS
          sync
        end
      end
      heartbeat.abort_on_exception = true # an unexpected failure here exits so Compose can restart the sidecar
      loop do
        @docker.each_container_start_or_die { sync }
        log("docker events stream ended; retrying in #{EVENTS_RETRY_SECONDS}s")
        sleep EVENTS_RETRY_SECONDS
      end
    end

    def sync
      @sync_mutex.synchronize do
        containers = @docker.running_containers
        devcontainer = containers.find { |container| devcontainer?(container) }
        raise "no running #{DEVCONTAINER_SERVICE} container in compose project #{compose_project_name}" if devcontainer.nil?

        forwards = desired_forwards(containers, devcontainer)
        reconcile_proxies(forwards)
        report_status(forwards)
      end
    rescue Docker::CommandError => error
      log(error.message)
    end

    private

    def desired_forwards(containers, devcontainer)
      devcontainer_networks = network_names(devcontainer)
      forwards = {}
      containers.each do |container|
        next unless workspace_stack_container?(container)

        published_ports = published_tcp_ports(container)
        next if published_ports.empty?

        container_name = container["Name"].delete_prefix("/")
        network_name = reachable_network(container, devcontainer, devcontainer_networks)
        if network_name.nil?
          log("cannot reach #{container_name}: no attachable network")
          next
        end

        target_ip = container.dig("NetworkSettings", "Networks", network_name, "IPAddress")
        published_ports.each do |host_port, private_port|
          forwards[host_port] = Forward.new(
            listen_port: host_port, target_ip: target_ip, target_port: private_port, container_name: container_name
          )
        end
      end
      forwards
    end

    def workspace_stack_container?(container)
      return false if compose_label(container, "project") == compose_project_name

      working_dir = compose_label(container, "project.working_dir").to_s
      workspace_prefixes.any? { |prefix| working_dir == prefix || working_dir.start_with?("#{prefix}/") }
    end

    # { host_port => private_port } for every TCP port the container publishes.
    def published_tcp_ports(container)
      ports = {}
      (container.dig("NetworkSettings", "Ports") || {}).each do |private_spec, bindings|
        private_port, protocol = private_spec.split("/")
        next unless protocol == "tcp"

        Array(bindings).each do |binding|
          host_port = binding["HostPort"].to_i
          ports[host_port] = private_port.to_i if host_port.positive?
        end
      end
      ports
    end

    # A compose network the devcontainer shares with the container, attaching the devcontainer to one if needed.
    def reachable_network(container, devcontainer, devcontainer_networks)
      candidates = network_names(container) - UNATTACHABLE_NETWORKS
      shared = candidates.find { |network_name| devcontainer_networks.include?(network_name) }
      return shared if shared

      network_name = candidates.first
      return nil if network_name.nil?

      @docker.connect_network(network_name, devcontainer["Id"])
      devcontainer_networks << network_name
      log("attached #{DEVCONTAINER_SERVICE} to network #{network_name}")
      network_name
    end

    def reconcile_proxies(forwards)
      (@proxies.keys - forwards.keys).each { |listen_port| @proxies.delete(listen_port).stop }

      forwards.each do |listen_port, forward|
        proxy = @proxies[listen_port]
        next if proxy && proxy.target_host == forward.target_ip && proxy.target_port == forward.target_port

        @proxies.delete(listen_port)&.stop
        @proxies[listen_port] = @proxy_class.new(
          listen_port: listen_port, target_host: forward.target_ip, target_port: forward.target_port
        ).start
      rescue Errno::EADDRINUSE
        nil # reported by report_status; retried on the next sync
      end
    end

    def report_status(forwards)
      status = forwards.values.sort_by(&:listen_port).map do |forward|
        if @proxies.key?(forward.listen_port)
          "#{forward.listen_port}→#{forward.container_name}:#{forward.target_port}"
        else
          "#{forward.listen_port} skipped (port already in use in the #{DEVCONTAINER_SERVICE})"
        end
      end.join(", ")
      status = "no published ports to mirror" if status.empty?
      return if status == @last_status

      @last_status = status
      log(status)
    end

    def devcontainer?(container)
      compose_label(container, "project") == compose_project_name &&
        compose_label(container, "service") == DEVCONTAINER_SERVICE
    end

    def compose_project_name
      @env.fetch("SUPER_PROJECTS_NAME", "super_projects")
    end

    # The workspace as seen from inside the devcontainer and from the Docker host: compose stacks started from
    # either place carry that path in their working_dir label.
    def workspace_prefixes
      prefixes = ["/#{@env.fetch("SUPER_PROJECTS_WORKDIR", "workspaces")}"]
      host_workspace_dir = @env["HOST_WORKSPACE_DIR"].to_s
      prefixes << host_workspace_dir unless host_workspace_dir.empty?
      prefixes
    end

    def compose_label(container, key)
      container.dig("Config", "Labels", "com.docker.compose.#{key}")
    end

    def network_names(container)
      (container.dig("NetworkSettings", "Networks") || {}).keys
    end

    def log(message)
      $stdout.puts("localhost forwards: #{message}")
    end
  end
end
