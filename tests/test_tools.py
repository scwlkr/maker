from __future__ import annotations

import socket
from pathlib import Path

import pytest

from maker_place import MakerPlace
from sandbox import CommandResult
from tools import (
    BlockedTarget,
    ToolRunner,
    assert_public_http_url,
    fetch_public_url,
    normalize_model_shell_command,
    safe_world_relative_path,
)


class FakeWriteSandbox:
    def __init__(self) -> None:
        self.command = ""
        self.input_text = ""

    def exec_bash(self, command: str, timeout: int | None = None) -> CommandResult:
        self.command = command
        return CommandResult(0, "f 12 ./people/ada.md\n", "", False, 0.01)

    def exec_bash_with_input(
        self,
        command: str,
        input_text: str,
        timeout: int | None = None,
    ) -> CommandResult:
        self.command = command
        self.input_text = input_text
        return CommandResult(0, "people/ada.md\n", "", False, 0.01)


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


def test_safe_world_relative_path_rejects_unsafe_paths() -> None:
    assert safe_world_relative_path("people/ada.md") == "people/ada.md"
    assert safe_world_relative_path("/world/people/ada.md") == "people/ada.md"
    with pytest.raises(ValueError):
        safe_world_relative_path("/tmp/people/ada.md")
    with pytest.raises(ValueError):
        safe_world_relative_path("/world")
    with pytest.raises(ValueError):
        safe_world_relative_path("../ada.md")
    with pytest.raises(ValueError):
        safe_world_relative_path("")


def test_write_file_tool_uses_stdin_and_records_result(tmp_path: Path) -> None:
    sandbox = FakeWriteSandbox()
    maker = MakerPlace(tmp_path / "maker-place")
    runner = ToolRunner(sandbox=sandbox, maker_place=maker, wake_id="wake-one")

    result, should_finish = runner.run(
        "write_file",
        {"path": "people/ada.md", "content": "hello\nworld\n"},
        1,
    )

    assert should_finish is False
    assert result["ok"] is True
    assert result["path"] == "people/ada.md"
    assert result["bytes"] == len("hello\nworld\n".encode())
    assert sandbox.input_text == "hello\nworld\n"
    assert "cat > \"$target\"" in sandbox.command
    events = (tmp_path / "maker-place" / "events.jsonl").read_text()
    assert "write_file_result" in events


def test_shell_command_normalization_is_opt_in(tmp_path: Path) -> None:
    sandbox = FakeWriteSandbox()
    maker = MakerPlace(tmp_path / "maker-place")
    runner = ToolRunner(sandbox=sandbox, maker_place=maker, wake_id="wake-one")

    runner.run(
        "shell",
        {"command": '/cd /world; mkdir world inhabitants, echo "you must name yourselves" > inhabitants/file.txt, /mkdir world'},
        1,
    )

    assert sandbox.command == '/cd /world; mkdir world inhabitants, echo "you must name yourselves" > inhabitants/file.txt, /mkdir world'
    events = (tmp_path / "maker-place" / "events.jsonl").read_text()
    assert "shell_command_normalized" not in events


def test_shell_command_normalization_repairs_common_model_punctuation(tmp_path: Path) -> None:
    sandbox = FakeWriteSandbox()
    maker = MakerPlace(tmp_path / "maker-place")
    runner = ToolRunner(
        sandbox=sandbox,
        maker_place=maker,
        wake_id="wake-one",
        normalize_shell_commands=True,
    )

    runner.run(
        "shell",
        {"command": '/cd /world; mkdir world inhabitants, echo "you must name yourselves" > inhabitants/file.txt, /mkdir world'},
        1,
    )

    assert sandbox.command == 'cd /world; mkdir world inhabitants; echo "you must name yourselves" > inhabitants/file.txt; mkdir world'
    events = (tmp_path / "maker-place" / "events.jsonl").read_text()
    assert "shell_command_normalized" in events


def test_shell_command_normalization_preserves_quoted_text() -> None:
    command = 'echo "keep this, /mkdir literal"; /mkdir people, touch people/ada.md'

    assert normalize_model_shell_command(command) == 'echo "keep this, /mkdir literal"; mkdir people; touch people/ada.md'


def test_write_file_tool_defaults_missing_path_when_content_exists(tmp_path: Path) -> None:
    sandbox = FakeWriteSandbox()
    maker = MakerPlace(tmp_path / "maker-place")
    runner = ToolRunner(sandbox=sandbox, maker_place=maker, wake_id="wake-one")

    result, should_finish = runner.run(
        "write_file",
        {"content": "orphaned text\n"},
        7,
    )

    assert should_finish is False
    assert result["ok"] is True
    assert result["path"] == "_finn/wake-one/write_file_0007_orphaned_text.md"
    assert sandbox.input_text == "orphaned text\n"
    assert "cat > \"$target\"" in sandbox.command
    events = (tmp_path / "maker-place" / "events.jsonl").read_text()
    assert "write_file_path_defaulted" in events
    assert "write_file_result" in events


def test_write_file_tool_defaults_missing_path_with_content_slug(tmp_path: Path) -> None:
    sandbox = FakeWriteSandbox()
    maker = MakerPlace(tmp_path / "maker-place")
    runner = ToolRunner(sandbox=sandbox, maker_place=maker, wake_id="wake-one")

    result, _ = runner.run(
        "write_file",
        {"content": "# Controlled Emergence Protocol\nDetails\n"},
        7,
    )

    assert result["ok"] is True
    assert result["path"] == "_finn/wake-one/write_file_0007_controlled_emergence_protocol.md"


