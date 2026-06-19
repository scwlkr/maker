from __future__ import annotations

import json
from pathlib import Path

import pytest

import controller
from controller import Controller, MockModelClient, OpenRouterClient, Settings
from maker_place import MakerPlace
from sandbox import CommandResult, SandboxSettings
from tools import TOOL_SCHEMAS


class FakeSandbox:
    snapshot = ""
    commands: list[str] = []

    def __init__(self, wake_id: str, settings: SandboxSettings):
        self.wake_id = wake_id
        self.settings = settings
        self.started = False

    def start(self) -> None:
        self.started = True

    def world_snapshot(self) -> str:
        return self.snapshot

    def exec_bash(self, command: str, timeout: int | None = None) -> CommandResult:
        self.commands.append(command)
        if "mock-wake.txt" in command:
            FakeSandbox.snapshot = "-rw-r--r-- 14 2026-01-01 00:00 ./mock-wake.txt\n"
        return CommandResult(0, "", "", False, 0.01)

    def stop(self) -> dict:
        return {"exists": True, "status": "running", "exit_code": 0, "mounts": []}


class TextOnlyModelClient:
    def chat(self, model: str, messages: list[dict], tools: list[dict], timeout: int) -> dict:
        return {
            "id": "text-only",
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": "x" * 8000},
                }
            ],
        }


def make_settings(tmp_path: Path) -> Settings:
    return Settings(
        model_provider="openrouter",
        openrouter_api_key=None,
        ollama_base_url="http://localhost:11434",
        model="mock/free:free",
        model_fallbacks=[],
        wake_interval_seconds=300,
        context_limit_tokens=120000,
        store_raw_outputs=False,
        model_timeout_seconds=5,
        fetch_timeout_seconds=5,
        text_only_delay_seconds=0,
        maker_place_dir=tmp_path / "maker-place",
        sandbox=SandboxSettings(repo_root=Path.cwd()),
        mock_model=True,
    )


