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

failures += 1 unless assert(discovery.workspace_container?(sample_app), "sample app is a workspace container")
failures += 1 unless assert(discovery.parent_compose_project?(parent), "parent compose project is skipped")
failures += 1 unless assert(!discovery.parent_compose_project?(sample_app), "sample app is not the parent project")
failures += 1 unless assert(discovery.skip_network?("bridge"), "bridge is not attachable")
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
sleep 0.05
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