def test_defaulted_write_paths_include_wake_id_to_avoid_collisions(tmp_path: Path) -> None:
    maker = MakerPlace(tmp_path / "maker-place")
    first = ToolRunner(sandbox=FakeWriteSandbox(), maker_place=maker, wake_id="wake-one")
    second = ToolRunner(sandbox=FakeWriteSandbox(), maker_place=maker, wake_id="wake-two")

    first_result, _ = first.run("write_file", {"content": "same\n"}, 7)
    second_result, _ = second.run("write_file", {"content": "same\n"}, 7)

    assert first_result["path"] == "_finn/wake-one/write_file_0007_same.md"
    assert second_result["path"] == "_finn/wake-two/write_file_0007_same.md"
    assert first_result["path"] != second_result["path"]


def test_append_file_tool_uses_stdin_and_records_result(tmp_path: Path) -> None:
    sandbox = FakeWriteSandbox()
    maker = MakerPlace(tmp_path / "maker-place")
    runner = ToolRunner(sandbox=sandbox, maker_place=maker, wake_id="wake-one")

    result, should_finish = runner.run(
        "append_file",
        {"path": "people/ada.md", "content": "again\n"},
        1,
    )

    assert should_finish is False
    assert result["ok"] is True
    assert result["path"] == "people/ada.md"
    assert result["append"] is True
    assert sandbox.input_text == "again\n"
    assert "cat >> \"$target\"" in sandbox.command
    events = (tmp_path / "maker-place" / "events.jsonl").read_text()
    assert "append_file_result" in events


def test_write_file_tool_rejects_unsafe_path(tmp_path: Path) -> None:
    sandbox = FakeWriteSandbox()
    maker = MakerPlace(tmp_path / "maker-place")
    runner = ToolRunner(sandbox=sandbox, maker_place=maker, wake_id="wake-one")

    result, should_finish = runner.run(
        "write_file",
        {"path": "../outside.md", "content": "no"},
        1,
    )

    assert should_finish is False
    assert result["ok"] is False
    assert "path cannot" in result["error"]
    assert sandbox.command == ""


def test_list_files_tool_allows_world_root_and_records_result(tmp_path: Path) -> None:
    sandbox = FakeWriteSandbox()
    maker = MakerPlace(tmp_path / "maker-place")
    runner = ToolRunner(sandbox=sandbox, maker_place=maker, wake_id="wake-one")

    result, should_finish = runner.run("list_files", {"path": "/world"}, 1)

    assert should_finish is False
    assert result["ok"] is True
    assert result["path"] == "."
    assert result["listing"]["preview"] == "f 12 ./people/ada.md\n"
    assert "find \"$target\" -mindepth 1 -maxdepth 3" in sandbox.command
    assert "File previews" not in sandbox.command
    events = (tmp_path / "maker-place" / "events.jsonl").read_text()
    assert "list_files_result" in events


def test_list_files_tool_can_include_file_previews(tmp_path: Path) -> None:
    sandbox = FakeWriteSandbox()
    maker = MakerPlace(tmp_path / "maker-place")
    runner = ToolRunner(
        sandbox=sandbox,
        maker_place=maker,
        wake_id="wake-one",
        list_files_preview_chars=80,
    )

    result, should_finish = runner.run("list_files", {"path": "."}, 1)

    assert should_finish is False
    assert result["ok"] is True
    assert "File previews" in sandbox.command
    assert "head -c \"$preview_chars\" -- \"$file\"" in sandbox.command
    assert "preview_chars=80" in sandbox.command
    assert "preview_file_limit=24" in sandbox.command
    assert 'find "$target" -mindepth 1 -maxdepth 3 -type f -printf "%T@ %p\\n"' in sandbox.command
    assert 'sort -rn | head -n "$preview_file_limit"' in sandbox.command
    events = (tmp_path / "maker-place" / "events.jsonl").read_text()
    assert '"preview_chars": 80' in events
    assert '"preview_file_limit": 24' in events


def test_read_file_tool_reads_bounded_path_and_records_result(tmp_path: Path) -> None:
    sandbox = FakeWriteSandbox()
    maker = MakerPlace(tmp_path / "maker-place")
    runner = ToolRunner(sandbox=sandbox, maker_place=maker, wake_id="wake-one", max_tool_output_chars=12)

    result, should_finish = runner.run("read_file", {"path": "/world/people/ada.md"}, 1)

    assert should_finish is False
    assert result["ok"] is True
    assert result["path"] == "people/ada.md"
    assert result["text"]["preview"] == "f 12 ./peopl"
    assert result["text"]["truncated"] is True
    assert "head -c 13" in sandbox.command
    events = (tmp_path / "maker-place" / "events.jsonl").read_text()
    assert "read_file_result" in events


def test_read_file_tool_rejects_unsafe_path(tmp_path: Path) -> None:
    sandbox = FakeWriteSandbox()
    maker = MakerPlace(tmp_path / "maker-place")
    runner = ToolRunner(sandbox=sandbox, maker_place=maker, wake_id="wake-one")

    result, should_finish = runner.run("read_file", {"path": "/world/../outside.md"}, 1)

    assert should_finish is False
    assert result["ok"] is False
    assert "path cannot" in result["error"]
    assert sandbox.command == ""
