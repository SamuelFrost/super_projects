# frozen_string_literal: true

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

  # Pure inspect-JSON helpers: which containers belong to the workspace, which ports to mirror.
  class Discovery
    DEFAULT_RESERVED_PORTS = [6080, 5900, 9223].freeze
    DEFAULT_SKIP_NETWORKS = %w[bridge host none ingress docker_gwbridge].freeze

    def initialize(workspace_prefixes:, reserved_ports:, skip_networks:, parent_compose_project:)
      @workspace_prefixes = workspace_prefixes
      @reserved_ports = reserved_ports.map(&:to_i)
      @skip_networks = skip_networks
      @parent_compose_project = parent_compose_project
    end

    def self.blank?(value)
      value.nil? || value.to_s.empty? || value.to_s == "<no value>"
    end

    def self.path_under?(path, prefix)
      return false if blank?(path) || blank?(prefix)

      path = path.to_s.chomp("/")
      prefix = prefix.to_s.chomp("/")
      path == prefix || path.start_with?("#{prefix}/")
    end

    def self.same_container_id?(left, right)
      a = left.to_s.delete_prefix("sha256:")
      b = right.to_s.delete_prefix("sha256:")
      return false if a.empty? || b.empty?

      a == b || a.start_with?(b) || b.start_with?(a)
    end

    def self.container_name(container)
      name = container.dig("Name") || container.dig("Config", "Labels", "com.docker.compose.service") || container["Id"]
      name.to_s.delete_prefix("/")
    end

    def self.compose_project(container)
      container.dig("Config", "Labels", "com.docker.compose.project")
    end

    def self.compose_working_dir(container)
      container.dig("Config", "Labels", "com.docker.compose.project.working_dir")
    end

    def self.network_names(container)
      (container.dig("NetworkSettings", "Networks") || {}).keys
    end

    def self.ipv4_on_network(container, network)
      container.dig("NetworkSettings", "Networks", network, "IPAddress").to_s
    end

    def self.published_host_ports(container)
      container.dig("NetworkSettings", "Ports") || {}
    end

    def self.parent_published_host_ports(container)
      published_tcp_forwards(container).map { |fwd| fwd[:host_port] }
    end

    def self.published_tcp_forwards(container)
      seen = {}
      forwards = []
      published_host_ports(container).each do |private_spec, bindings|
        next if bindings.nil?
        next if private_spec.end_with?("/udp")

        private_port = private_spec.to_i
        next if private_port.zero?

        Array(bindings).each do |binding|
          host_port = binding["HostPort"].to_s
          next unless host_port.match?(/\A\d+\z/)

          host_port = host_port.to_i
          next if seen[host_port]

          seen[host_port] = true
          forwards << { host_port: host_port, private_port: private_port }
        end
      end
      forwards
    end

    def self.parse_port_list(value)
      value.to_s.split(",").map(&:strip).reject(&:empty?).map(&:to_i)
    end

    def self.parse_name_list(value)
      value.to_s.split(",").map(&:strip).reject(&:empty?)
    end

    def skip_network?(name)
      @skip_networks.include?(name)
    end

    def reserved_port?(port)
      @reserved_ports.include?(port.to_i)
    end

    def parent_compose_project?(container)
      project = self.class.compose_project(container)
      !self.class.blank?(@parent_compose_project) && project == @parent_compose_project
    end

    def workspace_container?(container)
      return true if under_workspace?(self.class.compose_working_dir(container))

      config_files = container.dig("Config", "Labels", "com.docker.compose.project.config_files").to_s
      config_files.split(/[, ]+/).each do |part|
        return true if under_workspace?(part)
      end

      Array(container["Mounts"]).each do |mount|
        next unless mount["Type"] == "bind"
        return true if under_workspace?(mount["Source"])
      end

      false
    end

    def mirrorable_ports(container)
      self.class.published_tcp_forwards(container).reject { |fwd| reserved_port?(fwd[:host_port]) }
    end

    def first_attachable_network(child, parent)
      child_nets = self.class.network_names(child)
      parent_nets = self.class.network_names(parent)

      shared = child_nets.find { |net| !skip_network?(net) && parent_nets.include?(net) }
      return shared if shared

      child_nets.find { |net| !skip_network?(net) }
    end

    private

    def under_workspace?(path)
      @workspace_prefixes.any? { |prefix| self.class.path_under?(path, prefix) }
    end
  end
end
