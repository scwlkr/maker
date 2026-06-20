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

    def exec_bash_with_input(
        self,
        command: str,
        input_text: str,
        timeout: int | None = None,
    ) -> CommandResult:
        self.commands.append(command)
        return CommandResult(0, "written.txt\n", "", False, 0.01)

    def stop(self) -> dict:
        return {"exists": True, "status": "running", "exit_code": 0, "mounts": []}


class TextOnlyModelClient:
    def chat(
        self,
        model: str,
        messages: list[dict],
        tools: list[dict],
        timeout: int,
        tool_choice: object | None = None,
    ) -> dict:
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


class IgnoringWriteChoiceThenFinishModelClient:
    def __init__(self) -> None:
        self.calls = 0
        self.tool_choices: list[object | None] = []

    def chat(
        self,
        model: str,
        messages: list[dict],
        tools: list[dict],
        timeout: int,
        tool_choice: object | None = None,
    ) -> dict:
        self.calls += 1
        self.tool_choices.append(tool_choice)
        if self.calls == 1:
            message = {"role": "assistant", "content": "preserve this ignored write\n"}
        else:
            message = {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "finish-call",
                        "type": "function",
                        "function": {"name": "sleep_or_finish", "arguments": {}},
                    }
                ],
            }
        return {
            "id": f"ignored-write-{self.calls}",
            "model": model,
            "choices": [{"index": 0, "finish_reason": "stop", "message": message}],
        }


class TextJsonToolModelClient:
    def __init__(self) -> None:
        self.calls = 0

    def chat(
        self,
        model: str,
        messages: list[dict],
        tools: list[dict],
        timeout: int,
        tool_choice: object | None = None,
    ) -> dict:
        self.calls += 1
        if self.calls == 1:
            content = json.dumps(
                {
                    "name": "shell",
                    "arguments": {"command": "printf 'Finn was here\\n' > /world/mock-wake.txt"},
                }
            )
        else:
            content = json.dumps({"name": "sleep_or_finish", "arguments": {}})
        return {
            "id": f"text-json-{self.calls}",
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": content},
                }
            ],
        }


class TooManyToolCallsModelClient:
    def chat(
        self,
        model: str,
        messages: list[dict],
        tools: list[dict],
        timeout: int,
        tool_choice: object | None = None,
    ) -> dict:
        return {
            "id": "too-many-tools",
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "tool_calls",
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call-1",
                                "type": "function",
                                "function": {
                                    "name": "shell",
                                    "arguments": json.dumps({"command": "printf one > /world/one.txt"}),
                                },
                            },
                            {
                                "id": "call-2",
                                "type": "function",
                                "function": {
                                    "name": "shell",
                                    "arguments": json.dumps({"command": "printf two > /world/two.txt"}),
                                },
                            },
                            {
                                "id": "call-3",
                                "type": "function",
                                "function": {
                                    "name": "shell",
                                    "arguments": json.dumps({"command": "printf three > /world/three.txt"}),
                                },
                            },
                        ],
                    },
                }
            ],
        }


class RecordingToolChoiceModelClient:
    def __init__(self) -> None:
        self.calls = 0
        self.tool_choices: list[object | None] = []

    def chat(
        self,
        model: str,
        messages: list[dict],
        tools: list[dict],
        timeout: int,
        tool_choice: object | None = None,
    ) -> dict:
        self.calls += 1
        self.tool_choices.append(tool_choice)
        tool = "list_files" if self.calls == 1 else "sleep_or_finish"
        call_id = f"recording-call-{self.calls}"
        return {
            "id": f"recording-{self.calls}",
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "tool_calls",
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": call_id,
                                "type": "function",
                                "function": {"name": tool, "arguments": "{}"},
                            }
                        ],
                    },
                }
            ],
        }


