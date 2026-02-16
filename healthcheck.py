#!/usr/bin/env python3

import logging
import os
import socket
import subprocess

logger = logging.getLogger("healthcheck")


def error(message, exception=None):
    logger.error(message)
    if exception is None:
        raise SystemExit(1)
    raise exception


def http_healthcheck():
    """Use pycurl to check if the target server is still responding via proxy."""
    import re

    import pycurl

    check_url = os.environ.get("HTTP_HEALTHCHECK_URL", "http://$TARGET/")
    check_timeout_ms = int(os.environ.get("HTTP_HEALTHCHECK_TIMEOUT_MS", 2000))
    target = os.environ.get("TARGET", "localhost")
    check_url_with_target = check_url.replace("$TARGET", target)

    port = re.search(r"https?://[^:]*(?::([^/]+))?", check_url_with_target)[1]
    if not port:
        port = "80" if check_url_with_target.startswith("http://") else "443"
        ports = os.environ.get("PORT", "80 443").split()
        if port not in ports and "*" not in ports:
            port = ports[0]
            check_url_with_target = re.sub(
                r"(https?://[^/]+)", rf"\1:{port}", check_url_with_target
            )

    logger.info("checking %s via 127.0.0.1:%s", target, port)
    try:
        request = pycurl.Curl()
        request.setopt(pycurl.URL, check_url_with_target)
        # Route target:port to loopback so iptables OUTPUT (-o lo) REDIRECT applies.
        request.setopt(pycurl.RESOLVE, [f"{target}:{port}:127.0.0.1"])
        request.setopt(pycurl.CONNECTTIMEOUT_MS, check_timeout_ms)
        request.setopt(pycurl.TIMEOUT_MS, check_timeout_ms)
        request.perform()
        request.close()
    except pycurl.error as e:
        error("error while checking http connection", e)


def smtp_healthcheck():
    """Use pycurl to check if the target server is still responding via proxy."""
    import re

    import pycurl

    check_url = os.environ.get("SMTP_HEALTHCHECK_URL", "smtp://$TARGET/")
    check_command = os.environ.get("SMTP_HEALTHCHECK_COMMAND", "HELP")
    check_timeout_ms = int(os.environ.get("SMTP_HEALTHCHECK_TIMEOUT_MS", 2000))
    target = os.environ.get("TARGET", "localhost")
    check_url_with_target = check_url.replace("$TARGET", target)

    port = re.search(r"smtp://[^:]*(?::([^/]+))?", check_url_with_target)[1]
    if not port:
        port = "25"
        ports = os.environ.get("PORT", "25").split()
        if port not in ports and "*" not in ports:
            port = ports[0]
            check_url_with_target = re.sub(
                r"(smtp://[^/]+)", rf"\1:{port}", check_url_with_target
            )

    logger.info("checking %s via 127.0.0.1:%s", target, port)
    try:
        request = pycurl.Curl()
        request.setopt(pycurl.URL, check_url_with_target)
        request.setopt(pycurl.CUSTOMREQUEST, check_command)
        request.setopt(pycurl.RESOLVE, [f"{target}:{port}:127.0.0.1"])
        request.setopt(pycurl.CONNECTTIMEOUT_MS, check_timeout_ms)
        request.setopt(pycurl.TIMEOUT_MS, check_timeout_ms)
        request.perform()
        request.close()
    except pycurl.error as e:
        error("error while checking smtp connection", e)


def process_healthcheck():
    """Check proxy process and iptables rules exist."""
    listen_port = int(os.environ.get("LISTEN_PORT", "15000"))
    try:
        with socket.create_connection(("127.0.0.1", listen_port), timeout=1.0):
            pass
    except OSError as e:
        error(f"proxy is not listening on 127.0.0.1:{listen_port}", e)
    try:
        subprocess.check_output(["iptables", "-t", "nat", "-S", "WHITELIST_REDIRECT"])
    except Exception as e:
        error(
            "missing iptables nat chain WHITELIST_REDIRECT (CAP_NET_ADMIN required?)", e
        )


def preresolve_healthcheck():
    """If PRE_RESOLVE=1, ensure TARGET resolves via configured NAMESERVERS."""
    if os.environ.get("PRE_RESOLVE", "0") in {"0", "", "false", "False"}:
        return
    from dns.resolver import Resolver

    target = os.environ.get("TARGET", "")
    if not target:
        error("TARGET is empty")

    r = Resolver()
    r.nameservers = os.environ.get("NAMESERVERS", "8.8.8.8").split()
    try:
        answers = r.resolve(target)
        ips = [a.address for a in answers]
        if not ips:
            error(f"{target} resolved to empty set")
    except Exception as e:
        error(f"failed to resolve {target} with NAMESERVERS", e)


def main():
    logging.basicConfig(level=logging.INFO)

    if os.environ.get("HTTP_HEALTHCHECK", "0") == "1":
        http_healthcheck()
    elif os.environ.get("SMTP_HEALTHCHECK", "0") == "1":
        smtp_healthcheck()
    else:
        process_healthcheck()
        preresolve_healthcheck()

    print("OK")


if __name__ == "__main__":
    main()
