#!/usr/bin/env python3

import asyncio
import logging
import os
import random

from dns.resolver import Resolver

logging.root.setLevel(logging.INFO)
mode = os.environ["MODE"]
ports = os.environ["PORT"].split()
max_connections = os.environ.get("MAX_CONNECTIONS", 100)
ip = target = os.environ["TARGET"]
udp_answers = os.environ.get("UDP_ANSWERS", "1")

# Resolve target if required
if os.environ["PRE_RESOLVE"] == "1":
    resolver = Resolver()
    resolver.nameservers = os.environ["NAMESERVERS"].split()
    ip = random.choice([answer.address for answer in resolver.query(target)])
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


# Wait until all proxies exited, if they ever do
try:
    loop = asyncio.get_event_loop()
    loop.run_until_complete(asyncio.gather(*map(netcat, ports)))
finally:
    loop.run_until_complete(loop.shutdown_asyncgens())
    loop.close()
