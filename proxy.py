#!/usr/bin/env python3

import asyncio
import logging
import os
import random

from dns.resolver import Resolver

logging.root.setLevel(logging.INFO)
ports = os.environ["PORT"].split()
ip = target = os.environ["TARGET"]

# Resolve target if required
if os.environ["PRE_RESOLVE"] == "1":
    resolver = Resolver()
    resolver.nameservers = os.environ["NAMESERVERS"].split()
    ip = random.choice([answer.address for answer in resolver.query(target)])
    logging.info("Resolved %s to %s", target, ip)


@asyncio.coroutine
async def netcat(port):
    # Use a persistent BusyBox netcat server in listening mode
    command = ["nc", "-lkp", port]
    # UDP mode
    if os.environ["UDP"] == "1":
        command.append("-u")
    # Verbose mode
    if os.environ["VERBOSE"] == "1":
        command.append("-v")
    # Netcat to target IP when a connection comes in
    command += ["-e", "nc", ip, port]
    # Create the process and wait until it exits
    logging.info("Executing: %s", " ".join(command))
    process = await asyncio.create_subprocess_exec(*command)
    await process.wait()


# Wait until all proxies exited, if they ever do
try:
    loop.run_until_complete(asyncio.gather(*map(netcat, ports)))
finally:
    loop.run_until_complete(loop.shutdown_asyncgens())
    loop.close()
