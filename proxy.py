#!/usr/bin/env python3

import asyncio
import logging
import os
import random
import socket
import struct
import subprocess
from typing import Iterable, List, Optional

from dns.resolver import Resolver

logging.root.setLevel(logging.INFO)
_LOG = logging.getLogger("whitelist")


def _env_bool(name: str, default: bool = False) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except Exception:
        return default


def _expand_ports(port_tokens: Iterable[str]) -> List[int]:
    ports: List[int] = []
    for token in port_tokens:
        token = token.strip()
        if not token:
            continue
        if token == "*":
            ports.append(-1)
            continue
        if "-" in token:
            start_s, end_s = token.split("-", 1)
            start = int(start_s)
            end = int(end_s)
            if end < start:
                raise ValueError(f"Invalid port range: {token}")
            ports.extend(list(range(start, end + 1)))
        else:
            ports.append(int(token))
    return ports


MODE = os.environ.get("MODE", "tcp")
TARGET = os.environ["TARGET"]
PRE_RESOLVE = _env_bool("PRE_RESOLVE", False)
LISTEN_PORT = _env_int("LISTEN_PORT", 15000)
RESOLVE_INTERVAL = _env_int("RESOLVE_INTERVAL", 60)

PORTS = _expand_ports(os.environ.get("PORT", "80 443").split())
ANY_PORT = -1 in PORTS

# Linux constant from linux/netfilter_ipv4.h
_SO_ORIGINAL_DST = 80


class TargetResolver:
    def __init__(self, target: str):
        self.target = target
        self._resolver: Optional[Resolver] = None
        if PRE_RESOLVE:
            r = Resolver()
            r.nameservers = os.environ.get("NAMESERVERS", "8.8.8.8").split()
            self._resolver = r
        self.current_ip: Optional[str] = None

    def resolve_once(self) -> str:
        if not self._resolver:
            # System resolver (may resolve to self if you have Docker aliases)
            return socket.gethostbyname(self.target)
        answers = self._resolver.resolve(self.target)
        ips = [a.address for a in answers]
        if not ips:
            raise RuntimeError(f"No A records for {self.target}")
        return random.choice(ips)

    async def keep_fresh(self) -> None:
        while self.current_ip is None:
            try:
                self.current_ip = self.resolve_once()
                _LOG.info("Resolved %s to %s", self.target, self.current_ip)
            except Exception as e:
                _LOG.warning("DNS resolve failed for %s: %s", self.target, e)
                await asyncio.sleep(2)

        if not PRE_RESOLVE:
            return

        while True:
            await asyncio.sleep(max(1, RESOLVE_INTERVAL))
            try:
                new_ip = self.resolve_once()
                if new_ip != self.current_ip:
                    _LOG.info(
                        "DNS changed for %s: %s -> %s",
                        self.target,
                        self.current_ip,
                        new_ip,
                    )
                    self.current_ip = new_ip
            except Exception as e:
                _LOG.warning("DNS refresh failed for %s: %s", self.target, e)


