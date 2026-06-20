from __future__ import annotations

import json
import os
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def write_cli_fixture(root: Path) -> tuple[Path, str]:
    maker = root / "maker-place"
    wakes = maker / "wakes"
    field_notes = maker / "field-notes"
    wakes.mkdir(parents=True)
    field_notes.mkdir(parents=True)
    wake_id = "20260101T000000Z-cli"
    events = [
        {"time": "2026-01-01T00:00:00Z", "type": "wake_start", "wake_id": wake_id, "model": "mock/free:free"},
        {
            "time": "2026-01-01T00:00:01Z",
            "type": "model_response",
            "wake_id": wake_id,
            "model": "mock/free:free",
            "finish_reason": "stop",
            "has_tool_calls": False,
            "tool_call_count": 0,
        },
        {"time": "2026-01-01T00:00:02Z", "type": "model_text", "wake_id": wake_id, "text": {"preview": "hello"}},
        {"time": "2026-01-01T00:00:03Z", "type": "model_text_only", "wake_id": wake_id},
        {"time": "2026-01-01T00:00:04Z", "type": "required_tool_choice_ignored", "wake_id": wake_id},
        {
            "time": "2026-01-01T00:00:05Z",
            "type": "tool_call",
            "wake_id": wake_id,
            "tool": "shell",
            "arguments": {"command": "true"},
        },
        {"time": "2026-01-01T00:00:06Z", "type": "wake_end", "wake_id": wake_id, "end_reason": "sleep_or_finish"},
    ]
    (maker / "events.jsonl").write_text("\n".join(json.dumps(event) for event in events) + "\n")
    (wakes / f"{wake_id}.json").write_text(
        json.dumps(
            {
                "wake_id": wake_id,
                "model": "mock/free:free",
                "start_time": "2026-01-01T00:00:00Z",
                "end_time": "2026-01-01T00:00:06Z",
                "end_reason": "sleep_or_finish",
                "model_responses": [{"has_tool_calls": False}],
                "text_outputs": [{"preview": "hello"}],
                "tool_calls": [
                    {
                        "index": 1,
                        "name": "shell",
                        "arguments": {"command": "true"},
                        "result": {
                            "ok": True,
                            "exit_code": 0,
                            "elapsed_seconds": 0.01,
                            "stdout": {"preview": "ok"},
                            "stderr": {"preview": ""},
                        },
                    }
                ],
                "errors": [],
                "diff_summary": {
                    "before_entries": 1,
                    "after_entries": 1,
                    "changed": False,
                    "diff_lines": 0,
                    "diff_preview": [],
                    "diff_truncated": False,
                },
            }
        )
    )
    (field_notes / f"{wake_id}.md").write_text(
        "# Field Note: 20260101T000000Z-cli\n\n"
        "A companion creature named Lumen appeared in the garden record.\n"
    )
    return maker, wake_id


def fake_docker_env(tmp_path: Path) -> dict[str, str]:
    fake_bin = tmp_path / "fake-docker-bin"
    fake_bin.mkdir()
    fake_docker = fake_bin / "docker"
    fake_docker.write_text(
        "#!/usr/bin/env bash\n"
        "if [ \"$1\" = \"run\" ]; then\n"
        "  printf './garden\\n./friends/lumen.md\\n./creatures/spark.txt\\n'\n"
        "fi\n"
        "exit 0\n"
    )
    fake_docker.chmod(0o755)
    return {"PATH": f"{fake_bin}:{os.environ['PATH']}"}


def run_maker(
    repo_root: Path,
    args: list[str],
    env: dict[str, str] | None = None,
    **kwargs,
) -> subprocess.CompletedProcess[str]:
    run_env = os.environ.copy()
    if env:
        run_env.update(env)
    return subprocess.run(
        ["go", "run", "./cmd/maker", *args],
        cwd=repo_root,
        env=run_env,
        capture_output=True,
        text=True,
        check=True,
        **kwargs,
    )