def test_run_once_with_mock_model_logs_wake(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(controller, "Sandbox", FakeSandbox)
    FakeSandbox.snapshot = ""
    FakeSandbox.commands = []
    settings = make_settings(tmp_path)
    maker = MakerPlace(settings.maker_place_dir)
    summary = Controller(settings, maker_place=maker, model_client=MockModelClient()).run_wake()

    assert summary is not None
    assert summary["end_reason"] == "sleep_or_finish"
    assert [call["name"] for call in summary["tool_calls"]] == ["shell", "sleep_or_finish"]
    assert (settings.maker_place_dir / "events.jsonl").exists()
    assert Path(summary["snapshots"]["before"]).exists()
    assert Path(summary["snapshots"]["after"]).exists()
    assert (settings.maker_place_dir / "wakes" / f"{summary['wake_id']}.json").exists()
    assert any("mock-wake.txt" in command for command in FakeSandbox.commands)
    assert [item["has_tool_calls"] for item in summary["model_responses"]] == [True, True]


def test_context_exhaustion_ends_wake_without_summary(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(controller, "Sandbox", FakeSandbox)
    settings = make_settings(tmp_path)
    settings.context_limit_tokens = 1
    maker = MakerPlace(settings.maker_place_dir)
    summary = Controller(settings, maker_place=maker, model_client=MockModelClient()).run_wake()

    assert summary is not None
    assert summary["end_reason"] == "context_exhausted"
    assert summary["tool_calls"] == []


def test_text_only_response_logs_required_tool_choice_ignored(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(controller, "Sandbox", FakeSandbox)
    FakeSandbox.snapshot = ""
    settings = make_settings(tmp_path)
    settings.context_limit_tokens = 2000
    maker = MakerPlace(settings.maker_place_dir)
    summary = Controller(settings, maker_place=maker, model_client=TextOnlyModelClient()).run_wake()

    assert summary is not None
    assert summary["end_reason"] == "context_exhausted"
    assert summary["model_responses"][0]["has_tool_calls"] is False
    assert summary["model_responses"][0]["finish_reason"] == "stop"
    events = (settings.maker_place_dir / "events.jsonl").read_text()
    assert "required_tool_choice_ignored" in events


def test_wake_lock_skips_second_wake(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(controller, "Sandbox", FakeSandbox)
    settings = make_settings(tmp_path)
    maker = MakerPlace(settings.maker_place_dir)
    lock = maker.acquire_wake_lock("already-running")
    try:
        assert Controller(settings, maker_place=maker, model_client=MockModelClient()).run_wake() is None
        events = (settings.maker_place_dir / "events.jsonl").read_text()
        assert "wake_skipped_already_running" in events
    finally:
        lock.release()


def test_openrouter_requests_required_tool_choice(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def read(self) -> bytes:
            return b'{"choices":[{"message":{"role":"assistant","tool_calls":[]}}]}'

    def fake_urlopen(request, timeout):
        import json

        captured["timeout"] = timeout
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse()

    monkeypatch.setattr(controller.urllib.request, "urlopen", fake_urlopen)
    OpenRouterClient("key").chat(
        "model/free:free",
        [{"role": "user", "content": "prompt"}],
        TOOL_SCHEMAS,
        timeout=7,
    )

    assert captured["timeout"] == 7
    assert captured["body"]["tool_choice"] == "required"
    assert captured["body"]["tools"] == TOOL_SCHEMAS


def test_ollama_client_parses_tool_call_response(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def read(self) -> bytes:
            return json.dumps(
                {
                    "model": "llama3.1:8b",
                    "created_at": "2026-01-01T00:00:00Z",
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
            ).encode()

    def fake_urlopen(request, timeout):
        captured["timeout"] = timeout
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse()

    monkeypatch.setattr(controller.urllib.request, "urlopen", fake_urlopen)
    response = controller.OllamaClient("http://ollama.local").chat(
        "llama3.1:8b",
        [{"role": "user", "content": controller.MAKER_PROMPT}],
        TOOL_SCHEMAS,
        timeout=7,
    )

    message = response["choices"][0]["message"]
    tool_call = message["tool_calls"][0]
    assert captured["timeout"] == 7
    assert captured["body"]["stream"] is False
    assert captured["body"]["tools"] == TOOL_SCHEMAS
    assert tool_call["function"]["name"] == "shell"
    assert json.loads(tool_call["function"]["arguments"]) == {"command": "printf hi > /world/hi.txt"}


def test_ollama_client_handles_text_only_response(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def read(self) -> bytes:
            return json.dumps(
                {
                    "model": "llama3.1:8b",
                    "message": {"role": "assistant", "content": "hello"},
                    "done": True,
                    "done_reason": "stop",
                }
            ).encode()

    monkeypatch.setattr(controller.urllib.request, "urlopen", lambda request, timeout: FakeResponse())
    response = controller.OllamaClient("http://ollama.local").chat("llama3.1:8b", [], TOOL_SCHEMAS, timeout=7)

    message = response["choices"][0]["message"]
    assert message["content"] == "hello"
    assert "tool_calls" not in message
    assert response["choices"][0]["finish_reason"] == "stop"


def test_ollama_client_sends_native_tool_conversation(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def read(self) -> bytes:
            return json.dumps(
                {
                    "model": "llama3.1:8b",
                    "message": {"role": "assistant", "content": "done"},
                    "done": True,
                }
            ).encode()

    def fake_urlopen(request, timeout):
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse()

    monkeypatch.setattr(controller.urllib.request, "urlopen", fake_urlopen)
    controller.OllamaClient("http://ollama.local").chat(
        "llama3.1:8b",
        [
            {"role": "user", "content": controller.MAKER_PROMPT},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call-1",
                        "type": "function",
                        "function": {"name": "shell", "arguments": '{"command": "true"}'},
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "call-1", "name": "shell", "content": '{"ok": true}'},
        ],
        TOOL_SCHEMAS,
        timeout=7,
    )

    messages = captured["body"]["messages"]
    assert messages[1]["tool_calls"][0]["function"]["arguments"] == {"command": "true"}
    assert messages[2] == {"role": "tool", "content": '{"ok": true}'}


def test_provider_selection_uses_ollama_without_openrouter_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("MODEL_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama.local:11434")
    monkeypatch.setenv("OLLAMA_MODEL", "llama3.1:8b")
    monkeypatch.setenv("OLLAMA_FALLBACKS", "qwen3.5:9b")
    monkeypatch.setenv("MAKER_PLACE_DIR", str(tmp_path / "maker-place"))

    settings = controller.settings_from_env_file(tmp_path)
    runtime = Controller(settings)

    assert settings.model_provider == "ollama"
    assert settings.model == "llama3.1:8b"
    assert settings.model_fallbacks == ["qwen3.5:9b"]
    assert isinstance(runtime.model_client, controller.OllamaClient)
