# frozen_string_literal: true

require "json"
require "open3"
require "timeout"

module LocalhostForwardProxy
  # Thin wrapper around the Docker CLI (the sidecar talks to the host daemon via the socket).
  class Docker
    DEFAULT_TIMEOUT_SECONDS = 15
    NETWORK_CONNECT_TIMEOUT_SECONDS = 5

    def running_containers
      ids = capture("docker", "ps", "-q").split
      return [] if ids.empty?

      JSON.parse(capture("docker", "inspect", *ids))
    end

    def inspect(container_id)
      JSON.parse(capture("docker", "inspect", container_id)).first
    rescue CommandError
      nil
    end

    def connect_network(network, container_id)
      Timeout.timeout(NETWORK_CONNECT_TIMEOUT_SECONDS) do
        _out, _err, status = Open3.capture3("docker", "network", "connect", network, container_id)
        status.success?
      end
    rescue Timeout::Error
      false
    end

    def stream_container_events
      Open3.popen2("docker", "events", "--filter", "type=container", "--format", "{{.Action}}") do |_stdin, stdout, waiter|
        @events_pid = waiter.pid
        stdout.each_line { |line| yield line.strip }
      ensure
        @events_pid = nil
      end
    end

    def stop_event_stream
      pid = @events_pid
      return if pid.nil?

      Process.kill("TERM", pid)
    rescue Errno::ESRCH
      nil
    end

    private

    def capture(*args)
      out, err, status = Timeout.timeout(DEFAULT_TIMEOUT_SECONDS) { Open3.capture3(*args) }
      raise CommandError, "#{args.join(" ")}: #{err.strip}" unless status.success?

      out
    end

    class CommandError < StandardError; end
  end
end
