import hashlib
import json
import logging
import os.path
from datetime import datetime
from time import sleep

import plumbum.commands.processes
import pytest
from plumbum import TF, local
from plumbum.cmd import docker, which

HEALTHCHECK_YAML = os.path.abspath("tests/healthcheck.yaml")

PROXY_TARGET_PAIRS = [
    ("proxy_preresolve", "target"),
    ("proxy_smtp", "target_smtp"),
    ("proxy_without_preresolve", "target"),
]

logger = logging.getLogger()

# use docker compose plugin/v2
docker_compose = docker["compose"]
_healthcheck = docker_compose["-f", HEALTHCHECK_YAML]
_get_container_id = _healthcheck["ps", "-q"]


def _get_container_id_and_ip(service_name):
    container_id = _get_container_id(service_name).strip()
    container_info = json.loads(docker("inspect", container_id))
    return (
        container_id,
        container_info[0]["NetworkSettings"]["Networks"][
            "%s_simulated_outside" % local.env["COMPOSE_PROJECT_NAME"]
        ]["IPAddress"],
    )


def _new_ip(target):
    # we get the container id of the currently running target to be able to force changing ips by scaling up
    # and then stopping the old container
    old_container_id, old_ip = _get_container_id_and_ip(target)

    # start a second instance of the target
    _healthcheck_with_error_info("up", "-d", "--scale", "%s=2" % target, target)

    # stop and remove the old container
    docker("stop", old_container_id)
    docker("rm", old_container_id)

    # verify that we got a new ip (should not be able to reuse the old one)
    new_container_id, new_ip = _get_container_id_and_ip(target)
    assert old_container_id != new_container_id
    assert old_ip != new_ip


def _healthcheck_with_error_info(*args, **kwargs):
    try:
        _healthcheck(*args, **kwargs)
    except BaseException:
        # add additional infos to any error to make tracing down the error easier
        logger.error(_healthcheck("logs", "autoheal"))
        logger.error(_healthcheck("ps"))
        raise


def _wait_for(proxy, messages, callback, *args):
    try:
        if isinstance(messages, str):

            def missing_messages(result):
                return messages not in result

            messages_for_exception = messages
        else:

            def missing_messages(result):
                return any(message for message in messages if message not in result)

            messages_for_exception = ", ".join(messages)
        while missing_messages(callback(*args)):
            # try again in one second (to not hammer the CPU)
            sleep(1)
    except BaseException:
        # add additional infos to any error to make tracing down the error easier
        logger.error("failed waiting for '%s'" % messages_for_exception)
        logger.error(_healthcheck("logs", "autoheal"))
        logger.error(_healthcheck("ps"))
        logger.error(_healthcheck("exec", "-T", proxy, "healthcheck", retcode=None))
        raise


def _sha256(text):
    return hashlib.sha256(str(text).encode("utf-8")).hexdigest()


@pytest.fixture(scope="session")
def os_needs_privileges():
    if which["getenforce"] & TF:
        # if we can find getenforce on the current system, SELinux is probably installed and we need to start
        # autoheal with privileges
        return "true"
    return "false"


@pytest.fixture(scope="function", autouse=True)
def _cleanup_docker_compose(tmp_path, os_needs_privileges):
    with local.cwd(tmp_path):
        custom_compose_project_name = "{}_{}".format(
            os.path.basename(tmp_path), _sha256(tmp_path)[:6]
        )
        with local.env(
            COMPOSE_PROJECT_NAME=custom_compose_project_name,
            OS_NEEDS_PRIVILEGES_FOR_DOCKER_SOCK=os_needs_privileges,
        ) as env:
            yield env

            # stop autoheal first to prevent it from restarting containers to be stopped
            _healthcheck("stop", "autoheal")
            _healthcheck("down", "-v")


@pytest.fixture(scope="session", autouse=True)
def _pull_images():
    start = datetime.now()
    _healthcheck_with_error_info("pull", "--ignore-buildable")
    logger.info("pulled images {}".format(datetime.now() - start))


@pytest.mark.parametrize("proxy,target", PROXY_TARGET_PAIRS)
def test_healthcheck_ok(proxy, target):
    # given a started proxy with healthcheck
    _healthcheck("up", "-d", proxy)

    # when everything is ok and target is Up
    assert " Up " in _healthcheck("ps", target)

    # then healthcheck should be successful
    _healthcheck("exec", "-T", proxy, "healthcheck")


