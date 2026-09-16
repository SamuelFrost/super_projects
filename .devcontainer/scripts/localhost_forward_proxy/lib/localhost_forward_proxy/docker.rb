# frozen_string_literal: true

require "json"
require "open3"

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

    def connect_network(network_name, container_id)
      _out, _err, status = run_command(
        "docker", "network", "connect", network_name, container_id,
        timeout_seconds: NETWORK_CONNECT_TIMEOUT_SECONDS
      )
      status.success?
    rescue CommandError
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
      terminate_process(@events_pid)
    end

    private

    def capture(*args)
      out, err, status = run_command(*args, timeout_seconds: DEFAULT_TIMEOUT_SECONDS)
      raise CommandError, "#{args.join(" ")}: #{err.strip}" unless status.success?

      out
    end

    def run_command(*args, timeout_seconds:)
      Open3.popen3(*args) do |stdin, stdout, stderr, wait_thread|
        stdin.close
        stdout_thread = Thread.new { stdout.read }
        stderr_thread = Thread.new { stderr.read }

        unless wait_thread.join(timeout_seconds)
          terminate_process(wait_thread.pid)
          wait_thread.join(1)
          stdout_thread.join(1)
          stderr_thread.join(1)
          raise CommandError, "#{args.join(" ")}: timed out after #{timeout_seconds}s"
        end

        [stdout_thread.value, stderr_thread.value, wait_thread.value]
      end
    end

    def terminate_process(pid)
      return if pid.nil?

      Process.kill("TERM", pid)
    rescue Errno::ESRCH
      nil
    end

    class CommandError < StandardError; end
  end
end
