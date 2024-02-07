#!/usr/bin/env python3
"""
this is a server that accepts TCP connections but doesn't send any response. it just closes the connection after an hour
has passed. this is intended for testing timeouts only.
"""

import socket
import sys
import time


def keep_client_waiting(server_socket):
    client, address = server_socket.accept()
    print("connected")
    server_socket.setblocking(0)
    time.sleep(3600)
    print("waited for an hour")
    server_socket.close()


def start_server():
    listen_address = sys.argv[1] if len(sys.argv) > 1 else ""
    listen_port = int(sys.argv[2]) if len(sys.argv) > 2 else 80
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((listen_address, listen_port))
    server_socket.listen()
    keep_client_waiting(server_socket)


if __name__ == "__main__":
    start_server()
