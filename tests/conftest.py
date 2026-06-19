from __future__ import annotations

import subprocess
import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def repo_root() -> Path:
    return ROOT


def docker_available() -> bool:
    try:
        proc = subprocess.run(
            ["docker", "info", "--format", "{{.ServerVersion}}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
    return proc.returncode == 0


@pytest.fixture
def docker_required() -> None:
    if not docker_available():
        pytest.skip("Docker daemon is not available")


@pytest.fixture
def unique_name() -> str:
    return "maker_test_" + uuid.uuid4().hex[:12]
