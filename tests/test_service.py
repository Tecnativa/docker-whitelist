import logging

from plumbum.cmd import docker

logger = logging.getLogger()


def test_containers_start(container_factory):
    with container_factory(target="google.com") as test_container:
        docker(
            "exec",
            test_container,
            "socat",
            "-V",
        )