def _run(cmd: List[str], *, check: bool = True) -> subprocess.CompletedProcess:
    if os.environ.get("VERBOSE", "0") not in {"0", "", "false", "False"}:
        _LOG.info("Executing: %s", " ".join(cmd))
    return subprocess.run(
        cmd,
        check=check,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _iptables_prepare_chain(chain: str) -> None:
    # Create chain if missing; flush it to keep idempotent behaviour on restarts.
    _run(["iptables", "-t", "nat", "-N", chain], check=False)
    _run(["iptables", "-t", "nat", "-F", chain], check=True)

    # Ensure PREROUTING jumps into our chain once (traffic coming from other containers).
    if (
        _run(
            ["iptables", "-t", "nat", "-C", "PREROUTING", "-p", "tcp", "-j", chain],
            check=False,
        ).returncode
        != 0
    ):
        _run(
            ["iptables", "-t", "nat", "-A", "PREROUTING", "-p", "tcp", "-j", chain],
            check=True,
        )

    # Ensure OUTPUT on loopback also jumps into our chain (so in-container healthchecks
    # using 127.0.0.1 benefit from the same REDIRECT rules).
    if (
        _run(
            [
                "iptables",
                "-t",
                "nat",
                "-C",
                "OUTPUT",
                "-o",
                "lo",
                "-p",
                "tcp",
                "-j",
                chain,
            ],
            check=False,
        ).returncode
        != 0
    ):
        _run(
            [
                "iptables",
                "-t",
                "nat",
                "-A",
                "OUTPUT",
                "-o",
                "lo",
                "-p",
                "tcp",
                "-j",
                chain,
            ],
            check=True,
        )


def _setup_iptables_redirect(
    listen_port: int, ports: List[int], any_port: bool
) -> None:
    """Install REDIRECT rules to send selected inbound TCP ports to listen_port."""
    chain = "WHITELIST_REDIRECT"
    _iptables_prepare_chain(chain)

    if any_port:
        # Redirect all TCP ports except the internal listener port (avoid self-loop).
        _run(
            [
                "iptables",
                "-t",
                "nat",
                "-A",
                chain,
                "-p",
                "tcp",
                "!",
                "--dport",
                str(listen_port),
                "-j",
                "REDIRECT",
                "--to-ports",
                str(listen_port),
            ],
            check=True,
        )
        _LOG.info("iptables: redirecting ALL tcp ports -> %s", listen_port)
        return

    # Redirect explicit ports
    for p in ports:
        if p <= 0:
            continue
        if p == listen_port:
            # Avoid redirecting the proxy listener into itself.
            continue
        _run(
            [
                "iptables",
                "-t",
                "nat",
                "-A",
                chain,
                "-p",
                "tcp",
                "--dport",
                str(p),
                "-j",
                "REDIRECT",
                "--to-ports",
                str(listen_port),
            ],
            check=True,
        )
    _LOG.info(
        "iptables: redirecting tcp ports %s -> %s",
        " ".join(str(p) for p in ports if p > 0),
        listen_port,
    )


def _get_original_dst_port(conn: socket.socket) -> int:
    data = conn.getsockopt(socket.SOL_IP, _SO_ORIGINAL_DST, 16)
    _family, port = struct.unpack_from("!HH", data, 0)
    return port


async def _pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while True:
            chunk = await reader.read(65536)
            if not chunk:
                break
            writer.write(chunk)
            await writer.drain()
    except Exception:
        pass
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass


async def _handle_redirected(
    reader: asyncio.StreamReader, writer: asyncio.StreamWriter, resolver: TargetResolver
) -> None:
    sock = writer.get_extra_info("socket")
    if sock is None:
        writer.close()
        return
    if not hasattr(sock, "getsockopt"):
        _LOG.error("No socket/getsockopt available from transport: %r", sock)
        writer.close()
        return

    try:
        dst_port = _get_original_dst_port(sock)
    except Exception as e:
        _LOG.error("Failed to read original destination (SO_ORIGINAL_DST): %s", e)
        writer.close()
        return

    if dst_port == LISTEN_PORT and not ANY_PORT:
        # Someone connected directly to LISTEN_PORT; this is not a public interface.
        writer.close()
        return

    target_ip = resolver.current_ip or TARGET
    try:
        r2, w2 = await asyncio.open_connection(target_ip, dst_port)
    except Exception as e:
        _LOG.info("Connect failed to %s:%s: %s", target_ip, dst_port, e)
        writer.close()
        return

    await asyncio.gather(_pipe(reader, w2), _pipe(r2, writer))


async def _main() -> None:
    if MODE != "tcp":
        raise SystemExit("This image now supports MODE=tcp only (no socat).")

    resolver = TargetResolver(TARGET)
    asyncio.create_task(resolver.keep_fresh())

    try:
        _setup_iptables_redirect(LISTEN_PORT, PORTS, ANY_PORT)
    except Exception as e:
        raise SystemExit(
            "Failed to setup iptables NAT REDIRECT. "
            "You likely need CAP_NET_ADMIN (docker-compose: cap_add: [NET_ADMIN]). "
            f"Original error: {e}"
        )

    server = await asyncio.start_server(
        lambda r, w: _handle_redirected(r, w, resolver),
        host="0.0.0.0",
        port=LISTEN_PORT,
        backlog=1024,
    )
    addrs = ", ".join(str(sock.getsockname()) for sock in server.sockets or [])
    if ANY_PORT:
        _LOG.info(
            "Proxy listening on %s (redirect: ALL tcp ports -> %s)", addrs, LISTEN_PORT
        )
    else:
        _LOG.info(
            "Proxy listening on %s (redirect: %s -> %s)",
            addrs,
            " ".join(str(p) for p in PORTS if p > 0),
            LISTEN_PORT,
        )

    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(_main())
