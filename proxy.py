#!/usr/bin/env python3

import asyncio
import logging
import os
import random

from dns.resolver import Resolver

logging.root.setLevel(logging.INFO)
mode = os.environ["MODE"]
max_connections = os.environ.get("MAX_CONNECTIONS", 100)
ip = target = os.environ["TARGET"]
udp_answers = os.environ.get("UDP_ANSWERS", "1")


def _expand_ports(port_tokens):
    for token in port_tokens:
        token = token.strip()
        if not token:
            continue
        if "-" in token:
            start, end = token.split("-", 1)
            start = int(start)
            end = int(end)
            if end < start:
                raise ValueError(f"Invalid port range: {token}")
            for p in range(start, end + 1):
                yield str(p)
        else:
            yield token


ports = list(_expand_ports(os.environ["PORT"].split()))

# Resolve target if required
if os.environ.get("PRE_RESOLVE", "0") == "1":
    resolver = Resolver()
    resolver.nameservers = os.environ["NAMESERVERS"].split()
    ip = random.choice([answer.address for answer in resolver.resolve(target)])
    logging.info("Resolved %s to %s", target, ip)


async def netcat(port):
    # Use a persistent BusyBox netcat server in listening mode
    command = ["socat"]
    # Verbose mode
    if os.environ["VERBOSE"] == "1":
        command.append("-v")
    if mode == "udp" and udp_answers == "0":
        command += [f"udp-recv:{port},reuseaddr", f"udp-sendto:{ip}:{port}"]
    else:
        command += [
            f"{mode}-listen:{port},fork,reuseaddr,max-children={max_connections}",
            f"{mode}-connect:{ip}:{port}",
        ]
    # Create the process and wait until it exits
    logging.info("Executing: %s", " ".join(command))
    process = await asyncio.create_subprocess_exec(*command)
    await process.wait()


async def _main():
    # Create tasks within a running event loop (robust on Python 3.10+)
    tasks = [asyncio.create_task(netcat(port)) for port in ports]
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(_main())
