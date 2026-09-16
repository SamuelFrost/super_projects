# frozen_string_literal: true

require "socket"

module LocalhostForwardProxy
  # Accepts connections on 127.0.0.1:listen_port and copies bytes both ways to target_host:target_port.
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

    # Raises Errno::EADDRINUSE when something in the shared network namespace already listens on the port.
    def start
      @server = TCPServer.new("127.0.0.1", @listen_port)
      @accept_thread = Thread.new { accept_loop }
      self
    end

    # Closes the listener and any in-flight connections.
    def stop
      @server.close
      @open_sockets_mutex.synchronize { @open_sockets.each { |socket| close_quietly(socket) } }
      @accept_thread.join(1)
    end

    private

    def accept_loop
      loop do
        client = @server.accept
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
