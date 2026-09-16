# frozen_string_literal: true

require "socket"
require_relative "../lib/localhost_forward_proxy"

failures = 0

def assert(condition, message)
  unless condition
    warn("FAIL: #{message}")
    return false
  end
  puts("ok: #{message}")
  true
end

def free_port
  server = TCPServer.new("127.0.0.1", 0)
  server.addr[1]
ensure
  server.close
end

class RecordingProxy
  class << self
    attr_accessor :started
  end

  attr_reader :listen_port, :target_host, :target_port, :identity

  def initialize(listen_port:, target_host:, target_port:, identity:)
    @listen_port = listen_port
    @target_host = target_host
    @target_port = target_port
    @identity = identity
    @started = false
    @stopped = false
    self.class.started << self
  end

  def start
    @started = true
    self
  end

  def stop
    @stopped = true
    self
  end

  def alive?
    @started && !@stopped
  end
end

class FakeDocker
  attr_reader :network_connects

  def initialize(containers)
    @containers = containers
    @network_connects = []
  end

  def running_containers
    @containers
  end

  def inspect(container_id)
    @containers.find do |container|
      LocalhostForwardProxy::Discovery.same_container_id?(container["Id"], container_id)
    end
  end

  def connect_network(network_name, container_id)
    @network_connects << [network_name, container_id]
    parent = inspect(container_id)
    if parent
      networks = parent.dig("NetworkSettings", "Networks") || {}
      networks[network_name] = { "IPAddress" => "172.19.0.2" }
      parent["NetworkSettings"]["Networks"] = networks
    end
    true
  end
end

failures += 1 unless assert(
  LocalhostForwardProxy::Discovery.path_under?("/workspaces/sample_app_1", "/workspaces"),
  "container-side compose working_dir is under /workspaces"
)
failures += 1 unless assert(
  LocalhostForwardProxy::Discovery.path_under?(
    "/home/sam/projects/super_projects/sample_app_1",
    "/home/sam/projects/super_projects"
  ),
  "host bind source is under HOST_WORKSPACE_DIR"
)
failures += 1 unless assert(
  !LocalhostForwardProxy::Discovery.path_under?("/workspaces-other/app", "/workspaces"),
  "a sibling prefix is not treated as under the workspace"
)
failures += 1 unless assert(
  LocalhostForwardProxy::Discovery.same_container_id?("sha256:abc123def456", "abc123"),
  "short and long container ids match"
)
failures += 1 unless assert(
  LocalhostForwardProxy::Discovery.parse_port_list(" 8080, 9090 ") == [8080, 9090],
  "port lists split on commas"
)
failures += 1 unless assert(
  LocalhostForwardProxy::Discovery.parse_name_list("app_net, other_net") == %w[app_net other_net],
  "name lists split on commas"
)

discovery = LocalhostForwardProxy::Discovery.new(
  workspace_prefixes: ["/workspaces", "/host/super_projects"],
  reserved_ports: [6080, 3000],
  skip_networks: LocalhostForwardProxy::Discovery::DEFAULT_SKIP_NETWORKS,
  parent_compose_project: "super_projects"
)

sample_app = {
  "Id" => "aaa",
  "Name" => "/sample_app_1-web-1",
  "Config" => {
    "Labels" => {
      "com.docker.compose.project" => "sample_app_1",
      "com.docker.compose.project.working_dir" => "/host/super_projects/sample_app_1",
      "com.docker.compose.project.config_files" => "/host/super_projects/sample_app_1/docker-compose.yaml"
    }
  },
  "Mounts" => [
    { "Type" => "bind", "Source" => "/host/super_projects/sample_app_1" }
  ],
  "NetworkSettings" => {
    "Networks" => {
      "sample_app_1_default" => { "IPAddress" => "172.18.0.2" },
      "bridge" => { "IPAddress" => "172.17.0.2" }
    },
    "Ports" => {
      "80/tcp" => [{ "HostIp" => "0.0.0.0", "HostPort" => "3000" }],
      "443/tcp" => [{ "HostIp" => "0.0.0.0", "HostPort" => "3443" }],
      "53/udp" => [{ "HostIp" => "0.0.0.0", "HostPort" => "5353" }]
    }
  }
}

parent = {
  "Id" => "parentid",
  "Config" => {
    "Labels" => {
      "com.docker.compose.project" => "super_projects",
      "com.docker.compose.service" => "devcontainer",
      "com.docker.compose.project.working_dir" => "/host/super_projects/.devcontainer"
    }
  },
  "NetworkSettings" => {
    "Networks" => { "super_projects_default" => { "IPAddress" => "172.19.0.2" } },
    "Ports" => {
      "6080/tcp" => [{ "HostIp" => "0.0.0.0", "HostPort" => "6080" }]
    }
  }
}

sibling_in_parent_project = {
  "Id" => "sidecar",
  "Name" => "/super_projects-localhost_forward_proxy-1",
  "Config" => {
    "Labels" => {
      "com.docker.compose.project" => "super_projects",
      "com.docker.compose.project.working_dir" => "/host/super_projects/.devcontainer"
    }
  },
  "NetworkSettings" => {
    "Networks" => { "super_projects_default" => { "IPAddress" => "172.19.0.3" } },
    "Ports" => {}
  }
}