class IgnoringFirstToolChoiceModelClient:
    def __init__(self) -> None:
        self.calls = 0
        self.tool_choices: list[object | None] = []

    def chat(
        self,
        model: str,
        messages: list[dict],
        tools: list[dict],
        timeout: int,
        tool_choice: object | None = None,
    ) -> dict:
        self.calls += 1
        self.tool_choices.append(tool_choice)
        if self.calls == 1:
            return {
                "id": "ignoring-first-1",
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": "I will inspect the world."},
                    }
                ],
            }
        return {
            "id": "ignoring-first-2",
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "tool_calls",
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "finish-call",
                                "type": "function",
                                "function": {"name": "sleep_or_finish", "arguments": "{}"},
                            }
                        ],
                    },
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
        model_max_tokens=None,
        fetch_timeout_seconds=5,
        text_only_delay_seconds=0,
        max_consecutive_text_only_responses=3,
        max_tool_calls_per_wake=80,
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
    maker = MakerPlace(settings.maker_place_dir)
    summary = Controller(settings, maker_place=maker, model_client=TextOnlyModelClient()).run_wake()

    assert summary is not None
    assert summary["end_reason"] == "text_only_limit"
    assert len(summary["model_responses"]) == 3
    assert summary["model_responses"][0]["has_tool_calls"] is False
    assert summary["model_responses"][0]["finish_reason"] == "stop"
    events = (settings.maker_place_dir / "events.jsonl").read_text()
    assert "required_tool_choice_ignored" in events
    assert "text_only_limit_reached" in events


