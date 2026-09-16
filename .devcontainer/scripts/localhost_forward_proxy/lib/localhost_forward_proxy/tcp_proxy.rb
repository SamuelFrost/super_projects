# frozen_string_literal: true

require "socket"

module LocalhostForwardProxy
  # Accepts connections on 127.0.0.1 and ::1 (when IPv6 exists) and copies bytes both ways to target_host:target_port.
  class TcpProxy
    CONNECT_TIMEOUT_SECONDS = 10

    attr_reader :listen_port, :target_host, :target_port

    def initialize(listen_port:, target_host:, target_port:)
      @listen_port = listen_port
      @target_host = target_host
      @target_port = target_port
      @open_sockets = []
      @open_sockets_mutex = Mutex.new
    end

    # Raises Errno::EADDRINUSE when 127.0.0.1:listen_port is already taken in this network namespace.
    def start
      @servers = [TCPServer.new("127.0.0.1", @listen_port)]
      begin
        @servers << TCPServer.new("::1", @listen_port)
      rescue Errno::EADDRINUSE, Errno::EAFNOSUPPORT, Errno::EADDRNOTAVAIL, SocketError
        nil # IPv4 is enough when IPv6 loopback is missing or already taken
      end
      @accept_threads = @servers.map do |server|
        thread = Thread.new { accept_loop(server) }
        thread.abort_on_exception = true # a dead listener should restart the sidecar; a dead relay must not
        thread
      end
      self
    end

    # Closes the listeners and any in-flight connections.
    def stop
      @servers.each { |server| close_quietly(server) }
      @open_sockets_mutex.synchronize { @open_sockets.each { |socket| close_quietly(socket) } }
      @accept_threads.each { |thread| thread.join(1) }
    end

    private

    def accept_loop(server)
      loop do
        client = server.accept
        Thread.new { relay(client) }
      end
    rescue IOError, SystemCallError
      nil # the listener was closed by #stop
    end

    def relay(client)
      upstream = Socket.tcp(@target_host, @target_port, connect_timeout: CONNECT_TIMEOUT_SECONDS)
      track(client, upstream)
      Thread.new { copy_then_signal_end(client, upstream) }
      copy_then_signal_end(upstream, client)
    rescue IOError, SocketError, SystemCallError
      nil
    ensure
      untrack(client, upstream)
      close_quietly(client)
      close_quietly(upstream)
    end

    # Copies until source hits EOF, then half-closes destination so its peer sees that EOF too.
    def copy_then_signal_end(source, destination)
      IO.copy_stream(source, destination)
      destination.close_write
    rescue IOError, SystemCallError
      nil
    end

    def track(*sockets)
      @open_sockets_mutex.synchronize { @open_sockets.concat(sockets) }
    end

    def untrack(*sockets)
      @open_sockets_mutex.synchronize { @open_sockets -= sockets }
    end

    def close_quietly(socket)
      socket&.close
    rescue IOError, SystemCallError
      nil
    end
  end
end
