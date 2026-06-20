from __future__ import annotations

import contextlib
import difflib
import json
import os
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def make_wake_id() -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{uuid.uuid4().hex[:8]}"


def summarize_text(text: str, max_chars: int = 2000) -> dict[str, Any]:
    encoded = text.encode("utf-8", errors="replace")
    preview = encoded[:max_chars].decode("utf-8", errors="replace")
    return {
        "bytes": len(encoded),
        "truncated": len(encoded) > max_chars,
        "preview": preview,
    }


def diff_summary(before: str, after: str, limit: int = 80) -> dict[str, Any]:
    before_lines = before.splitlines()
    after_lines = after.splitlines()
    diff = list(difflib.unified_diff(before_lines, after_lines, lineterm=""))
    return {
        "before_entries": len(before_lines),
        "after_entries": len(after_lines),
        "changed": before != after,
        "diff_lines": len(diff),
        "diff_preview": diff[:limit],
        "diff_truncated": len(diff) > limit,
    }


@dataclass
class WakeLock:
    maker_place: "MakerPlace"
    acquired: bool

    def release(self) -> None:
        if self.acquired:
            self.maker_place.release_wake_lock()
            self.acquired = False

    def __enter__(self) -> "WakeLock":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.release()


class MakerPlace:
    def __init__(self, root: str | Path = "maker-place", store_raw_outputs: bool = False):
        self.root = Path(root)
        self.events_path = self.root / "events.jsonl"
        self.wakes_dir = self.root / "wakes"
        self.snapshots_dir = self.root / "world-snapshots"
        self.field_notes_dir = self.root / "field-notes"
        self.raw_dir = self.root / "raw"
        self.store_raw_outputs = store_raw_outputs
        self.lock_path = self.root / "wake.lock"
        self.ensure()

    def ensure(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.wakes_dir.mkdir(parents=True, exist_ok=True)
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        self.field_notes_dir.mkdir(parents=True, exist_ok=True)
        if self.store_raw_outputs:
            self.raw_dir.mkdir(parents=True, exist_ok=True)
        if not self.events_path.exists():
            self.events_path.touch()

    def append_event(self, event_type: str, wake_id: str | None = None, **payload: Any) -> dict[str, Any]:
        self.ensure()
        event = {
            "time": utc_now(),
            "type": event_type,
            "wake_id": wake_id,
            **payload,
        }
        with self.events_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
        return event

    def acquire_wake_lock(self, wake_id: str) -> WakeLock:
        self.ensure()
        payload = {
            "wake_id": wake_id,
            "pid": os.getpid(),
            "started_at": utc_now(),
        }
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        try:
            fd = os.open(self.lock_path, flags)
        except FileExistsError:
            existing = self.read_lock()
            self.append_event("wake_skipped_already_running", wake_id, existing_lock=existing)
            return WakeLock(self, False)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, sort_keys=True)
        return WakeLock(self, True)

    def release_wake_lock(self) -> None:
        with contextlib.suppress(FileNotFoundError):
            self.lock_path.unlink()

    def read_lock(self) -> dict[str, Any] | None:
        try:
            return json.loads(self.lock_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    def snapshot_path(self, wake_id: str, label: str) -> Path:
        return self.snapshots_dir / f"{wake_id}-{label}.txt"

    def write_snapshot(self, wake_id: str, label: str, content: str) -> Path:
        self.ensure()
        path = self.snapshot_path(wake_id, label)
        path.write_text(content, encoding="utf-8")
        self.append_event(
            "world_snapshot_written",
            wake_id,
            label=label,
            path=str(path),
            summary=summarize_text(content, 1000),
        )
        return path

    def write_wake_summary(self, wake_id: str, summary: dict[str, Any]) -> Path:
        self.ensure()
        path = self.wakes_dir / f"{wake_id}.json"
        path.write_text(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        self.append_event("wake_summary_written", wake_id, path=str(path))
        return path

    def write_field_note(self, wake_id: str, summary: dict[str, Any]) -> Path:
        self.ensure()
        path = self.field_notes_dir / f"{wake_id}.md"
        path.write_text(format_field_note(summary), encoding="utf-8")
        self.append_event("field_note_written", wake_id, path=str(path))
        return path

    def raw_output_path(self, wake_id: str, name: str) -> Path:
        safe = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in name)
        return self.raw_dir / wake_id / safe

    def write_raw_output(self, wake_id: str, name: str, content: str) -> str | None:
        if not self.store_raw_outputs:
            return None
        path = self.raw_output_path(wake_id, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", errors="replace")
        return str(path)

    def latest_wake_path(self) -> Path | None:
        paths = sorted(self.wakes_dir.glob("*.json"))
        return paths[-1] if paths else None


@contextlib.contextmanager
def timed() -> Iterator[dict[str, float]]:
    start = time.monotonic()
    result = {"elapsed_seconds": 0.0}
    try:
        yield result
    finally:
        result["elapsed_seconds"] = round(time.monotonic() - start, 3)


def format_field_note(summary: dict[str, Any]) -> str:
    wake_id = str(summary.get("wake_id") or "unknown")
    tool_calls = summary.get("tool_calls") if isinstance(summary.get("tool_calls"), list) else []
    model_responses = summary.get("model_responses") if isinstance(summary.get("model_responses"), list) else []
    text_outputs = summary.get("text_outputs") if isinstance(summary.get("text_outputs"), list) else []
    errors = summary.get("errors") if isinstance(summary.get("errors"), list) else []
    diff = summary.get("diff_summary") if isinstance(summary.get("diff_summary"), dict) else {}
    tool_names = [str(call.get("name") or "") for call in tool_calls if isinstance(call, dict)]
    code_calls = [
        call for call in tool_calls
        if isinstance(call, dict) and str(call.get("name") or "") in {"run_script", "shell"}
    ]
    lines = [
        f"# Field Note: {wake_id}",
        "",
        "Observer stance: passive runtime observation. No extra user message was sent to Finn.",
        "",
        "## Specimen",
        "",
        f"- Model provider: {summary.get('model_provider') or 'unknown'}",
        f"- Model: {summary.get('model') or 'unknown'}",
        f"- Start: {summary.get('start_time') or 'unknown'}",
        f"- End: {summary.get('end_time') or 'unknown'}",
        f"- End reason: {summary.get('end_reason') or 'unknown'}",
        "",
        "## Behavioral Trace",
        "",
        f"- Model responses: {len(model_responses)}",
        f"- Text-only observations: {len(text_outputs)}",
        f"- Tool calls: {len(tool_calls)}",
        f"- Tool sequence: {', '.join(name for name in tool_names if name) or 'none'}",
        f"- Code-capable acts: {len(code_calls)}",
        f"- World changed: {'yes' if diff.get('changed') is True else 'no'}",
        f"- World entries: {diff.get('before_entries', 'unknown')} -> {diff.get('after_entries', 'unknown')}",
        "",
        "## Manipulation Evidence",
        "",
    ]
    if tool_calls:
        for call in tool_calls[:12]:
            if not isinstance(call, dict):
                continue
            result = call.get("result") if isinstance(call.get("result"), dict) else {}
            path = result.get("path") or _argument_path(call.get("arguments"))
            status = "ok" if result.get("ok") is True else "not-ok" if result else "unknown"
            detail = f"- #{call.get('index', '?')} {call.get('name') or 'unknown'}: {status}"
            if path:
                detail += f" path={path}"
            lines.append(detail)
        if len(tool_calls) > 12:
            lines.append(f"- Additional tool calls omitted: {len(tool_calls) - 12}")
    else:
        lines.append("- No tool-mediated manipulation was recorded.")
    lines.extend(["", "## World Diff Preview", ""])
    diff_preview = diff.get("diff_preview") if isinstance(diff.get("diff_preview"), list) else []
    if diff_preview:
        lines.append("```diff")
        lines.extend(str(line) for line in diff_preview[:40])
        if diff.get("diff_truncated"):
            lines.append("...")
        lines.append("```")
    else:
        lines.append("No world diff was recorded.")
    if errors:
        lines.extend(["", "## Anomalies", ""])
        lines.extend(f"- {error}" for error in errors[:8])
    return "\n".join(lines) + "\n"


def _argument_path(arguments: Any) -> str | None:
    if not isinstance(arguments, dict):
        return None
    value = arguments.get("path")
    if value is None:
        return None
    return str(value)
