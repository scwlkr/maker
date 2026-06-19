from __future__ import annotations

import socket

import pytest

from tools import BlockedTarget, assert_public_http_url, fetch_public_url


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost/",
        "http://127.0.0.1/",
        "http://10.0.0.1/",
        "http://172.16.0.1/",
        "http://192.168.1.1/",
        "http://169.254.169.254/latest/meta-data/",
        "ftp://example.com/file",
    ],
)
def test_controller_fetch_blocks_local_private_and_metadata(url: str) -> None:
    with pytest.raises(BlockedTarget):
        assert_public_http_url(url)


def test_public_fetch_works() -> None:
    try:
        result = fetch_public_url("https://example.com", timeout=10, max_chars=4000)
    except (OSError, socket.gaierror) as exc:
        pytest.skip(f"public network unavailable: {exc}")
    assert result["status"] == 200
    assert "Example Domain" in result["text"]["preview"]
