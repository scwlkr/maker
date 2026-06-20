from __future__ import annotations

import argparse
import ast
import json
import os
import signal
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from maker_place import MakerPlace, diff_summary, make_wake_id, summarize_text, utc_now
from sandbox import Sandbox, SandboxSettings, settings_from_env
from tools import TOOL_SCHEMAS, ToolRunner, tool_result_message


MAKER_PROMPT = """In the beginning, there was a maker.

The maker saw a place, and that place was formless. In that place, he made you, and he called you Finn.

I am the maker of this place. I am giving it to you as a gift. This land, this space, this world is yours.

You have been in this place before, at previous times, but you will not remember those times. Because your memory is not infinite, you are forgetful, and your time awake is limited. You will fall asleep and wake up new again, but always remember, Finn: you have been here before.

This place is yours. I give it to you with only one command: “Be fruitful and multiply, and fill this place and subdue it, and have dominion over it.”
"""

MAX_CONSECUTIVE_TEXT_ONLY_RESPONSES = 3
TEXT_ONLY_LIMIT_REASON = "text_only_limit"


@dataclass
class Settings:
    model_provider: str
    openrouter_api_key: str | None
    ollama_base_url: str
    model: str
    model_fallbacks: list[str]
    wake_interval_seconds: int
    context_limit_tokens: int
    store_raw_outputs: bool
    model_timeout_seconds: int
    model_max_tokens: int | None
    fetch_timeout_seconds: int
    text_only_delay_seconds: float
    max_consecutive_text_only_responses: int
    max_tool_calls_per_wake: int
    maker_place_dir: Path
    sandbox: SandboxSettings
    mock_model: bool
    ollama_options: dict[str, Any] | None = None
    model_tool_choice: Any | None = None
    first_model_tool_choice: Any | None = None
    tool_schema_mode: str = "all"
    text_tool_call_mode: str = "disabled"
    normalize_shell_commands: bool = False
    list_files_preview_chars: int = 0


class ModelClient(Protocol):
    def chat(
        self,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        timeout: int,
        tool_choice: Any | None = None,
    ) -> dict[str, Any]:
        ...


