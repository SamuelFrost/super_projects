# frozen_string_literal: true

require "socket"
require "stringio"
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
    attr_accessor :started, :ports_in_use
  end

  attr_reader :listen_port, :target_host, :target_port, :stopped

  def initialize(listen_port:, target_host:, target_port:)
    @listen_port = listen_port
    @target_host = target_host
    @target_port = target_port
    @stopped = false
  end

  def start
    raise Errno::EADDRINUSE if self.class.ports_in_use.include?(@listen_port)

    self.class.started << self
    self
  end

  def stop
    @stopped = true
  end
end

class FakeDocker
  attr_reader :network_connects
  attr_accessor :containers

  def initialize(containers)
    @containers = containers
    @network_connects = []
  end

  def running_containers
    @containers
  end

  def connect_network(network_name, container_id)
    @network_connects << [network_name, container_id]
    target = @containers.find { |container| container["Id"] == container_id }
    target["NetworkSettings"]["Networks"][network_name] = { "IPAddress" => "172.18.0.9" }
  end
end

def compose_container(id:, name:, project:, working_dir:, service: name, networks:, ports: {}, mounts: [])
  {
    "Id" => id,
    "Name" => "/#{name}",
    "Config" => {
      "Labels" => {
        "com.docker.compose.project" => project,
        "com.docker.compose.service" => service,
        "com.docker.compose.project.working_dir" => working_dir
      }
    },
    "NetworkSettings" => { "Networks" => networks, "Ports" => ports },
    "Mounts" => mounts
  }
end

def published(host_port)
  [{ "HostIp" => "127.0.0.1", "HostPort" => host_port.to_s }, { "HostIp" => "::1", "HostPort" => host_port.to_s }]
end

devcontainer = compose_container(
  id: "devcontainerid", name: "super_projects-devcontainer-1", project: "super_projects", service: "devcontainer",
  working_dir: "/host/super_projects/.devcontainer",
  networks: { "super_projects_default" => { "IPAddress" => "172.19.0.2" } },
  ports: { "6080/tcp" => published(6080) },
  mounts: [{ "Type" => "bind", "Source" => "/host/super_projects", "Destination" => "/workspaces" }]
)
sidecar_in_super_projects_project = compose_container(
  id: "sidecarid", name: "super_projects-localhost_forward_proxy-1", project: "super_projects",
  service: "localhost_forward_proxy", working_dir: "/host/super_projects/.devcontainer",
  networks: { "super_projects_default" => { "IPAddress" => "172.19.0.3" } },
  ports: { "8000/tcp" => published(8000) }
)
sample_app = compose_container(
  id: "sampleid", name: "sample_app_1-sample_app_1-1", project: "sample_app_1", working_dir: "/workspaces/sample_app_1",
  networks: { "sample_app_1_default" => { "IPAddress" => "172.18.0.2" }, "bridge" => { "IPAddress" => "172.17.0.2" } },
  ports: {
    "80/tcp" => published(3000),
    "443/tcp" => published(3443),
    "53/udp" => published(5353),
    "5432/tcp" => nil
  }
)
sample_app_postgres = compose_container(
  id: "postgresid", name: "sample_app_1-postgres-1", project: "sample_app_1", working_dir: "/workspaces/sample_app_1",
  networks: { "sample_app_1_default" => { "IPAddress" => "172.18.0.3" } },
  ports: { "5432/tcp" => published(5432) }
)
host_started_app = compose_container(
  id: "hostappid", name: "host_app-web-1", project: "host_app", working_dir: "/host/super_projects/host_app",
  networks: { "host_app_default" => { "IPAddress" => "172.20.0.2" } },
  ports: { "80/tcp" => published(4000) }
)
outside_workspace = compose_container(
  id: "otherid", name: "unrelated-web-1", project: "unrelated", working_dir: "/elsewhere/unrelated",
  networks: { "unrelated_default" => { "IPAddress" => "172.21.0.2" } },
  ports: { "80/tcp" => published(8080) }
)
sibling_path_app = compose_container(
  id: "siblingid", name: "sibling-web-1", project: "sibling", working_dir: "/workspaces-other/app",
  networks: { "sibling_default" => { "IPAddress" => "172.22.0.2" } },
  ports: { "80/tcp" => published(8081) }
)

RecordingProxy.started = []
RecordingProxy.ports_in_use = [3443]
fake_docker = FakeDocker.new(
  [devcontainer, sidecar_in_super_projects_project, sample_app, sample_app_postgres, host_started_app, outside_workspace, sibling_path_app]
)
watcher = LocalhostForwardProxy::Watcher.new(
  docker: fake_docker,
  env: { "SUPER_PROJECTS_NAME" => "super_projects" },
  proxy_class: RecordingProxy
)

log = StringIO.new
$stdout = log
watcher.sync
$stdout = STDOUT