def test_ignored_write_file_choice_preserves_text_as_fallback_write(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(controller, "Sandbox", FakeSandbox)
    FakeSandbox.snapshot = ""
    FakeSandbox.commands = []
    settings = make_settings(tmp_path)
    settings.tool_schema_mode = "files"
    settings.model_tool_choice = {"type": "function", "function": {"name": "write_file"}}
    maker = MakerPlace(settings.maker_place_dir)
    client = IgnoringWriteChoiceThenFinishModelClient()

    summary = Controller(settings, maker_place=maker, model_client=client).run_wake()

    assert summary is not None
    assert summary["end_reason"] == "sleep_or_finish"
    assert client.calls == 2
    assert [call["name"] for call in summary["tool_calls"]] == ["write_file", "sleep_or_finish"]
    first_call = summary["tool_calls"][0]
    assert first_call["id"] == "enforced-write_file-text-1"
    assert first_call["arguments"] == {"content": "preserve this ignored write\n"}
    assert first_call["result"]["path"].startswith("_finn/")
    assert first_call["result"]["path"].endswith("/write_file_0001_preserve_this_ignored_write.md")
    assert FakeSandbox.commands
    events = (settings.maker_place_dir / "events.jsonl").read_text()
    assert "file_tool_choice_text_enforced" in events
    assert "write_file_path_defaulted" in events


def test_exact_json_text_tool_call_mode_promotes_tool_calls(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(controller, "Sandbox", FakeSandbox)
    FakeSandbox.snapshot = ""
    FakeSandbox.commands = []
    settings = make_settings(tmp_path)
    settings.text_tool_call_mode = "exact-json"
    maker = MakerPlace(settings.maker_place_dir)
    summary = Controller(settings, maker_place=maker, model_client=TextJsonToolModelClient()).run_wake()

    assert summary is not None
    assert summary["end_reason"] == "sleep_or_finish"
    assert [call["name"] for call in summary["tool_calls"]] == ["shell", "sleep_or_finish"]
    assert any("mock-wake.txt" in command for command in FakeSandbox.commands)
    events = (settings.maker_place_dir / "events.jsonl").read_text()
    assert "text_tool_call_promoted" in events


def test_tool_call_limit_stops_before_executing_extra_calls(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(controller, "Sandbox", FakeSandbox)
    FakeSandbox.snapshot = ""
    FakeSandbox.commands = []
    settings = make_settings(tmp_path)
    settings.max_tool_calls_per_wake = 2
    maker = MakerPlace(settings.maker_place_dir)
    summary = Controller(settings, maker_place=maker, model_client=TooManyToolCallsModelClient()).run_wake()

    assert summary is not None
    assert summary["end_reason"] == "tool_call_limit"
    assert [call["id"] for call in summary["tool_calls"]] == ["call-1", "call-2"]
    assert FakeSandbox.commands == ["printf one > /world/one.txt", "printf two > /world/two.txt"]
    events = (settings.maker_place_dir / "events.jsonl").read_text()
    assert "tool_call_limit_reached" in events


def test_first_model_tool_choice_applies_only_to_first_request(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(controller, "Sandbox", FakeSandbox)
    FakeSandbox.snapshot = ""
    FakeSandbox.commands = []
    settings = make_settings(tmp_path)
    settings.tool_schema_mode = "files"
    settings.model_tool_choice = "required"
    settings.first_model_tool_choice = {"type": "function", "function": {"name": "list_files"}}
    client = RecordingToolChoiceModelClient()

    summary = Controller(settings, model_client=client).run_wake()

    assert summary is not None
    assert summary["end_reason"] == "sleep_or_finish"
    assert client.tool_choices == [
        {"type": "function", "function": {"name": "list_files"}},
        None,
    ]
    assert [call["name"] for call in summary["tool_calls"]] == ["list_files", "sleep_or_finish"]


def test_first_model_tool_choice_is_enforced_when_provider_ignores_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(controller, "Sandbox", FakeSandbox)
    FakeSandbox.snapshot = ""
    FakeSandbox.commands = []
    settings = make_settings(tmp_path)
    settings.tool_schema_mode = "files"
    settings.model_tool_choice = "required"
    settings.first_model_tool_choice = {"type": "function", "function": {"name": "list_files"}}
    client = IgnoringFirstToolChoiceModelClient()
    maker = MakerPlace(settings.maker_place_dir)

    summary = Controller(settings, maker_place=maker, model_client=client).run_wake()

    assert summary is not None
    assert summary["end_reason"] == "sleep_or_finish"
    assert client.tool_choices == [
        {"type": "function", "function": {"name": "list_files"}},
        None,
    ]
    assert [call["id"] for call in summary["tool_calls"]] == [
        "enforced-first-tool-choice-1",
        "finish-call",
    ]
    assert [call["name"] for call in summary["tool_calls"]] == ["list_files", "sleep_or_finish"]
    assert summary["model_responses"][0]["has_tool_calls"] is False
    events = (settings.maker_place_dir / "events.jsonl").read_text()
    assert "first_tool_choice_enforced" in events


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
    OpenRouterClient("key", max_tokens=2048).chat(
        "model/free:free",
        [{"role": "user", "content": "prompt"}],
        TOOL_SCHEMAS,
        timeout=7,
    )

    assert captured["timeout"] == 7
    assert captured["body"]["tool_choice"] == "required"
    assert captured["body"]["max_tokens"] == 2048
    assert captured["body"]["tools"] == TOOL_SCHEMAS


def test_openrouter_tool_choice_can_be_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def read(self) -> bytes:
            return b'{"choices":[{"message":{"role":"assistant","content":"ok"}}]}'

    def fake_urlopen(request, timeout):
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse()

    monkeypatch.setattr(controller.urllib.request, "urlopen", fake_urlopen)
    OpenRouterClient("key", tool_choice=None).chat("model/free:free", [], TOOL_SCHEMAS, timeout=7)

    assert "tool_choice" not in captured["body"]


def test_openrouter_chat_can_override_tool_choice(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def read(self) -> bytes:
            return b'{"choices":[{"message":{"role":"assistant","content":"ok"}}]}'

    def fake_urlopen(request, timeout):
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse()

    monkeypatch.setattr(controller.urllib.request, "urlopen", fake_urlopen)
    OpenRouterClient("key", tool_choice="required").chat(
        "model/free:free",
        [],
        TOOL_SCHEMAS,
        timeout=7,
        tool_choice={"type": "function", "function": {"name": "list_files"}},
    )

    assert captured["body"]["tool_choice"] == {"type": "function", "function": {"name": "list_files"}}


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


def test_ollama_client_sends_configured_tool_choice(monkeypatch: pytest.MonkeyPatch) -> None:
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
                    "message": {"role": "assistant", "content": "hello"},
                    "done": True,
                }
            ).encode()

    def fake_urlopen(request, timeout):
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse()

    monkeypatch.setattr(controller.urllib.request, "urlopen", fake_urlopen)
    controller.OllamaClient(
        "http://ollama.local",
        tool_choice={"type": "function", "function": {"name": "shell"}},
        options={"temperature": 1.2},
    ).chat("llama3.1:8b", [], TOOL_SCHEMAS, timeout=7)

    assert captured["body"]["tool_choice"] == {"type": "function", "function": {"name": "shell"}}
    assert captured["body"]["options"] == {"temperature": 1.2}


def test_ollama_client_can_override_tool_choice(monkeypatch: pytest.MonkeyPatch) -> None:
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
                    "message": {"role": "assistant", "content": "hello"},
                    "done": True,
                }
            ).encode()

    def fake_urlopen(request, timeout):
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse()

    monkeypatch.setattr(controller.urllib.request, "urlopen", fake_urlopen)
    controller.OllamaClient("http://ollama.local", tool_choice="required").chat(
        "llama3.1:8b",
        [],
        TOOL_SCHEMAS,
        timeout=7,
        tool_choice={"type": "function", "function": {"name": "list_files"}},
    )

    assert captured["body"]["tool_choice"] == {"type": "function", "function": {"name": "list_files"}}


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


def test_settings_parse_list_files_preview_chars(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LIST_FILES_PREVIEW_CHARS", "700")
    monkeypatch.setenv("MAKER_PLACE_DIR", str(tmp_path / "maker-place"))

    settings = controller.settings_from_env_file(tmp_path)

    assert settings.list_files_preview_chars == 700


def test_tool_schema_mode_can_limit_to_shell(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    settings.tool_schema_mode = "shell-only"
    runtime = Controller(settings, model_client=MockModelClient())

    assert [schema["function"]["name"] for schema in runtime.tool_schemas] == ["shell"]


def test_tool_schema_mode_can_limit_to_write_file(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    settings.tool_schema_mode = "write-only"
    runtime = Controller(settings, model_client=MockModelClient())

    assert [schema["function"]["name"] for schema in runtime.tool_schemas] == ["write_file"]


def test_tool_schema_mode_can_limit_to_file_tools(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    settings.tool_schema_mode = "files"
    runtime = Controller(settings, model_client=MockModelClient())

    assert [schema["function"]["name"] for schema in runtime.tool_schemas] == [
        "list_files",
        "read_file",
        "write_file",
        "append_file",
    ]


def test_parse_model_tool_choice_function() -> None:
    assert controller.parse_model_tool_choice("function:shell") == {
        "type": "function",
        "function": {"name": "shell"},
    }


def test_promote_text_tool_call_accepts_parameters_key() -> None:
    promoted = controller.promote_text_tool_call(
        {
            "role": "assistant",
            "content": '{"name":"shell","parameters":{"command":"true"}}',
        },
        "exact-json",
    )

    assert promoted is not None
    tool_call = promoted["assistant_message"]["tool_calls"][0]
    assert json.loads(tool_call["function"]["arguments"]) == {"command": "true"}


def test_promote_text_tool_call_exact_literal_accepts_python_literals() -> None:
    promoted = controller.promote_text_tool_call(
        {
            "role": "assistant",
            "content": "{'name':'write_file','parameters':{'path':'init.txt','content':'hi','append':False}}",
        },
        "exact-literal",
        {"write_file"},
    )

    assert promoted is not None
    tool_call = promoted["assistant_message"]["tool_calls"][0]
    assert json.loads(tool_call["function"]["arguments"]) == {
        "path": "init.txt",
        "content": "hi",
        "append": False,
    }


def test_promote_text_tool_call_exact_literal_accepts_string_concat() -> None:
    promoted = controller.promote_text_tool_call(
        {
            "role": "assistant",
            "content": (
                '{"name": "write_file", "parameters": '
                '{"path": "/world/genesis.txt", '
                '"content": "hello\\n" + "world\\n", "append": False}}'
            ),
        },
        "exact-literal",
        {"write_file"},
    )

    assert promoted is not None
    tool_call = promoted["assistant_message"]["tool_calls"][0]
    assert json.loads(tool_call["function"]["arguments"]) == {
        "path": "/world/genesis.txt",
        "content": "hello\nworld\n",
        "append": False,
    }


def test_promote_text_tool_call_fenced_json_accepts_whole_code_block() -> None:
    promoted = controller.promote_text_tool_call(
        {
            "role": "assistant",
            "content": (
                "```json\n"
                '{"name":"write_file","arguments":{"path":"README.md","content":"hi"}}\n'
                "```"
            ),
        },
        "fenced-json",
        {"write_file"},
    )

    assert promoted is not None
    tool_call = promoted["assistant_message"]["tool_calls"][0]
    assert json.loads(tool_call["function"]["arguments"]) == {
        "path": "README.md",
        "content": "hi",
    }


def test_promote_text_tool_call_rejects_unadvertised_tool() -> None:
    promoted = controller.promote_text_tool_call(
        {
            "role": "assistant",
            "content": '{"name":"tell_finn_the_command","parameters":{"command":"true"}}',
        },
        "exact-json",
        {"shell"},
    )

    assert promoted is None