@pytest.mark.parametrize("proxy,target", PROXY_TARGET_PAIRS)
def test_healthcheck_failing(proxy, target):
    # given a started proxy with healthcheck
    _healthcheck("up", "-d", proxy)
    # and autoheal not interfering
    _healthcheck("stop", "autoheal")

    # when target is not reachable
    _healthcheck("stop", target)
    assert " Exited " in _healthcheck("ps", "--all", target)

    # then healthcheck should return an error (non zero exit code)
    with pytest.raises(
        plumbum.commands.processes.ProcessExecutionError,
        match=r"Unexpected exit code: (1|137)",
    ):
        _healthcheck("exec", "-T", proxy, "healthcheck")


@pytest.mark.parametrize("proxy,target", PROXY_TARGET_PAIRS)
@pytest.mark.timeout(30)
def test_healthcheck_failing_firewalled(proxy, target):
    # given a started proxy with healthcheck
    _healthcheck_with_error_info("up", "-d", proxy)
    # and autoheal not interfering
    _healthcheck_with_error_info("stop", "autoheal")

    # when target stops responding
    _healthcheck_with_error_info("stop", target)
    assert " Exited " in _healthcheck("ps", "--all", target)
    _healthcheck_with_error_info(
        "up", "-d", "{target:s}_firewalled_not_responding".format(target=target)
    )
    assert "Up" in _healthcheck(
        "ps", "{target:s}_firewalled_not_responding".format(target=target)
    )

    # then healthcheck should return an error (non-zero exit code)
    with pytest.raises(
        plumbum.commands.processes.ProcessExecutionError,
        match=r"Unexpected exit code: (1|137)",
    ):
        start = datetime.now()
        _healthcheck_with_error_info("exec", "-T", proxy, "healthcheck")
    end = datetime.now()
    # timeout is set to 200ms for tests, so the exception should be raised at earliest after 0.2s
    # and at most 2s after starting considering overhead
    # if it happens outside that timeframe (especially before 0.2s) the exception might hint to another error type
    assert 0.2 < (end - start).total_seconds() < 2


@pytest.mark.parametrize(
    "proxy,target",
    (p for p in PROXY_TARGET_PAIRS if p[0] != "proxy_without_preresolve"),
)
@pytest.mark.timeout(60)
def test_healthcheck_autoheal(proxy, target):
    # given a started proxy with healthcheck
    _healthcheck_with_error_info("up", "-d", proxy)
    proxy_container_id = _get_container_id(proxy).strip()
    # that was healthy
    _wait_for(proxy, (" Up ", " (healthy) "), _healthcheck, "ps", proxy)

    # when target gets a new ip
    _new_ip(target)

    # then autoheal should restart the proxy
    _wait_for(
        proxy,
        "(%s) found to be unhealthy - Restarting container now"
        % proxy_container_id[:12],
        _healthcheck,
        "logs",
        "autoheal",
    )

    # and the proxy should become healthy
    _wait_for(proxy, (" Up ", " (healthy) "), _healthcheck, "ps", proxy)

    # and healthcheck should be successful
    _healthcheck_with_error_info("exec", "-T", proxy, "healthcheck")


@pytest.mark.timeout(60)
def test_healthcheck_autoheal_proxy_without_preresolve():
    # given a started proxy with healthcheck
    proxy = "proxy_without_preresolve"
    _healthcheck_with_error_info("up", "-d", proxy)
    # that was healthy
    _wait_for(proxy, (" Up ", " (healthy) "), _healthcheck, "ps", proxy)

    # when target gets a new ip
    _new_ip("target")

    # then healthcheck should be always successful (we wait just for 5 seconds)
    for _ in range(0, 50):
        _healthcheck_with_error_info("exec", "-T", proxy, "healthcheck")
        sleep(0.1)

    # and autoheal shouldn't have restarted anything
    assert not [
        line
        for line in _healthcheck("logs", "autoheal").split("\n")
        if line and not line.startswith("Attaching to ") and "AUTOHEAL_" not in line
    ]