outside_workspace = {
  "Id" => "other",
  "Name" => "/unrelated-web-1",
  "Config" => {
    "Labels" => {
      "com.docker.compose.project" => "unrelated",
      "com.docker.compose.project.working_dir" => "/unrelated"
    }
  },
  "Mounts" => [],
  "NetworkSettings" => {
    "Networks" => { "unrelated_default" => { "IPAddress" => "172.20.0.2" } },
    "Ports" => {
      "80/tcp" => [{ "HostIp" => "0.0.0.0", "HostPort" => "8080" }]
    }
  }
}

colliding_app = {
  "Id" => "bbb",
  "Name" => "/sample_app_2-web-1",
  "Config" => {
    "Labels" => {
      "com.docker.compose.project" => "sample_app_2",
      "com.docker.compose.project.working_dir" => "/host/super_projects/sample_app_2"
    }
  },
  "Mounts" => [
    { "Type" => "bind", "Source" => "/host/super_projects/sample_app_2" }
  ],
  "NetworkSettings" => {
    "Networks" => {
      "sample_app_2_default" => { "IPAddress" => "172.21.0.2" }
    },
    "Ports" => {
      "80/tcp" => [{ "HostIp" => "0.0.0.0", "HostPort" => "3443" }]
    }
  }
}

failures += 1 unless assert(discovery.workspace_container?(sample_app), "sample app is a workspace container")
failures += 1 unless assert(discovery.parent_compose_project?(parent), "parent compose project is skipped")
failures += 1 unless assert(!discovery.parent_compose_project?(sample_app), "sample app is not the parent project")
failures += 1 unless assert(
  discovery.skip_container?(parent, parent_id: "parentid"),
  "the parent container itself is skipped"
)
failures += 1 unless assert(
  discovery.skip_container?(sibling_in_parent_project, parent_id: "parentid"),
  "sibling containers in the parent compose project are skipped"
)
failures += 1 unless assert(
  discovery.skip_container?(outside_workspace, parent_id: "parentid"),
  "containers outside the workspace are skipped"
)
failures += 1 unless assert(
  !discovery.skip_container?(sample_app, parent_id: "parentid"),
  "workspace apps are not skipped"
)
failures += 1 unless assert(discovery.skip_network?("bridge"), "bridge is not attachable")
failures += 1 unless assert(
  discovery.attachable_networks(sample_app) == ["sample_app_1_default"],
  "attachable networks skip bridge"
)
failures += 1 unless assert(
  discovery.shared_attachable_network(sample_app, parent).nil?,
  "parent is not yet on the sample app network"
)
failures += 1 unless assert(
  discovery.first_attachable_network(sample_app, parent) == "sample_app_1_default",
  "first attachable network skips bridge"
)
failures += 1 unless assert(discovery.reserved_port?(3000), "reserved host ports are not mirrored")
failures += 1 unless assert(
  discovery.mirrorable_ports(sample_app) == [{ host_port: 3443, private_port: 443 }],
  "udp and reserved tcp ports are dropped"
)
failures += 1 unless assert(
  LocalhostForwardProxy::Discovery.parent_published_host_ports(parent) == [6080],
  "parent published ports are collected"
)

parent_already_attached = Marshal.load(Marshal.dump(parent))
parent_already_attached["NetworkSettings"]["Networks"]["sample_app_1_default"] = { "IPAddress" => "172.18.0.9" }
failures += 1 unless assert(
  discovery.shared_attachable_network(sample_app, parent_already_attached) == "sample_app_1_default",
  "shared attachable network is preferred when the parent is already connected"
)

RecordingProxy.started = []
fake_docker = FakeDocker.new([parent, sample_app, sibling_in_parent_project, outside_workspace, colliding_app])
watcher = LocalhostForwardProxy::Watcher.new(
  docker: fake_docker,
  env: {
    "HOST_WORKSPACE_DIR" => "/host/super_projects",
    "SUPER_PROJECTS_WORKDIR" => "workspaces",
    "LOCALHOST_FORWARD_RESERVED_PORTS" => "3000"
  },
  parent_id: "parentid",
  proxy_class: RecordingProxy
)
watcher.sync

started = RecordingProxy.started
failures += 1 unless assert(
  fake_docker.network_connects == [["sample_app_1_default", "parentid"], ["sample_app_2_default", "parentid"]],
  "parent is attached to workspace app networks"
)
failures += 1 unless assert(started.length == 1, "only the first owner of a host port is proxied")
failures += 1 unless assert(
  started.first.listen_port == 3443 && started.first.target_port == 443 && started.first.target_host == "172.18.0.2",
  "watcher proxies the sample app host port to the container IPv4"
)
failures += 1 unless assert(
  started.none? { |proxy| proxy.listen_port == 8080 },
  "containers outside the workspace are not proxied"
)
failures += 1 unless assert(
  started.none? { |proxy| proxy.listen_port == 3000 },
  "extra reserved ports from env are not proxied"
)

backend_port = free_port
listen_port = free_port
backend = TCPServer.new("127.0.0.1", backend_port)
backend_thread = Thread.new do
  client = backend.accept
  client.write(client.readpartial(5))
  client.close
end
proxy = LocalhostForwardProxy::TcpProxy.new(
  listen_port: listen_port,
  target_host: "127.0.0.1",
  target_port: backend_port,
  identity: "test"
).start
response = Socket.tcp("127.0.0.1", listen_port) do |client|
  client.write("hello")
  client.readpartial(5)
end
proxy.stop
backend_thread.join(1)
backend.close

failures += 1 unless assert(response == "hello", "tcp proxy copies bytes in both directions")

if failures.positive?
  warn("#{failures} failure(s)")
  exit 1
end

puts("all checks passed")
