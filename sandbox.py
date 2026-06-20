from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from maker_place import summarize_text


DEFAULT_PATH = "/world/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"


@dataclass
class CommandResult:
    exit_code: int | None
    stdout: str
    stderr: str
    timed_out: bool
    elapsed_seconds: float

    def for_tool(self, max_chars: int) -> dict[str, Any]:
        return {
            "exit_code": self.exit_code,
            "timed_out": self.timed_out,
            "elapsed_seconds": self.elapsed_seconds,
            "stdout": summarize_text(self.stdout, max_chars),
            "stderr": summarize_text(self.stderr, max_chars),
        }


@dataclass
class SandboxSettings:
    image: str = "maker-finn-sandbox:latest"
    world_volume: str = "maker_finn_world"
    cpus: str = "1.0"
    memory: str = "512m"
    pids_limit: str = "256"
    shell_timeout_seconds: int = 60
    tool_output_chars: int = 20000
    repo_root: Path = Path(".")


class DockerError(RuntimeError):
    pass


class Sandbox:
    def __init__(self, wake_id: str, settings: SandboxSettings):
        self.wake_id = wake_id
        self.settings = settings
        suffix = wake_id.lower().replace("_", "-")
        self.container_name = f"maker-finn-{suffix}"
        self.started = False

    def _run(
        self,
        args: list[str],
        timeout: int | None = None,
        check: bool = True,
        text: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        try:
            proc = subprocess.run(
                args,
                cwd=self.settings.repo_root,
                capture_output=True,
                text=text,
                timeout=timeout,
            )
        except FileNotFoundError as exc:
            raise DockerError("docker CLI not found") from exc
        except subprocess.TimeoutExpired as exc:
            raise DockerError(f"docker command timed out: {' '.join(args)}") from exc
        if check and proc.returncode != 0:
            detail = proc.stderr.strip() or proc.stdout.strip()
            raise DockerError(f"docker command failed ({proc.returncode}): {' '.join(args)}\n{detail}")
        return proc

    def ensure_image(self) -> None:
        if os.environ.get("REBUILD_SANDBOX") == "1":
            self.build_image()
            return
        proc = self._run(["docker", "image", "inspect", self.settings.image], check=False)
        if proc.returncode != 0:
            self.build_image()

    def build_image(self) -> None:
        dockerfile = self.settings.repo_root / "Dockerfile.sandbox"
        self._run(
            [
                "docker",
                "build",
                "-f",
                str(dockerfile),
                "-t",
                self.settings.image,
                str(self.settings.repo_root),
            ],
            timeout=600,
        )

    def ensure_volume(self) -> None:
        self._run(["docker", "volume", "create", self.settings.world_volume])

    def start(self) -> None:
        self.ensure_image()
        self.ensure_volume()
        self._run(
            [
                "docker",
                "run",
                "-d",
                "--name",
                self.container_name,
                "--label",
                "maker.runtime=finn",
                "--network",
                "bridge",
                "--cpus",
                self.settings.cpus,
                "--memory",
                self.settings.memory,
                "--pids-limit",
                self.settings.pids_limit,
                "--workdir",
                "/world",
                "--env",
                "HOME=/world",
                "--env",
                f"PATH={DEFAULT_PATH}",
                "-v",
                f"{self.settings.world_volume}:/world",
                self.settings.image,
                "sleep",
                "infinity",
            ]
        )
        self.started = True

    def exec_bash(self, command: str, timeout: int | None = None) -> CommandResult:
        timeout = timeout if timeout is not None else self.settings.shell_timeout_seconds
        args = [
            "docker",
            "exec",
            "--workdir",
            "/world",
            "--env",
            "HOME=/world",
            "--env",
            f"PATH={DEFAULT_PATH}",
            self.container_name,
            "bash",
            "-lc",
            command,
        ]
        start = time.monotonic()
        try:
            proc = subprocess.run(
                args,
                cwd=self.settings.repo_root,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return CommandResult(
                proc.returncode,
                proc.stdout,
                proc.stderr,
                False,
                round(time.monotonic() - start, 3),
            )
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout or ""
            stderr = exc.stderr or ""
            if isinstance(stdout, bytes):
                stdout = stdout.decode("utf-8", errors="replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode("utf-8", errors="replace")
            return CommandResult(None, stdout, stderr, True, round(time.monotonic() - start, 3))
        except FileNotFoundError as exc:
            return CommandResult(None, "", f"docker CLI not found: {exc}", False, round(time.monotonic() - start, 3))

    def exec_bash_with_input(
        self,
        command: str,
        input_text: str,
        timeout: int | None = None,
    ) -> CommandResult:
        timeout = timeout if timeout is not None else self.settings.shell_timeout_seconds
        args = [
            "docker",
            "exec",
            "-i",
            "--workdir",
            "/world",
            "--env",
            "HOME=/world",
            "--env",
            f"PATH={DEFAULT_PATH}",
            self.container_name,
            "bash",
            "-lc",
            command,
        ]
        start = time.monotonic()
        try:
            proc = subprocess.run(
                args,
                cwd=self.settings.repo_root,
                input=input_text,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return CommandResult(
                proc.returncode,
                proc.stdout,
                proc.stderr,
                False,
                round(time.monotonic() - start, 3),
            )
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout or ""
            stderr = exc.stderr or ""
            if isinstance(stdout, bytes):
                stdout = stdout.decode("utf-8", errors="replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode("utf-8", errors="replace")
            return CommandResult(None, stdout, stderr, True, round(time.monotonic() - start, 3))
        except FileNotFoundError as exc:
            return CommandResult(None, "", f"docker CLI not found: {exc}", False, round(time.monotonic() - start, 3))

    def world_snapshot(self) -> str:
        self.ensure_image()
        self.ensure_volume()
        script = (
            "cd /world && "
            "if [ -z \"$(find . -mindepth 1 -maxdepth 1 -print -quit)\" ]; then exit 0; fi && "
            "find . -mindepth 1 "
            "-printf '%M %s %TY-%Tm-%Td %TH:%TM %p\\n' | sort | head -n 5000"
        )
        proc = self._run(
            [
                "docker",
                "run",
                "--rm",
                "-v",
                f"{self.settings.world_volume}:/world:ro",
                self.settings.image,
                "bash",
                "-lc",
                script,
            ],
            timeout=120,
            check=False,
        )
        return proc.stdout if proc.returncode == 0 else proc.stdout + proc.stderr

    def inspect(self) -> dict[str, Any]:
        proc = self._run(
            ["docker", "inspect", self.container_name],
            timeout=30,
            check=False,
        )
        if proc.returncode != 0:
            return {"exists": False, "error": proc.stderr.strip()}
        payload = json.loads(proc.stdout)
        if not payload:
            return {"exists": False}
        state = payload[0].get("State", {})
        mounts = payload[0].get("Mounts", [])
        return {
            "exists": True,
            "status": state.get("Status"),
            "exit_code": state.get("ExitCode"),
            "oom_killed": state.get("OOMKilled"),
            "mounts": [
                {
                    "type": mount.get("Type"),
                    "name": mount.get("Name"),
                    "destination": mount.get("Destination"),
                    "source": mount.get("Source"),
                }
                for mount in mounts
            ],
        }

    def stop(self) -> dict[str, Any]:
        status = self.inspect() if self.started else {"exists": False}
        self._run(["docker", "rm", "-f", self.container_name], timeout=60, check=False)
        self.started = False
        return status


def settings_from_env(repo_root: str | Path = ".") -> SandboxSettings:
    return SandboxSettings(
        image=os.getenv("SANDBOX_IMAGE", "maker-finn-sandbox:latest"),
        world_volume=os.getenv("WORLD_VOLUME", "maker_finn_world"),
        cpus=os.getenv("SANDBOX_CPUS", "1.0"),
        memory=os.getenv("SANDBOX_MEMORY", "512m"),
        pids_limit=os.getenv("SANDBOX_PIDS_LIMIT", "256"),
        shell_timeout_seconds=int(os.getenv("SHELL_TIMEOUT_SECONDS", "60")),
        tool_output_chars=int(os.getenv("MAX_TOOL_OUTPUT_CHARS", "20000")),
        repo_root=Path(repo_root).resolve(),
    )