def test_go_cli_status_events_wakes_show_and_evaluate(repo_root: Path, tmp_path: Path) -> None:
    maker, wake_id = write_cli_fixture(tmp_path)
    base = ["--maker-place", str(maker)]

    status = run_maker(repo_root, [*base, "status"])
    assert "maker-place:" in status.stdout
    assert f"latest wake: {wake_id}" in status.stdout

    events = run_maker(repo_root, [*base, "events", "--last", "2"])
    assert "tool_call" in events.stdout
    assert "wake_end" in events.stdout

    wakes = run_maker(repo_root, [*base, "wakes"])
    assert wake_id in wakes.stdout

    show = run_maker(repo_root, [*base, "show", "last"])
    assert "tools: 1" in show.stdout
    assert "model responses: 1" in show.stdout

    evaluate = run_maker(repo_root, [*base, "evaluate", "--wake", wake_id, "--last-responses", "10"])
    assert "required ignored: 1" in evaluate.stdout
    assert "tool calls: 1" in evaluate.stdout
    assert "evaluation: world-mutating tool activity observed" in evaluate.stdout


def test_go_cli_file_stdin_and_output_routing(repo_root: Path, tmp_path: Path) -> None:
    maker, wake_id = write_cli_fixture(tmp_path)
    events_path = maker / "events.jsonl"
    out_path = tmp_path / "events.out"

    run_maker(repo_root, ["--input", str(events_path), "--output", str(out_path), "events", "--last", "1"])
    assert "wake_end" in out_path.read_text()

    stdin_eval = run_maker(
        repo_root,
        ["--input", "-", "evaluate", "--wake", wake_id, "--last-responses", "10"],
        input=events_path.read_text(),
    )
    assert "wake: 20260101T000000Z-cli" in stdin_eval.stdout
    assert stdin_eval.stderr == ""


def test_go_cli_dashboard_once_and_output_file(repo_root: Path, tmp_path: Path) -> None:
    maker, wake_id = write_cli_fixture(tmp_path)
    base = ["--maker-place", str(maker)]
    fake_bin = tmp_path / "fake-dashboard-bin"
    fake_bin.mkdir()
    fake_docker = fake_bin / "docker"
    fake_docker.write_text("#!/usr/bin/env bash\nexit 0\n")
    fake_docker.chmod(0o755)
    env = {"PATH": f"{fake_bin}:{os.environ['PATH']}"}

    dashboard = run_maker(repo_root, [*base, "dashboard", "--once", "--no-clear", "--events", "3"], env=env)
    assert "Maker Dashboard" in dashboard.stdout
    assert "\x1b[" not in dashboard.stdout
    assert "[IDLE] no controller loop or wake is active" in dashboard.stdout
    assert "STATUS" in dashboard.stdout
    assert "CURRENT WAKE" in dashboard.stdout
    assert "WORK ACCOMPLISHED" in dashboard.stdout
    assert "RECENT WAKES" in dashboard.stdout
    assert "RECENT EVENTS" in dashboard.stdout
    assert wake_id in dashboard.stdout
    assert "tool activity observed; no world listing changes" in dashboard.stdout
    assert "world         unchanged entries=1->1 diff_lines=0" in dashboard.stdout
    assert "tools         1 call(s)" in dashboard.stdout

    color_dashboard = run_maker(
        repo_root,
        [*base, "dashboard", "--once", "--no-clear", "--color", "always"],
        env=env,
    )
    assert "\x1b[" in color_dashboard.stdout

    out_path = tmp_path / "dashboard.out"
    run_maker(
        repo_root,
        [*base, "--output", str(out_path), "dashboard", "--once", "--no-clear", "--events", "2"],
        env=env,
    )
    written = out_path.read_text()
    assert "Maker Dashboard" in written
    assert "wake_end" in written


def test_go_cli_interface_html_json_output_and_world_publish(repo_root: Path, tmp_path: Path) -> None:
    maker, wake_id = write_cli_fixture(tmp_path)
    base = ["--maker-place", str(maker)]
    env = fake_docker_env(tmp_path)

    interface = run_maker(repo_root, [*base, "interface", "--refresh", "0", "--world-depth", "2"], env=env)
    assert "<title>Finn Interface</title>" in interface.stdout
    assert "Thinking" in interface.stdout
    assert "Creations" in interface.stdout
    assert "Friends" in interface.stdout
    assert "Creatures" in interface.stdout
    assert wake_id in interface.stdout
    assert "./friends/lumen.md" in interface.stdout
    assert "./creatures/spark.txt" in interface.stdout

    snapshot = run_maker(repo_root, [*base, "--json", "interface", "--world-depth", "2"], env=env)
    payload = json.loads(snapshot.stdout)
    assert payload["latest_wake"]["id"] == wake_id
    assert payload["totals"]["wakes"] == 1
    assert payload["world"]["count"] == 3
    assert payload["friends"]
    assert payload["creatures"]

    out_path = tmp_path / "interface" / "index.html"
    written = run_maker(
        repo_root,
        [*base, "interface", "--output", str(out_path), "--publish-world"],
        env=env,
    )
    assert f"interface written: {out_path}" in written.stdout
    assert "world snapshot published: /world/_maker/interface-status.md" in written.stdout
    assert "Finn Interface" in out_path.read_text()


