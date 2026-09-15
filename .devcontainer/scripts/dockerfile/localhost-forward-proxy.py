#!/usr/bin/env python3
"""TCP proxy: listen on 127.0.0.1:listen_port and forward to target_host:target_port."""
from __future__ import annotations

import socket
import sys
import threading


def pipe(src: socket.socket, dst: socket.socket) -> None:
    try:
        while True:
            data = src.recv(65536)
            if not data:
                break
            dst.sendall(data)
    except OSError:
        pass
    finally:
        try:
            dst.shutdown(socket.SHUT_WR)
        except OSError:
            pass
        try:
            src.shutdown(socket.SHUT_RD)
        except OSError:
            pass


def handle(client: socket.socket, target_host: str, target_port: int) -> None:
    try:
        upstream = socket.create_connection((target_host, target_port), timeout=10)
        upstream.settimeout(None)
    except OSError:
        client.close()
        return
    threading.Thread(target=pipe, args=(client, upstream), daemon=True).start()
    pipe(upstream, client)
    client.close()
    upstream.close()


def main() -> None:
    if len(sys.argv) != 4:
        print("usage: localhost-forward-proxy.py LISTEN_PORT TARGET_HOST TARGET_PORT", file=sys.stderr)
        sys.exit(2)
    listen_port = int(sys.argv[1])
    target_host = sys.argv[2]
    target_port = int(sys.argv[3])
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", listen_port))
    server.listen(128)
    while True:
        client, _ = server.accept()
        threading.Thread(
            target=handle, args=(client, target_host, target_port), daemon=True
        ).start()


if __name__ == "__main__":
    main()
