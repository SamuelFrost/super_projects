# frozen_string_literal: true

require "json"
require "open3"

module LocalhostForwardProxy
  # Thin wrapper around the Docker CLI, which talks to the host daemon through the mounted socket.
  class Docker
    class CommandError < StandardError; end

    CONTAINER_START_OR_DIE_EVENTS = %w[docker events --filter type=container --filter event=start --filter event=die].freeze

    # Full `docker inspect` JSON for every running container on the host.
    def running_containers
      ids = run("ps", "--quiet").split
      return [] if ids.empty?

      # A container can exit between ps and inspect; inspect still prints the others but exits non-zero.
      stdout, = Open3.capture3("docker", "inspect", *ids)
      stdout.empty? ? [] : JSON.parse(stdout)
    end

    def connect_network(network_name, container_id)
      run("network", "connect", network_name, container_id)
    end

    # Yields once per container start/die anywhere on the host, until the stream ends (for example a daemon restart).
    def each_container_start_or_die
      events = IO.popen(CONTAINER_START_OR_DIE_EVENTS)
      events.each_line { yield }
      events.close
    end

    private

    def run(*args)
      stdout, stderr, status = Open3.capture3("docker", *args)
      raise CommandError, "docker #{args.join(" ")}: #{stderr.strip}" unless status.success?

      stdout
    end
  end
end
