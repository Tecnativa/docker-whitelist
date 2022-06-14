#!/usr/bin/env python3

import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("healthcheck")


def error(message, exception=None):
    logger.error(message)
    if exception is None:
        exit(1)
    else:
        raise exception


def http_healthcheck():
    """
    Use pycurl to check if the target server is still responding via proxy.py
    :return: None
    """
    import re

    import pycurl

    check_url = os.environ.get("HTTP_HEALTHCHECK_URL", "http://localhost/")
    check_timeout_ms = int(os.environ.get("HTTP_HEALTHCHECK_TIMEOUT_MS", 2000))
    target = os.environ.get("TARGET", "localhost")
    check_url_with_target = check_url.replace("$TARGET", target)
    port = re.search("https?://[^:]*(?::([^/]+))?", check_url_with_target)[1] or "80"
    print("checking %s via 127.0.0.1" % check_url_with_target)
    logger.info("checking %s via 127.0.0.1" % check_url_with_target)
    try:
        request = pycurl.Curl()
        request.setopt(pycurl.URL, check_url_with_target)
        # do not send the request to the target directly but use our own socat proxy process to check if it's still
        # working
        request.setopt(pycurl.RESOLVE, ["{}:{}:127.0.0.1".format(target, port)])
        request.setopt(pycurl.CONNECTTIMEOUT_MS, check_timeout_ms)
        request.setopt(pycurl.TIMEOUT_MS, check_timeout_ms)
        request.perform()
        request.close()
    except pycurl.error as e:
        error("error while checking http connection", e)


def smtp_healthcheck():
    """
    Use pycurl to check if the target server is still responding via proxy.py
    :return: None
    """
    import re

    import pycurl

    check_url = os.environ.get("SMTP_HEALTHCHECK_URL", "smtp://localhost/")
    check_command = os.environ.get("SMTP_HEALTHCHECK_COMMAND", "HELP")
    check_timeout_ms = int(os.environ.get("SMTP_HEALTHCHECK_TIMEOUT_MS", 2000))
    target = os.environ.get("TARGET", "localhost")
    check_url_with_target = check_url.replace("$TARGET", target)
    port = re.search("smtp://[^:]*(?::([^/]+))?", check_url_with_target)[1] or "25"
    logger.info("checking %s via 127.0.0.1" % check_url_with_target)
    try:
        request = pycurl.Curl()
        request.setopt(pycurl.URL, check_url_with_target)
        request.setopt(pycurl.CUSTOMREQUEST, check_command)
        # do not send the request to the target directly but use our own socat proxy process to check if it's still
        # working
        request.setopt(pycurl.RESOLVE, ["{}:{}:127.0.0.1".format(target, port)])
        request.setopt(pycurl.CONNECTTIMEOUT_MS, check_timeout_ms)
        request.setopt(pycurl.TIMEOUT_MS, check_timeout_ms)
        request.perform()
        request.close()
    except pycurl.error as e:
        error("error while checking smtp connection", e)


def process_healthcheck():
    """
    Check that at least one socat process exists per port and no more than the number of configured max connections
    processes exist for each port.
    :return:
    """
    import subprocess

    ports = os.environ["PORT"].split()
    max_connections = int(os.environ["MAX_CONNECTIONS"])
    logger.info(
        "checking socat processes for port(s) %s having at least one and less than %d socat processes"
        % (ports, max_connections)
    )
    socat_processes = (
        subprocess.check_output(["sh", "-c", "grep -R socat /proc/[0-9]*/cmdline"])
        .decode("utf-8")
        .split("\n")
    )
    pids = [process.split("/")[2] for process in socat_processes if process]
    if len(pids) < len(ports):
        # if we have less than the number of ports socat processes we do not need to count processes per port and can
        # fail fast
        error("Expected at least %d socat processes" % len(ports))
    port_process_count = {port: 0 for port in ports}
    for pid in pids:
        # foreach socat pid we detect the port it's for by checking the last argument (connect to) that ends with
        # :{ip}:{port} for our processes
        try:
            with open("/proc/%d/cmdline" % int(pid)) as fp:
                # arguments in /proc/.../cmdline are split by null bytes
                cmd = [part for part in "".join(fp.readlines()).split("\x00") if part]
                port = cmd[2].split(":")[-1]
                port_process_count[port] = port_process_count[port] + 1
        except FileNotFoundError:
            # ignore processes no longer existing (possibly retrieved an answer)
            pass
    for port in ports:
        if port_process_count[port] == 0:
            error("Missing socat process(es) for port: %s" % port)
        if port_process_count[port] >= max_connections + 1:
            error(
                "More than %d + 1  socat process(es) for port: %s"
                % (max_connections, port)
            )


def preresolve_healthcheck():
    """
    Check that the pre-resolved ip is still valid now for target
    :return:
    """
    from tempfile import gettempdir

    load_balancing_dns_fs_flag = os.path.join(
        gettempdir(), "load_balancing_dns_detected"
    )
    if not os.path.exists(load_balancing_dns_fs_flag):
        # only run the resolver check if a previous run didn't flag the target as being dns load-balanced
        import subprocess

        from dns.resolver import Resolver

        pre_resolved_ips = {
            line.split(":")[2]
            for line in subprocess.check_output(
                ["sh", "-c", "grep -R '\\(udp\\|tcp\\)-connect:' /proc/[0-9]*/cmdline"]
            )
            .decode("utf-8")
            .split("\n")
            if line
        }
        resolver = Resolver()
        resolver.nameservers = os.environ["NAMESERVERS"].split()
        target = os.environ["TARGET"]
        resolved_ips = [answer.address for answer in resolver.resolve(target)]
        for ip in pre_resolved_ips:
            logger.info(f"checking {target} resolves to {ip}")
            if ip not in resolved_ips:
                resolved_ips_2 = [answer.address for answer in resolver.resolve(target)]
                if resolved_ips_2 == resolved_ips:
                    error(
                        f"{target} no longer resolves to {ip}, {resolved_ips}, {resolved_ips_2}"
                    )
                else:
                    resolved_ips_3 = [
                        answer.address for answer in resolver.resolve(target)
                    ]
                    # to make sure we didn't just hit the server switch in dns, we check again before deactivating
                    # the healthcheck permanently (until the container restarts)
                    if resolved_ips_3 != resolved_ips_2:
                        logger.info(
                            f"{target} seems to be load-balancing with dns ({resolved_ips} != {resolved_ips_2}), "
                            f"deactivating the resolver healthcheck"
                        )
                        with open(f"{load_balancing_dns_fs_flag}", "w") as fp:
                            fp.write(target)


process_healthcheck()
if os.environ["PRE_RESOLVE"] == "1":
    preresolve_healthcheck()
if os.environ.get("HTTP_HEALTHCHECK", "0") == "1":
    http_healthcheck()
if os.environ.get("SMTP_HEALTHCHECK", "0") == "1":
    smtp_healthcheck()
