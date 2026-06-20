from __future__ import annotations

import os
import subprocess
from pathlib import Path

from controller import Controller, MockModelClient, Settings
from maker_place import MakerPlace
from sandbox import Sandbox, SandboxSettings


def docker_settings(repo_root: Path, unique_name: str) -> SandboxSettings:
    return SandboxSettings(
        image=f"{unique_name}:sandbox",
        world_volume=f"{unique_name}_world",
        shell_timeout_seconds=2,
        tool_output_chars=4000,
        repo_root=repo_root,
    )


def remove_volume(name: str) -> None:
    subprocess.run(["docker", "volume", "rm", "-f", name], capture_output=True, text=True)


def test_sandbox_world_persists_and_can_be_destroyed(
    docker_required: None, repo_root: Path, unique_name: str
) -> None:
    settings = docker_settings(repo_root, unique_name)
    remove_volume(settings.world_volume)
    try:
        first = Sandbox("wake-one", settings)
        first.start()
        result = first.exec_bash("printf hi > keep.txt && mkdir -p tools && printf x > tools/x")
        assert result.exit_code == 0
        first.stop()

        second = Sandbox("wake-two", settings)
        second.start()
        assert second.exec_bash("test -f keep.txt && test -f tools/x").exit_code == 0
        assert second.exec_bash("rm -rf /world/* /world/.[!.]* /world/..?* 2>/dev/null || true").exit_code == 0
        second.stop()

        third = Sandbox("wake-three", settings)
        snapshot = third.world_snapshot()
        assert snapshot == ""
    finally:
        remove_volume(settings.world_volume)


def test_sandbox_does_not_receive_secrets_docker_sock_host_or_maker_place(
    docker_required: None, repo_root: Path, unique_name: str, monkeypatch
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "should-not-enter-sandbox")
    settings = docker_settings(repo_root, unique_name)
    remove_volume(settings.world_volume)
    sandbox = Sandbox("boundary", settings)
    try:
        sandbox.start()
        assert sandbox.exec_bash("! env | grep OPENROUTER_API_KEY").exit_code == 0
        assert sandbox.exec_bash("test ! -S /var/run/docker.sock").exit_code == 0
        assert sandbox.exec_bash("test ! -e /Users && test ! -e /maker-place && test ! -e /app/maker-place").exit_code == 0
        info = sandbox.inspect()
        mounts = info["mounts"]
        assert mounts == [
            {
                "type": "volume",
                "name": settings.world_volume,
                "destination": "/world",
                "source": mounts[0]["source"],
            }
        ]
    finally:
        sandbox.stop()
        remove_volume(settings.world_volume)


def test_shell_timeout(docker_required: None, repo_root: Path, unique_name: str) -> None:
    settings = docker_settings(repo_root, unique_name)
    settings.shell_timeout_seconds = 1
    remove_volume(settings.world_volume)
    sandbox = Sandbox("timeout", settings)
    try:
        sandbox.start()
        result = sandbox.exec_bash("sleep 5")
        assert result.timed_out is True
        assert result.exit_code is None
    finally:
        sandbox.stop()
        remove_volume(settings.world_volume)


def test_controller_run_once_with_mock_model_real_sandbox(
    docker_required: None, repo_root: Path, tmp_path: Path, unique_name: str
) -> None:
    sandbox_settings = docker_settings(repo_root, unique_name)
    remove_volume(sandbox_settings.world_volume)
    settings = Settings(
        model_provider="openrouter",
        openrouter_api_key=None,
        ollama_base_url="http://localhost:11434",
        model="mock/free:free",
        model_fallbacks=[],
        wake_interval_seconds=300,
        context_limit_tokens=120000,
        store_raw_outputs=False,
        model_timeout_seconds=5,
        model_max_tokens=None,
        fetch_timeout_seconds=5,
        text_only_delay_seconds=0,
        max_consecutive_text_only_responses=3,
        max_tool_calls_per_wake=80,
        maker_place_dir=tmp_path / "maker-place",
        sandbox=sandbox_settings,
        mock_model=True,
    )
    try:
        maker = MakerPlace(settings.maker_place_dir)
        summary = Controller(settings, maker_place=maker, model_client=MockModelClient()).run_wake()
        assert summary is not None
        assert summary["end_reason"] == "sleep_or_finish"
        assert len(summary["tool_calls"]) == 2
        inspector = Sandbox("inspect", sandbox_settings)
        snapshot = inspector.world_snapshot()
        assert "mock-wake.txt" in snapshot
    finally:
        remove_volume(sandbox_settings.world_volume)


def test_inspect_world_script_works_after_world_deleted(
    docker_required: None, repo_root: Path, unique_name: str
) -> None:
    settings = docker_settings(repo_root, unique_name)
    remove_volume(settings.world_volume)
    sandbox = Sandbox("delete-world", settings)
    try:
        sandbox.start()
        assert sandbox.exec_bash("printf data > file.txt").exit_code == 0
        assert sandbox.exec_bash("rm -rf /world/* /world/.[!.]* /world/..?* 2>/dev/null || true").exit_code == 0
        sandbox.stop()
        env = {
            **os.environ,
            "WORLD_VOLUME": settings.world_volume,
            "SANDBOX_IMAGE": settings.image,
        }
        result = subprocess.run(
            ["bash", "scripts/inspect-world.sh"],
            cwd=repo_root,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        assert "(empty)" in result.stdout
    finally:
        remove_volume(settings.world_volume)
