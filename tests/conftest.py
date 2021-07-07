import logging
from contextlib import contextmanager
from pathlib import Path

import pytest
from plumbum import local
from plumbum.cmd import docker

_logger = logging.getLogger(__name__)


def pytest_addoption(parser):
    """Allow prebuilding image for local testing."""
    parser.addoption(
        "--prebuild", action="store_true", help="Build local image before testing"
    )
    parser.addoption(
        "--image",
        action="store",
        default="test:docker-whitelist",
        help="Specify testing image name",
    )


@pytest.fixture(scope="session")
def image(request):
    """Get image name. Builds it if needed."""
    image = request.config.getoption("--image")
    if request.config.getoption("--prebuild"):
        build = docker["image", "build", "-t", image, Path(__file__).parent.parent]
        retcode, stdout, stderr = build.run()
        _logger.log(
            # Pytest prints warnings if a test fails, so this is a warning if
            # the build succeeded, to allow debugging the build logs
            logging.ERROR if retcode else logging.WARNING,
            "Build logs for COMMAND: %s\nEXIT CODE:%d\nSTDOUT:%s\nSTDERR:%s",
            build.bound_command(),
            retcode,
            stdout,
            stderr,
        )
        assert not retcode, "Image build failed"
    return image


@pytest.fixture(scope="session")
def container_factory(image):
    """A context manager that starts the docker container."""

    @contextmanager
    def _container(target):
        container_id = None
        _logger.info(f"Starting {image} container")
        try:
            container_id = docker(
                "container",
                "run",
                "--detach",
                "-e",
                "TARGET=%s" % target,
                image,
            ).strip()
            with local.env():
                yield container_id
        finally:
            if container_id:
                _logger.info(f"Removing {container_id}...")
                docker(
                    "container",
                    "rm",
                    "-f",
                    container_id,
                )

    return _container
