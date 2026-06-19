from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path


def test_show_wake_and_show_last_scripts(repo_root: Path, tmp_path: Path) -> None:
    maker = tmp_path / "maker-place"
    wakes = maker / "wakes"
    wakes.mkdir(parents=True)
    wake_id = "20260101T000000Z-test"
    (wakes / f"{wake_id}.json").write_text(
        json.dumps(
            {
                "wake_id": wake_id,
                "model": "mock/free:free",
                "start_time": "start",
                "end_time": "end",
                "end_reason": "sleep_or_finish",
                "tool_calls": [{"index": 1, "name": "shell", "arguments": {"command": "true"}}],
                "errors": [],
            }
        )
    )
    env = {**os.environ, "MAKER_PLACE_DIR": str(maker)}
    show = subprocess.run(
        ["bash", "scripts/show-wake.sh", wake_id],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert f"wake: {wake_id}" in show.stdout
    last = subprocess.run(
        ["bash", "scripts/show-last.sh"],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert f"wake: {wake_id}" in last.stdout


def test_watch_script_starts(repo_root: Path, tmp_path: Path) -> None:
    maker = tmp_path / "maker-place"
    maker.mkdir()
    env = {**os.environ, "MAKER_PLACE_DIR": str(maker), "LINES": "1"}
    proc = subprocess.Popen(
        ["bash", "scripts/watch.sh"],
        cwd=repo_root,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        time.sleep(0.3)
        assert proc.poll() is None
        assert (maker / "events.jsonl").exists()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
