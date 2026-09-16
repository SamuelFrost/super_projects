# frozen_string_literal: true

require "socket"

module LocalhostForwardProxy
  # Listen on 127.0.0.1:listen_port and copy bytes to target_host:target_port.
  class TcpProxy
    attr_reader :listen_port, :target_host, :target_port, :identity

    def initialize(listen_port:, target_host:, target_port:, identity:)
      @listen_port = listen_port
      @target_host = target_host
      @target_port = target_port
      @identity = identity
      @open_sockets = []
      @sockets_mutex = Mutex.new
    end

    def start
      @server = Socket.new(Socket::AF_INET, Socket::SOCK_STREAM)
      @server.setsockopt(Socket::SOL_SOCKET, Socket::SO_REUSEADDR, 1)
      @server.bind(Addrinfo.tcp("127.0.0.1", @listen_port))
      @server.listen(128)
      @connection_threads = ThreadGroup.new
      @accept_thread = Thread.new { accept_loop }
      @accept_thread.abort_on_exception = true
      self
    end

    def stop
      close_quietly(@server)
      sockets = @sockets_mutex.synchronize do
        taken = @open_sockets.dup
        @open_sockets.clear
        taken
      end
      sockets.each { |socket| close_socket(socket) }
      @connection_threads&.list&.each { |thread| thread.join(1) }
      @accept_thread&.join(1)
    end

    def alive?
      @accept_thread&.alive? && @server && !@server.closed?
    end

    private

    def accept_loop
      loop do
        client, _addr = @server.accept
        remember_socket(client)
        @connection_threads.add(Thread.new { handle(client) })
      end
    rescue IOError, Errno::EBADF, Errno::EINVAL
      nil
    end

    def handle(client)
      upstream = nil
      upstream = Socket.tcp(@target_host, @target_port, connect_timeout: 10)
      remember_socket(upstream)
      to_upstream = Thread.new { copy(client, upstream) }
      copy(upstream, client)
      to_upstream.join
    rescue Errno::ECONNREFUSED, Errno::EHOSTUNREACH, Errno::ETIMEDOUT, SocketError, IOError
      nil
    ensure
      close_quietly(client)
      close_quietly(upstream)
    end

    def copy(src, dst)
      IO.copy_stream(src, dst)
    rescue IOError, Errno::EPIPE, Errno::ECONNRESET, Errno::ECONNABORTED, Errno::ENOTCONN
      nil
    end

    def remember_socket(socket)
      @sockets_mutex.synchronize { @open_sockets << socket }
    end

    def close_quietly(socket)
      return if socket.nil?

      @sockets_mutex.synchronize { @open_sockets.delete(socket) }
      close_socket(socket)
    end

    def close_socket(socket)
      socket.close
    rescue IOError
      nil
    end
  end
end
