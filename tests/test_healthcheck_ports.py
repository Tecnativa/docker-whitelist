import os
from unittest import TestCase
from unittest.mock import call, patch

import pycurl

from healthcheck import http_healthcheck, smtp_healthcheck


@patch("pycurl.Curl")
class TestHealthcheckPorts(TestCase):
    # given default environment
    @patch.dict(os.environ, {"PORT": "80 443"}, clear=True)
    def test_healthcheck_http_default_port(self, mock_curl):
        # when running http_healthcheck
        http_healthcheck()

        # then the called url should be http://localhost/
        mock_curl.assert_has_calls(
            [
                call().setopt(pycurl.URL, "http://localhost/"),
                # and port 80 should be used
                call().setopt(pycurl.RESOLVE, ["localhost:80:127.0.0.1"]),
            ]
        )

    # given default environment with https url specified
    @patch.dict(
        os.environ,
        {"PORT": "80 443", "HTTP_HEALTHCHECK_URL": "https://localhost/"},
        clear=True,
    )
    def test_healthcheck_https_default_port(self, mock_curl):
        # when running http_healthcheck
        http_healthcheck()

        # then the called url should be https://localhost/
        mock_curl.assert_has_calls(
            [
                call().setopt(pycurl.URL, "https://localhost/"),
                # and port 443 should be used
                call().setopt(pycurl.RESOLVE, ["localhost:443:127.0.0.1"]),
            ]
        )

    # given special http port
    @patch.dict(os.environ, {"PORT": "8025"}, clear=True)
    def test_healthcheck_http_custom_port(self, mock_curl):
        # when running http_healthcheck
        http_healthcheck()

        # then the called url should be http://localhost:8025/
        mock_curl.assert_has_calls(
            [
                call().setopt(pycurl.URL, "http://localhost:8025/"),
                # and port 8025 should be used
                call().setopt(pycurl.RESOLVE, ["localhost:8025:127.0.0.1"]),
            ]
        )

    # given smtp environment
    @patch.dict(os.environ, {"PORT": "25"}, clear=True)
    def test_healthcheck_smtp_default_port(self, mock_curl):
        # when running smtp_healthcheck
        smtp_healthcheck()

        # then the called url should be smtp://localhost/
        mock_curl.assert_has_calls(
            [
                call().setopt(pycurl.URL, "smtp://localhost/"),
                # and command should be HELP
                call().setopt(pycurl.CUSTOMREQUEST, "HELP"),
                # and port 25 should be used
                call().setopt(pycurl.RESOLVE, ["localhost:25:127.0.0.1"]),
            ]
        )

    # given mailhog smtp environment
    @patch.dict(
        os.environ,
        {
            "PORT": "1025",
            "TARGET": "mailhog",
            "SMTP_HEALTHCHECK_URL": "smtp://$TARGET/",
            "SMTP_HEALTHCHECK_COMMAND": "QUIT",
        },
        clear=True,
    )
    def test_healthcheck_smtp_mailhog_port(self, mock_curl):
        # when running smtp_healthcheck
        smtp_healthcheck()

        # then the called url should be smtp://mailhog:1025/
        mock_curl.assert_has_calls(
            [
                call().setopt(pycurl.URL, "smtp://mailhog:1025/"),
                # and command should be QUIT
                call().setopt(pycurl.CUSTOMREQUEST, "QUIT"),
                # and port 1025 should be used
                call().setopt(pycurl.RESOLVE, ["mailhog:1025:127.0.0.1"]),
            ]
        )

    # given mailhog multiple ports environment
    @patch.dict(
        os.environ,
        {
            "PORT": "10001 10002",
            "TARGET": "mailhog",
            "SMTP_HEALTHCHECK_URL": "smtp://$TARGET/",
            "SMTP_HEALTHCHECK_COMMAND": "QUIT",
        },
        clear=True,
    )
    def test_healthcheck_smtp_mailhog_multiple_ports(self, mock_curl):
        # when running smtp_healthcheck
        smtp_healthcheck()

        # then the called url should be smtp://mailhog:10001/
        mock_curl.assert_has_calls(
            [
                call().setopt(pycurl.URL, "smtp://mailhog:10001/"),
                # and command should be QUIT
                call().setopt(pycurl.CUSTOMREQUEST, "QUIT"),
                # and port 10001 should be used
                call().setopt(pycurl.RESOLVE, ["mailhog:10001:127.0.0.1"]),
            ]
        )

    # given mailhog multiple ports environment
    @patch.dict(
        os.environ,
        {
            "PORT": "10001 10002",
            "TARGET": "mailhog",
            "SMTP_HEALTHCHECK_URL": "smtp://$TARGET:10002/",
            "SMTP_HEALTHCHECK_COMMAND": "QUIT",
        },
        clear=True,
    )
    def test_healthcheck_smtp_mailhog_custom_port_in_url(self, mock_curl):
        # when running smtp_healthcheck
        smtp_healthcheck()

        # then the called url should be smtp://mailhog:10002/
        mock_curl.assert_has_calls(
            [
                call().setopt(pycurl.URL, "smtp://mailhog:10002/"),
                # and command should be QUIT
                call().setopt(pycurl.CUSTOMREQUEST, "QUIT"),
                # and port 10001 should be used
                call().setopt(pycurl.RESOLVE, ["mailhog:10002:127.0.0.1"]),
            ]
        )
