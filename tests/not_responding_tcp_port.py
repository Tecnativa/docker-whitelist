#!/usr/bin/env python3
"""
this is a server that accepts TCP connections but doesn't send any response. it just closes the connection after an hour
has passed. this is intended for testing timeouts only.
"""
import errno
import signal
import socket
import sys
import time


def keep_client_waiting(server_socket):
    client, address = server_socket.accept()
    print("connected", flush=True)
    server_socket.setblocking(0)
    time.sleep(3600)
    print("waited for an hour", flush=True)
    server_socket.close()


def start_server():
    listen_address = sys.argv[1] if len(sys.argv) > 1 else ""
    listen_port = int(sys.argv[2]) if len(sys.argv) > 2 else 80
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((listen_address, listen_port))
    server_socket.listen()
    print("listening", flush=True)

    def shutdown_on_interrupt(signum, frame):
        stop_server(server_socket)

    signal.signal(signal.SIGINT, shutdown_on_interrupt)
    signal.signal(signal.SIGTERM, shutdown_on_interrupt)
    try:
        keep_client_waiting(server_socket)
    except OSError as e:
        if e.errno == errno.EBADF:
            print("stopped", flush=True)
        else:
            raise


def stop_server(server_socket):
    print("stopping...", flush=True)
    server_socket.close()


if __name__ == "__main__":
    start_server()