def test_go_cli_start_and_stop_commands(repo_root: Path, tmp_path: Path) -> None:
    maker = tmp_path / "maker-place"
    maker.mkdir()
    pid_path = maker / "controller.pid"
    pid_path.write_text(str(os.getpid()))

    start = run_maker(repo_root, ["--maker-place", str(maker), "start"])

    assert "controller already running" in start.stdout
    assert pid_path.read_text() == str(os.getpid())

    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    fake_docker = fake_bin / "docker"
    fake_docker.write_text("#!/usr/bin/env bash\nexit 0\n")
    fake_docker.chmod(0o755)
    stop_maker = tmp_path / "stop-maker-place"
    stop_maker.mkdir()
    (stop_maker / "wake.lock").write_text(
        json.dumps({"pid": 0, "started_at": "2026-01-01T00:00:00Z", "wake_id": "stale-wake"})
    )
    stop = run_maker(
        repo_root,
        ["--maker-place", str(stop_maker), "stop"],
        env={"PATH": f"{fake_bin}:{os.environ['PATH']}"},
    )

    assert "controller stopped" in stop.stdout
    assert "removed stale wake lock" in stop.stdout
    assert (stop_maker / "stop").exists()
    assert not (stop_maker / "wake.lock").exists()


def test_go_cli_evaluate_prefers_wake_diff_over_snapshot_presence(repo_root: Path, tmp_path: Path) -> None:
    maker, wake_id = write_cli_fixture(tmp_path)
    with (maker / "events.jsonl").open("a") as f:
        f.write(
            json.dumps(
                {
                    "time": "2026-01-01T00:00:07Z",
                    "type": "world_snapshot_written",
                    "wake_id": wake_id,
                    "label": "after",
                    "summary": {"bytes": 99},
                }
            )
            + "\n"
        )

    evaluate = run_maker(repo_root, ["--maker-place", str(maker), "evaluate", "--wake", wake_id])

    assert "world changed: false" in evaluate.stdout


def test_go_cli_doctor_and_probe_cover_ollama(repo_root: Path, tmp_path: Path) -> None:
    requests: list[dict] = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path != "/api/tags":
                self.send_error(404)
                return
            self._send_json(
                {
                    "models": [
                        {"name": "llama3.1:8b"},
                        {"name": "qwen3.5:9b"},
                    ]
                }
            )

        def do_POST(self) -> None:
            if self.path != "/api/chat":
                self.send_error(404)
                return
            length = int(self.headers.get("content-length", "0"))
            payload = json.loads(self.rfile.read(length).decode())
            requests.append(payload)
            self._send_json(
                {
                    "model": payload["model"],
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "function": {
                                    "name": "shell",
                                    "arguments": {"command": "printf hi > /world/hi.txt"},
                                }
                            }
                        ],
                    },
                    "done": True,
                }
            )

        def log_message(self, format: str, *args) -> None:
            return

        def _send_json(self, payload: dict) -> None:
            data = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"
    env = {
        "OLLAMA_BASE_URL": base_url,
        "OLLAMA_MODEL": "llama3.1:8b",
        "OLLAMA_FALLBACKS": "qwen3.5:9b",
        "MAKER_PLACE_DIR": str(tmp_path / "maker-place"),
    }
    try:
        doctor = run_maker(repo_root, ["doctor"], env=env)
        assert "ollama_reachable" in doctor.stdout
        assert "ollama_primary_installed" in doctor.stdout
        assert "ollama_fallback_installed" in doctor.stdout

        probe = run_maker(
            repo_root,
            ["probe-model", "--provider", "ollama", "--model", "llama3.1:8b"],
            env=env,
        )
    finally:
        server.shutdown()
        server.server_close()

    assert "tool calls emitted: true" in probe.stdout
    assert "tool names: shell" in probe.stdout
    assert requests
    assert requests[0]["messages"][0]["content"].startswith("In the beginning, there was a maker.")
    assert len(requests[0]["tools"]) == 9