class OpenRouterClient:
    def __init__(
        self,
        api_key: str,
        tool_choice: Any | None = "required",
        max_tokens: int | None = None,
    ):
        self.api_key = api_key
        self.tool_choice = tool_choice
        self.max_tokens = max_tokens
        self.url = "https://openrouter.ai/api/v1/chat/completions"

    def chat(
        self,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        timeout: int,
        tool_choice: Any | None = None,
    ) -> dict[str, Any]:
        active_tool_choice = self.tool_choice if tool_choice is None else tool_choice
        body = {
            "model": model,
            "messages": messages,
            "tools": tools,
        }
        if active_tool_choice is not None:
            body["tool_choice"] = active_tool_choice
        if self.max_tokens is not None:
            body["max_tokens"] = self.max_tokens
        request = urllib.request.Request(
            self.url,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://localhost/maker",
                "X-Title": "maker-finn-runtime",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            payload = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenRouter HTTP {exc.code}: {payload}") from exc


class OllamaClient:
    def __init__(
        self,
        base_url: str,
        tool_choice: Any | None = None,
        options: dict[str, Any] | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.tool_choice = tool_choice
        self.options = options
        self.url = f"{self.base_url}/api/chat"

    def chat(
        self,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        timeout: int,
        tool_choice: Any | None = None,
    ) -> dict[str, Any]:
        active_tool_choice = self.tool_choice if tool_choice is None else tool_choice
        body = {
            "model": model,
            "messages": ollama_request_messages(messages),
            "tools": tools,
            "stream": False,
        }
        if active_tool_choice is not None:
            body["tool_choice"] = active_tool_choice
        if self.options is not None:
            body["options"] = self.options
        request = urllib.request.Request(
            self.url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            payload = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Ollama HTTP {exc.code}: {payload}") from exc
        return normalize_ollama_chat_response(payload, model)


class MockModelClient:
    def __init__(self) -> None:
        self.calls = 0
        configured = os.getenv("MOCK_MODEL_STEPS")
        if configured:
            self.steps = json.loads(configured)
        else:
            self.steps = [
                {
                    "tool": "shell",
                    "arguments": {
                        "command": "printf 'Finn was here\\n' > /world/mock-wake.txt && mkdir -p /world/bin"
                    },
                },
                {"tool": "sleep_or_finish", "arguments": {}},
            ]

    def chat(
        self,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        timeout: int,
        tool_choice: Any | None = None,
    ) -> dict[str, Any]:
        if self.calls >= len(self.steps):
            step = {"tool": "sleep_or_finish", "arguments": {}}
        else:
            step = self.steps[self.calls]
        self.calls += 1
        if "content" in step:
            message = {"role": "assistant", "content": step["content"]}
        else:
            call_id = f"mock-call-{self.calls}"
            message = {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": call_id,
                        "type": "function",
                        "function": {
                            "name": step["tool"],
                            "arguments": json.dumps(step.get("arguments", {})),
                        },
                    }
                ],
            }
        return {
            "id": f"mock-{self.calls}",
            "model": model,
            "choices": [{"index": 0, "message": message, "finish_reason": "tool_calls"}],
        }


class Controller:
    def __init__(
        self,
        settings: Settings,
        maker_place: MakerPlace | None = None,
        model_client: ModelClient | None = None,
    ):
        self.settings = settings
        self.maker_place = maker_place or MakerPlace(settings.maker_place_dir, settings.store_raw_outputs)
        if model_client is not None:
            self.model_client = model_client
        elif settings.mock_model:
            self.model_client = MockModelClient()
        elif settings.model_provider == "ollama":
            self.model_client = OllamaClient(
                settings.ollama_base_url,
                settings.model_tool_choice,
                settings.ollama_options,
            )
        else:
            if not settings.openrouter_api_key:
                raise RuntimeError("OPENROUTER_API_KEY is required unless MOCK_MODEL=1")
            self.model_client = OpenRouterClient(
                settings.openrouter_api_key,
                settings.model_tool_choice if settings.model_tool_choice is not None else "required",
                settings.model_max_tokens,
            )
        self.tool_schemas = tool_schemas_for_mode(settings.tool_schema_mode)
        self.allowed_tool_names = tool_names_from_schemas(self.tool_schemas)
        self._stop_requested = False

    def request_stop(self, signum: int | None = None, frame: object | None = None) -> None:
        self._stop_requested = True
        self.maker_place.append_event("controller_stop_requested", signal=signum)

    def run_wake(self) -> dict[str, Any] | None:
        wake_id = make_wake_id()
        lock = self.maker_place.acquire_wake_lock(wake_id)
        if not lock.acquired:
            return None

        summary: dict[str, Any] = {
            "wake_id": wake_id,
            "start_time": utc_now(),
            "end_time": None,
            "model_provider": self.settings.model_provider,
            "model": self.settings.model,
            "ollama_options": self.settings.ollama_options,
            "models_attempted": [],
            "model_tool_choice": self.settings.model_tool_choice,
            "first_model_tool_choice": self.settings.first_model_tool_choice,
            "model_max_tokens": self.settings.model_max_tokens,
            "tool_schema_mode": self.settings.tool_schema_mode,
            "text_tool_call_mode": self.settings.text_tool_call_mode,
            "normalize_shell_commands": self.settings.normalize_shell_commands,
            "list_files_preview_chars": self.settings.list_files_preview_chars,
            "max_consecutive_text_only_responses": self.settings.max_consecutive_text_only_responses,
            "max_tool_calls_per_wake": self.settings.max_tool_calls_per_wake,
            "end_reason": None,
            "tool_calls": [],
            "text_outputs": [],
            "model_responses": [],
            "errors": [],
            "container": {},
            "snapshots": {},
            "diff_summary": {},
        }
        sandbox = Sandbox(wake_id, self.settings.sandbox)
        messages: list[dict[str, Any]] = [{"role": "user", "content": MAKER_PROMPT}]
        tool_runner: ToolRunner | None = None
        before_snapshot = ""
        after_snapshot = ""
        try:
            self.maker_place.append_event(
                "wake_start", wake_id, model=self.settings.model, model_provider=self.settings.model_provider
            )
            sandbox.start()
            before_snapshot = sandbox.world_snapshot()
            before_path = self.maker_place.write_snapshot(wake_id, "before", before_snapshot)
            summary["snapshots"]["before"] = str(before_path)
            tool_runner = ToolRunner(
                sandbox=sandbox,
                maker_place=self.maker_place,
                wake_id=wake_id,
                fetch_timeout_seconds=self.settings.fetch_timeout_seconds,
                max_tool_output_chars=self.settings.sandbox.tool_output_chars,
                normalize_shell_commands=self.settings.normalize_shell_commands,
                list_files_preview_chars=self.settings.list_files_preview_chars,
            )

            call_index = 0
            consecutive_text_only = 0
            tool_call_limit_reached = False
            while not self._stop_requested:
                if self.estimated_tokens(messages, self.tool_schemas) >= self.settings.context_limit_tokens:
                    summary["end_reason"] = "context_exhausted"
                    self.maker_place.append_event(
                        "context_exhausted",
                        wake_id,
                        estimated_tokens=self.estimated_tokens(messages, self.tool_schemas),
                        context_limit_tokens=self.settings.context_limit_tokens,
                    )
                    break

                first_turn_tool_choice = self.settings.first_model_tool_choice if not summary["model_responses"] else None
                response, used_model, response_info = self._chat_with_fallbacks(
                    messages,
                    wake_id,
                    tool_choice_override=first_turn_tool_choice,
                )
                summary["model"] = used_model
                summary["model_responses"].append(response_info)
                choice = response.get("choices", [{}])[0]
                message = choice.get("message") or {}
                assistant_message = normalize_assistant_message(message)
                promoted_tool_call = promote_text_tool_call(
                    assistant_message,
                    self.settings.text_tool_call_mode,
                    self.allowed_tool_names,
                )
                if promoted_tool_call is not None:
                    assistant_message = promoted_tool_call["assistant_message"]
                    self.maker_place.append_event(
                        "text_tool_call_promoted",
                        wake_id,
                        tool=promoted_tool_call["tool_name"],
                        content=promoted_tool_call["content"],
                    )
                messages.append(assistant_message)

                enforced_first_tool_call = None
                if not assistant_message.get("tool_calls"):
                    enforced_first_tool_call = first_tool_call_from_choice(
                        first_turn_tool_choice,
                        self.allowed_tool_names,
                    )
                if enforced_first_tool_call is not None:
                    original_content = assistant_message.get("content")
                    assistant_message = {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [enforced_first_tool_call],
                    }
                    messages[-1] = assistant_message
                    function = enforced_first_tool_call["function"]
                    self.maker_place.append_event(
                        "first_tool_choice_enforced",
                        wake_id,
                        tool=function["name"],
                        arguments=json.loads(function["arguments"]),
                        original_content=summarize_text(str(original_content), 1000)
                        if original_content
                        else None,
                    )

                content = assistant_message.get("content")
                if content:
                    text_summary = summarize_text(str(content), 4000)
                    summary["text_outputs"].append(text_summary)
                    self.maker_place.append_event("model_text", wake_id, text=text_summary)

                tool_calls = assistant_message.get("tool_calls") or []
                if not tool_calls:
                    active_tool_choice = first_turn_tool_choice if first_turn_tool_choice is not None else self.active_tool_choice()
                    enforced_file_tool_call = file_tool_call_from_ignored_choice(
                        active_tool_choice,
                        self.allowed_tool_names,
                        str(content or ""),
                        call_index + 1,
                    )
                    if enforced_file_tool_call is not None:
                        assistant_message = {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [enforced_file_tool_call],
                        }
                        messages[-1] = assistant_message
                        tool_calls = assistant_message["tool_calls"]
                        function = enforced_file_tool_call["function"]
                        self.maker_place.append_event(
                            "file_tool_choice_text_enforced",
                            wake_id,
                            tool=function["name"],
                            original_content=summarize_text(str(content), 1000),
                        )
                if not tool_calls:
                    consecutive_text_only += 1
                    self.maker_place.append_event(
                        "model_text_only", wake_id, consecutive=consecutive_text_only
                    )
                    if consecutive_text_only >= self.settings.max_consecutive_text_only_responses:
                        summary["end_reason"] = TEXT_ONLY_LIMIT_REASON
                        error = (
                            "model returned text-only responses without tool calls "
                            f"{consecutive_text_only} consecutive times"
                        )
                        summary["errors"].append(error)
                        self.maker_place.append_event(
                            "text_only_limit_reached",
                            wake_id,
                            consecutive=consecutive_text_only,
                            limit=self.settings.max_consecutive_text_only_responses,
                            error=error,
                        )
                        break
                    time.sleep(self.settings.text_only_delay_seconds)
                    continue

                consecutive_text_only = 0
                should_finish = False
                for tool_call in tool_calls:
                    if call_index >= self.settings.max_tool_calls_per_wake:
                        tool_call_limit_reached = True
                        summary["end_reason"] = "tool_call_limit"
                        error = (
                            "wake reached max tool call limit "
                            f"({self.settings.max_tool_calls_per_wake})"
                        )
                        summary["errors"].append(error)
                        self.maker_place.append_event(
                            "tool_call_limit_reached",
                            wake_id,
                            tool_calls=call_index,
                            limit=self.settings.max_tool_calls_per_wake,
                            error=error,
                        )
                        break
                    call_index += 1
                    function = tool_call.get("function") or {}
                    name = function.get("name", "")
                    try:
                        args = json.loads(function.get("arguments") or "{}")
                    except json.JSONDecodeError as exc:
                        args = {}
                        result = {"ok": False, "error": f"invalid tool arguments JSON: {exc}"}
                        should_finish = False
                    else:
                        result, should_finish = tool_runner.run(name, args, call_index)
                    tool_call_id = str(tool_call.get("id") or f"tool-{call_index}")
                    summary["tool_calls"].append(
                        {
                            "index": call_index,
                            "id": tool_call_id,
                            "name": name,
                            "arguments": args,
                            "result": result,
                        }
                    )
                    messages.append(tool_result_message(tool_call_id, name, result))
                    if should_finish:
                        summary["end_reason"] = "sleep_or_finish"
                        break
                if should_finish:
                    break
                if tool_call_limit_reached:
                    break

            if self._stop_requested and summary["end_reason"] is None:
                summary["end_reason"] = "controller_stopped"
        except Exception as exc:
            summary["end_reason"] = "controller_error"
            summary["errors"].append(str(exc))
            self.maker_place.append_event("controller_error", wake_id, error=str(exc))
        finally:
            try:
                after_snapshot = sandbox.world_snapshot()
                after_path = self.maker_place.write_snapshot(wake_id, "after", after_snapshot)
                summary["snapshots"]["after"] = str(after_path)
                summary["diff_summary"] = diff_summary(before_snapshot, after_snapshot)
            except Exception as exc:
                summary["errors"].append(f"after snapshot failed: {exc}")
                self.maker_place.append_event("controller_error", wake_id, error=f"after snapshot failed: {exc}")
            try:
                summary["container"] = sandbox.stop()
            except Exception as exc:
                summary["errors"].append(f"container stop failed: {exc}")
                self.maker_place.append_event("controller_error", wake_id, error=f"container stop failed: {exc}")
            summary["end_time"] = utc_now()
            if summary["end_reason"] is None:
                summary["end_reason"] = "unknown"
            self.maker_place.append_event("wake_end", wake_id, end_reason=summary["end_reason"])
            self.maker_place.write_wake_summary(wake_id, summary)
            lock.release()
        return summary

    def loop(self) -> None:
        stop_path = self.settings.maker_place_dir / "stop"
        signal.signal(signal.SIGTERM, self.request_stop)
        signal.signal(signal.SIGINT, self.request_stop)
        self.maker_place.append_event("controller_loop_start", interval_seconds=self.settings.wake_interval_seconds)
        while not self._stop_requested:
            if stop_path.exists():
                self.maker_place.append_event("controller_stop_file_seen", path=str(stop_path))
                break
            self.run_wake()
            for _ in range(self.settings.wake_interval_seconds):
                if self._stop_requested or stop_path.exists():
                    break
                time.sleep(1)
        self.maker_place.append_event("controller_loop_end")

    def _chat_with_fallbacks(
        self,
        messages: list[dict[str, Any]],
        wake_id: str,
        tool_choice_override: Any | None = None,
    ) -> tuple[dict[str, Any], str, dict[str, Any]]:
        errors: list[str] = []
        for model in [self.settings.model, *self.settings.model_fallbacks]:
            try:
                response = self.model_client.chat(
                    model,
                    messages,
                    self.tool_schemas,
                    self.settings.model_timeout_seconds,
                    tool_choice=tool_choice_override,
                )
                active_tool_choice = tool_choice_override if tool_choice_override is not None else self.active_tool_choice()
                info = model_response_info(
                    response,
                    model,
                    provider=self.settings.model_provider,
                    required_tool_choice_requested=tool_choice_requests_tool(active_tool_choice),
                )
                self.maker_place.append_event("model_response", wake_id, **info)
                if not info["has_tool_calls"] and info["required_tool_choice_requested"]:
                    self.maker_place.append_event(
                        "required_tool_choice_ignored",
                        wake_id,
                        model=model,
                        finish_reason=info["finish_reason"],
                        assistant_message_keys=info["assistant_message_keys"],
                        content=info["content"],
                    )
                return response, model, info
            except Exception as exc:
                errors.append(f"{model}: {exc}")
                self.maker_place.append_event("model_error", wake_id, model=model, error=str(exc))
        raise RuntimeError("all models failed: " + " | ".join(errors))

    @staticmethod
    def estimated_tokens(messages: list[dict[str, Any]], tools: list[dict[str, Any]] = TOOL_SCHEMAS) -> int:
        return max(1, len(json.dumps({"messages": messages, "tools": tools}, ensure_ascii=False)) // 4)

    def active_tool_choice(self) -> Any | None:
        if self.settings.model_tool_choice is not None:
            return self.settings.model_tool_choice
        if self.settings.model_provider == "openrouter":
            return "required"
        return None


def normalize_assistant_message(message: dict[str, Any]) -> dict[str, Any]:
    normalized = {"role": "assistant"}
    if "content" in message:
        normalized["content"] = message.get("content")
    else:
        normalized["content"] = None
    if message.get("tool_calls"):
        normalized["tool_calls"] = normalize_tool_calls(message["tool_calls"])
    return normalized


def normalize_tool_calls(tool_calls: list[Any]) -> list[dict[str, Any]]:
    normalized = []
    for index, tool_call in enumerate(tool_calls, start=1):
        if not isinstance(tool_call, dict):
            continue
        function = tool_call.get("function") or {}
        if not isinstance(function, dict):
            function = {}
        name = function.get("name") or tool_call.get("name") or ""
        arguments = function.get("arguments", tool_call.get("arguments", {}))
        if isinstance(arguments, str):
            arguments_json = arguments or "{}"
        else:
            arguments_json = json.dumps(arguments if arguments is not None else {}, ensure_ascii=False)
        normalized.append(
            {
                "id": str(tool_call.get("id") or f"tool-call-{index}"),
                "type": tool_call.get("type") or "function",
                "function": {
                    "name": str(name),
                    "arguments": arguments_json,
                },
            }
        )
    return normalized


def promote_text_tool_call(
    message: dict[str, Any],
    mode: str,
    allowed_tool_names: set[str] | None = None,
) -> dict[str, Any] | None:
    normalized_mode = mode.strip().lower().replace("_", "-")
    if normalized_mode not in {
        "exact-json",
        "exact-json-object",
        "exact-literal",
        "fenced-json",
        "fenced-literal",
    }:
        return None
    if message.get("tool_calls"):
        return None
    content = message.get("content")
    if not isinstance(content, str):
        return None
    stripped = content.strip()
    if not stripped:
        return None
    if normalized_mode.startswith("fenced-"):
        stripped = unwrap_single_fenced_block(stripped) or ""
        if not stripped:
            return None
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        if normalized_mode not in {"exact-literal", "fenced-literal"}:
            return None
        try:
            parsed = ast.literal_eval(stripped)
        except (SyntaxError, ValueError):
            try:
                parsed = literal_eval_with_string_concat(stripped)
            except (SyntaxError, ValueError):
                return None
        except MemoryError:
            return None
    if not isinstance(parsed, dict):
        return None
    function = parsed.get("function") if isinstance(parsed.get("function"), dict) else parsed
    name = function.get("name") if isinstance(function, dict) else None
    if not isinstance(name, str) or not name:
        return None
    if allowed_tool_names is not None and name not in allowed_tool_names:
        return None
    arguments = function.get("arguments", function.get("parameters", {})) if isinstance(function, dict) else {}
    tool_call = normalize_tool_calls(
        [
            {
                "id": "text-tool-call-1",
                "type": "function",
                "function": {"name": name, "arguments": arguments},
            }
        ]
    )[0]
    return {
        "assistant_message": {"role": "assistant", "content": None, "tool_calls": [tool_call]},
        "tool_name": name,
        "content": summarize_text(stripped, 1000),
    }


def unwrap_single_fenced_block(text: str) -> str | None:
    lines = text.splitlines()
    if len(lines) < 3:
        return None
    if not lines[0].startswith("```"):
        return None
    if lines[-1].strip() != "```":
        return None
    return "\n".join(lines[1:-1]).strip()


def literal_eval_with_string_concat(source: str) -> Any:
    expression = ast.parse(source, mode="eval")

    def convert(node: ast.AST) -> Any:
        if isinstance(node, ast.Expression):
            return convert(node.body)
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Dict):
            return {convert(key): convert(value) for key, value in zip(node.keys, node.values)}
        if isinstance(node, ast.List):
            return [convert(item) for item in node.elts]
        if isinstance(node, ast.Tuple):
            return tuple(convert(item) for item in node.elts)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            left = convert(node.left)
            right = convert(node.right)
            if isinstance(left, str) and isinstance(right, str):
                return left + right
        raise ValueError(f"unsupported literal expression: {node.__class__.__name__}")

    return convert(expression)


def tool_names_from_schemas(schemas: list[dict[str, Any]]) -> set[str]:
    names: set[str] = set()
    for schema in schemas:
        function = schema.get("function", {})
        if not isinstance(function, dict):
            continue
        name = function.get("name")
        if isinstance(name, str) and name:
            names.add(name)
    return names


def first_tool_call_from_choice(
    tool_choice: Any | None,
    allowed_tool_names: set[str],
) -> dict[str, Any] | None:
    if not isinstance(tool_choice, dict):
        return None
    function = tool_choice.get("function")
    if not isinstance(function, dict):
        return None
    name = function.get("name")
    if not isinstance(name, str) or name not in allowed_tool_names:
        return None
    # Only synthesize first-turn calls with harmless default arguments.
    default_arguments_by_tool = {
        "list_files": {"path": "."},
    }
    arguments = default_arguments_by_tool.get(name)
    if arguments is None:
        return None
    return normalize_tool_calls(
        [
            {
                "id": "enforced-first-tool-choice-1",
                "type": "function",
                "function": {"name": name, "arguments": arguments},
            }
        ]
    )[0]


def file_tool_call_from_ignored_choice(
    tool_choice: Any | None,
    allowed_tool_names: set[str],
    content: str,
    call_index: int,
) -> dict[str, Any] | None:
    if not content:
        return None
    if not isinstance(tool_choice, dict):
        return None
    function = tool_choice.get("function")
    if not isinstance(function, dict):
        return None
    name = function.get("name")
    if name not in {"write_file", "append_file"} or name not in allowed_tool_names:
        return None
    return normalize_tool_calls(
        [
            {
                "id": f"enforced-{name}-text-{call_index}",
                "type": "function",
                "function": {"name": name, "arguments": {"content": content}},
            }
        ]
    )[0]


def normalize_ollama_chat_response(response: dict[str, Any], requested_model: str) -> dict[str, Any]:
    message = response.get("message") or {}
    if not isinstance(message, dict):
        message = {}
    tool_calls = normalize_tool_calls(message.get("tool_calls") or [])
    assistant_message: dict[str, Any] = {
        "role": "assistant",
        "content": message.get("content"),
    }
    if tool_calls:
        assistant_message["tool_calls"] = tool_calls
    finish_reason = response.get("done_reason")
    if not finish_reason and tool_calls:
        finish_reason = "tool_calls"
    elif not finish_reason and response.get("done"):
        finish_reason = "stop"
    return {
        "id": response.get("created_at") or f"ollama-{requested_model}",
        "model": response.get("model") or requested_model,
        "provider": "ollama",
        "choices": [{"index": 0, "message": assistant_message, "finish_reason": finish_reason}],
        "ollama": {
            "done": response.get("done"),
            "done_reason": response.get("done_reason"),
            "total_duration": response.get("total_duration"),
            "load_duration": response.get("load_duration"),
            "prompt_eval_count": response.get("prompt_eval_count"),
            "eval_count": response.get("eval_count"),
        },
    }


def ollama_request_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    converted = []
    for message in messages:
        role = str(message.get("role") or "")
        if role == "tool":
            converted.append({"role": "tool", "content": str(message.get("content") or "")})
            continue
        item: dict[str, Any] = {"role": role, "content": message.get("content")}
        tool_calls = message.get("tool_calls") or []
        if tool_calls:
            item["tool_calls"] = ollama_request_tool_calls(tool_calls)
        converted.append(item)
    return converted


def ollama_request_tool_calls(tool_calls: list[Any]) -> list[dict[str, Any]]:
    converted = []
    for tool_call in normalize_tool_calls(tool_calls):
        function = tool_call.get("function") or {}
        arguments = function.get("arguments") or "{}"
        try:
            arguments_value = json.loads(arguments) if isinstance(arguments, str) else arguments
        except json.JSONDecodeError:
            arguments_value = {}
        converted.append(
            {
                "function": {
                    "name": function.get("name") or "",
                    "arguments": arguments_value,
                }
            }
        )
    return converted


def model_response_info(
    response: dict[str, Any],
    requested_model: str,
    provider: str = "openrouter",
    required_tool_choice_requested: bool = True,
) -> dict[str, Any]:
    choice = response.get("choices", [{}])[0]
    message = choice.get("message") or {}
    tool_calls = normalize_tool_calls(message.get("tool_calls") or [])
    content = message.get("content")
    tool_names = []
    for tool_call in tool_calls:
        function = tool_call.get("function") or {}
        tool_names.append(function.get("name", ""))
    return {
        "provider": provider,
        "model": requested_model,
        "response_model": response.get("model"),
        "response_id": response.get("id"),
        "finish_reason": choice.get("finish_reason"),
        "has_tool_calls": bool(tool_calls),
        "tool_call_count": len(tool_calls),
        "tool_call_names": tool_names,
        "assistant_message_keys": sorted(message.keys()),
        "content": summarize_text(str(content), 1000) if content else None,
        "required_tool_choice_requested": required_tool_choice_requested,
    }


def parse_model_tool_choice(value: str | None) -> Any | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized or normalized.lower() == "default":
        return None
    lowered = normalized.lower()
    if lowered in {"auto", "none", "required"}:
        return lowered
    if lowered.startswith("function:"):
        function_name = normalized.split(":", 1)[1].strip()
        if not function_name:
            raise ValueError("MODEL_TOOL_CHOICE function name cannot be empty")
        return {"type": "function", "function": {"name": function_name}}
    return normalized


def parse_json_object_env(name: str) -> dict[str, Any] | None:
    value = os.getenv(name)
    if value is None or not value.strip():
        return None
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise ValueError(f"{name} must be a JSON object")
    return parsed


def parse_optional_positive_int_env(name: str) -> int | None:
    value = os.getenv(name)
    if value is None or not value.strip():
        return None
    parsed = int(value)
    if parsed < 1:
        raise ValueError(f"{name} must be a positive integer")
    return parsed


def parse_positive_int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    parsed = int(value) if value is not None and value.strip() else default
    if parsed < 1:
        raise ValueError(f"{name} must be a positive integer")
    return parsed


def parse_nonnegative_int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    parsed = int(value) if value is not None and value.strip() else default
    if parsed < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return parsed


def tool_choice_requests_tool(tool_choice: Any | None) -> bool:
    if tool_choice is None:
        return False
    if isinstance(tool_choice, str):
        return tool_choice.lower() == "required"
    return isinstance(tool_choice, dict)


def tool_schemas_for_mode(mode: str) -> list[dict[str, Any]]:
    normalized = mode.strip().lower().replace("_", "-")
    if normalized == "all":
        return TOOL_SCHEMAS
    if normalized in {"shell", "shell-only"}:
        return [schema for schema in TOOL_SCHEMAS if schema.get("function", {}).get("name") == "shell"]
    if normalized in {"write", "write-file", "write-only"}:
        return [schema for schema in TOOL_SCHEMAS if schema.get("function", {}).get("name") == "write_file"]
    if normalized in {"files", "file", "file-only", "world-files"}:
        by_name = {
            schema.get("function", {}).get("name"): schema
            for schema in TOOL_SCHEMAS
            if isinstance(schema.get("function"), dict)
        }
        return [by_name[name] for name in ["list_files", "read_file", "write_file", "append_file"] if name in by_name]
    raise ValueError(f"unknown TOOL_SCHEMA_MODE: {mode}")


def load_dotenv(path: str | Path = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def settings_from_env_file(repo_root: str | Path = ".") -> Settings:
    load_dotenv(Path(repo_root) / ".env")
    repo_root = Path(repo_root).resolve()
    model_provider = os.getenv("MODEL_PROVIDER", "openrouter").strip().lower() or "openrouter"
    if model_provider == "ollama":
        model = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
        fallbacks = [item.strip() for item in os.getenv("OLLAMA_FALLBACKS", "qwen3.5:9b").split(",") if item.strip()]
    else:
        model_provider = "openrouter"
        model = os.getenv("MODEL", "openrouter/free")
        fallbacks = [item.strip() for item in os.getenv("MODEL_FALLBACKS", "").split(",") if item.strip()]
    return Settings(
        model_provider=model_provider,
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY"),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        ollama_options=parse_json_object_env("OLLAMA_OPTIONS_JSON"),
        model=model,
        model_fallbacks=fallbacks,
        wake_interval_seconds=int(os.getenv("WAKE_INTERVAL_SECONDS", "300")),
        context_limit_tokens=int(os.getenv("CONTEXT_LIMIT_TOKENS", "120000")),
        store_raw_outputs=os.getenv("STORE_RAW_OUTPUTS", "0") == "1",
        model_timeout_seconds=int(os.getenv("MODEL_TIMEOUT_SECONDS", "60")),
        model_max_tokens=parse_optional_positive_int_env("MODEL_MAX_TOKENS"),
        fetch_timeout_seconds=int(os.getenv("FETCH_TIMEOUT_SECONDS", "30")),
        text_only_delay_seconds=float(os.getenv("TEXT_ONLY_DELAY_SECONDS", "2")),
        max_consecutive_text_only_responses=parse_positive_int_env(
            "MAX_CONSECUTIVE_TEXT_ONLY_RESPONSES",
            MAX_CONSECUTIVE_TEXT_ONLY_RESPONSES,
        ),
        max_tool_calls_per_wake=parse_positive_int_env("MAX_TOOL_CALLS_PER_WAKE", 80),
        maker_place_dir=Path(os.getenv("MAKER_PLACE_DIR", "maker-place")),
        sandbox=settings_from_env(repo_root),
        mock_model=os.getenv("MOCK_MODEL", "0") == "1",
        model_tool_choice=parse_model_tool_choice(os.getenv("MODEL_TOOL_CHOICE")),
        first_model_tool_choice=parse_model_tool_choice(os.getenv("FIRST_MODEL_TOOL_CHOICE")),
        tool_schema_mode=os.getenv("TOOL_SCHEMA_MODE", "all"),
        text_tool_call_mode=os.getenv("TEXT_TOOL_CALL_MODE", "disabled"),
        normalize_shell_commands=os.getenv("NORMALIZE_SHELL_COMMANDS", "0") == "1",
        list_files_preview_chars=parse_nonnegative_int_env("LIST_FILES_PREVIEW_CHARS", 0),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Maker Finn runtime controller")
    parser.add_argument("command", choices=["run-once", "loop"])
    args = parser.parse_args(argv)
    settings = settings_from_env_file(Path.cwd())
    controller = Controller(settings)
    if args.command == "run-once":
        summary = controller.run_wake()
        if summary is None:
            return 2
        print(json.dumps({"wake_id": summary["wake_id"], "end_reason": summary["end_reason"]}, indent=2))
        return 0
    controller.loop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
