#!/usr/bin/env python3

import os
import random
import logging

from dns.resolver import Resolver

logging.root.setLevel(logging.INFO)

port = os.environ["PORT"]
ip = target = os.environ["TARGET"]

# Resolve target if required
if os.environ["PRE_RESOLVE"] == "1":
    resolver = Resolver()
    resolver.nameservers = os.environ["NAMESERVERS"].split()
    ip = random.choice([answer.address for answer in resolver.query(target)])
    logging.info("Resolved %s to %s", target, ip)

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

logging.info("Executing: %s", " ".join(command))
os.execvp(command[0], command)