started = RecordingProxy.started
failures += 1 unless assert(
  fake_docker.network_connects == [["sample_app_1_default", "devcontainerid"], ["host_app_default", "devcontainerid"]],
  "the devcontainer is attached once per workspace stack network, skipping the bridge network"
)
failures += 1 unless assert(
  started.map { |proxy| [proxy.listen_port, proxy.target_host, proxy.target_port] }.sort ==
    [[3000, "172.18.0.2", 80], [4000, "172.20.0.2", 80], [5432, "172.18.0.3", 5432]],
  "published tcp ports of stacks started in the container or on the host are proxied to the container IPv4"
)
failures += 1 unless assert(
  started.none? { |proxy| proxy.listen_port == 5353 },
  "udp ports are not proxied"
)
failures += 1 unless assert(
  started.none? { |proxy| [8000, 6080].include?(proxy.listen_port) },
  "containers of the super_projects compose project are not proxied"
)
failures += 1 unless assert(
  started.none? { |proxy| [8080, 8081].include?(proxy.listen_port) },
  "stacks outside the workspace (including sibling path prefixes) are not proxied"
)
failures += 1 unless assert(
  log.string.include?("3443 skipped (port already in use in the devcontainer)"),
  "a port already bound in the shared namespace is reported and skipped"
)
failures += 1 unless assert(
  log.string.include?("3000→sample_app_1-sample_app_1-1:80"),
  "status logs the active forwards"
)

watcher.sync
failures += 1 unless assert(
  started.length == 3 && started.none?(&:stopped) && fake_docker.network_connects.length == 2,
  "an unchanged sync keeps the running proxies and does not reattach networks"
)

recreated_sample_app = Marshal.load(Marshal.dump(sample_app))
recreated_sample_app["Id"] = "sampleid2"
recreated_sample_app["NetworkSettings"]["Networks"]["sample_app_1_default"]["IPAddress"] = "172.18.0.5"
fake_docker.containers = [devcontainer, recreated_sample_app]
watcher.sync
sample_app_proxies = started.select { |proxy| proxy.listen_port == 3000 }
failures += 1 unless assert(
  sample_app_proxies.map(&:stopped) == [true, false] && sample_app_proxies.last.target_host == "172.18.0.5",
  "a recreated container with a new IPv4 replaces its proxy"
)
failures += 1 unless assert(
  started.select { |proxy| [4000, 5432].include?(proxy.listen_port) }.all?(&:stopped),
  "proxies of containers that went away are stopped"
)

fake_docker.containers = [sample_app]
log = StringIO.new
$stdout = log
begin
  watcher.sync
rescue RuntimeError => error
  devcontainer_missing_error = error
end
$stdout = STDOUT
failures += 1 unless assert(
  devcontainer_missing_error&.message == "no running devcontainer container in compose project super_projects",
  "sync fails loudly when the devcontainer is not running"
)

backend_port = free_port
listen_port = free_port
backend = TCPServer.new("127.0.0.1", backend_port)
backend_thread = Thread.new do
  loop do
    client = backend.accept
    client.write(client.readpartial(5))
    client.close
  end
rescue IOError, SystemCallError
  nil
end
proxy = LocalhostForwardProxy::TcpProxy.new(listen_port: listen_port, target_host: "127.0.0.1", target_port: backend_port).start
response = Socket.tcp("127.0.0.1", listen_port) do |client|
  client.write("hello")
  client.readpartial(5)
end
failures += 1 unless assert(response == "hello", "tcp proxy copies bytes in both directions on 127.0.0.1")

begin
  ipv6_response = Socket.tcp("::1", listen_port, connect_timeout: 1) do |client|
    client.write("hello")
    client.readpartial(5)
  end
rescue Errno::ECONNREFUSED, Errno::EADDRNOTAVAIL, Errno::EHOSTUNREACH, SocketError
  ipv6_response = nil
end
if ipv6_response.nil?
  puts("skip: ::1 not listening (IPv6 loopback unavailable)")
else
  failures += 1 unless assert(ipv6_response == "hello", "tcp proxy copies bytes in both directions on ::1")
end

begin
  LocalhostForwardProxy::TcpProxy.new(listen_port: listen_port, target_host: "127.0.0.1", target_port: backend_port).start
  address_in_use = false
rescue Errno::EADDRINUSE
  address_in_use = true
end
failures += 1 unless assert(address_in_use, "starting a proxy on a bound port raises Errno::EADDRINUSE")

proxy.stop
backend.close
backend_thread.join(1)
begin
  Socket.tcp("127.0.0.1", listen_port, connect_timeout: 1) { nil }
  listener_closed = false
rescue Errno::ECONNREFUSED
  listener_closed = true
end
failures += 1 unless assert(listener_closed, "a stopped proxy no longer accepts connections on 127.0.0.1")

if failures.positive?
  warn("#{failures} failure(s)")
  exit 1
end

puts("all checks passed")
