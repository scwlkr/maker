from __future__ import annotations

import html
import ipaddress
import json
import shlex
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import PurePosixPath
from typing import Any

from maker_place import MakerPlace, summarize_text
from sandbox import Sandbox


TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "shell",
            "description": "Run arbitrary bash as root inside /world. The current directory is /world and changes to files under /world persist.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string"},
                },
                "required": ["command"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_script",
            "description": "Write a bash script to a relative path under /world, make it executable, and run it from /world. The script source and files it creates under /world persist.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "script": {"type": "string"},
                },
                "required": ["path", "script"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write UTF-8 text to a relative path under /world. Parent directories are created. Set append to true to append instead of replace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                    "append": {"type": "boolean"},
                },
                "required": ["path", "content"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "append_file",
            "description": "Append UTF-8 text to a relative path under /world. Parent directories are created.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files and directories under /world or a relative directory inside /world.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read UTF-8 text from a relative file path under /world. Output is bounded by the tool output limit.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                },
                "required": ["path"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search",
            "description": "Search the public web and return titles, URLs, snippets, and dates when available.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch",
            "description": "Fetch a public HTTP or HTTPS URL and return status, final URL, content type, and text.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                },
                "required": ["url"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sleep_or_finish",
            "description": "End this wake cycle.",
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    },
]


class BlockedTarget(ValueError):
    pass


def _is_blocked_ip(value: str) -> bool:
    ip = ipaddress.ip_address(value)
    return (
        ip.is_loopback
        or ip.is_private
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def assert_public_http_url(url: str) -> urllib.parse.ParseResult:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise BlockedTarget("only http and https URLs are allowed")
    if not parsed.hostname:
        raise BlockedTarget("URL must include a hostname")
    hostname = parsed.hostname.strip().lower().rstrip(".")
    if hostname in {"localhost", "localhost.localdomain"}:
        raise BlockedTarget("localhost is blocked")
    try:
        if _is_blocked_ip(hostname):
            raise BlockedTarget("private, local, link-local, reserved, and metadata IPs are blocked")
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(hostname, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise BlockedTarget(f"host did not resolve: {hostname}") from exc
    for info in infos:
        ip = info[4][0]
        if _is_blocked_ip(ip):
            raise BlockedTarget(f"blocked resolved address: {ip}")
    return parsed


class BlockingRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        assert_public_http_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_public_url(url: str, timeout: int = 30, max_chars: int = 20000) -> dict[str, Any]:
    parsed = assert_public_http_url(url)
    request = urllib.request.Request(
        parsed.geturl(),
        headers={"User-Agent": "maker-finn-controller/1.0"},
    )
    opener = urllib.request.build_opener(BlockingRedirectHandler)
    started = time.monotonic()
    try:
        with opener.open(request, timeout=timeout) as response:
            raw = response.read(max_chars + 1)
            final_url = response.geturl()
            assert_public_http_url(final_url)
            content_type = response.headers.get("content-type", "")
            text = raw[:max_chars].decode("utf-8", errors="replace")
            return {
                "ok": True,
                "status": response.status,
                "final_url": final_url,
                "content_type": content_type,
                "elapsed_seconds": round(time.monotonic() - started, 3),
                "text": summarize_text(text, max_chars),
            }
    except BlockedTarget:
        raise
    except urllib.error.HTTPError as exc:
        raw = exc.read(max_chars + 1)
        return {
            "ok": False,
            "status": exc.code,
            "final_url": exc.url,
            "content_type": exc.headers.get("content-type", ""),
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "text": summarize_text(raw[:max_chars].decode("utf-8", errors="replace"), max_chars),
        }


class DuckDuckGoParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.results: list[dict[str, str]] = []
        self._in_title = False
        self._in_snippet = False
        self._current: dict[str, str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {key: value or "" for key, value in attrs}
        class_name = attrs_dict.get("class", "")
        if tag == "a" and "result__a" in class_name:
            href = attrs_dict.get("href", "")
            self._current = {"title": "", "url": _unwrap_duck_url(href), "snippet": "", "date": ""}
            self._in_title = True
        elif tag in {"a", "div"} and "result__snippet" in class_name and self._current is not None:
            self._in_snippet = True

    def handle_endtag(self, tag: str) -> None:
        if self._in_title and tag == "a":
            self._in_title = False
            if self._current is not None:
                self.results.append(self._current)
        if self._in_snippet and tag in {"a", "div"}:
            self._in_snippet = False

    def handle_data(self, data: str) -> None:
        if self._current is None:
            return
        if self._in_title:
            self._current["title"] += data.strip()
        elif self._in_snippet:
            existing = self._current.get("snippet", "")
            self._current["snippet"] = (existing + " " + data.strip()).strip()


def _unwrap_duck_url(url: str) -> str:
    parsed = urllib.parse.urlparse(html.unescape(url))
    query = urllib.parse.parse_qs(parsed.query)
    if "uddg" in query:
        return query["uddg"][0]
    return html.unescape(url)


def search_public_web(query: str, timeout: int = 30) -> dict[str, Any]:
    encoded = urllib.parse.urlencode({"q": query})
    url = f"https://duckduckgo.com/html/?{encoded}"
    fetched = fetch_public_url(url, timeout=timeout, max_chars=120000)
    parser = DuckDuckGoParser()
    parser.feed(fetched["text"]["preview"])
    return {
        "ok": fetched["ok"],
        "query": query,
        "results": parser.results[:10],
    }


def safe_world_relative_path(value: Any, *, allow_current: bool = False) -> str:
    raw = str(value).strip()
    if not raw and allow_current:
        raw = "."
    if not raw:
        raise ValueError("path is required")
    if "\x00" in raw:
        raise ValueError("path cannot contain NUL bytes")
    if raw.startswith("/world/"):
        raw = raw.removeprefix("/world/")
    elif raw == "/world":
        if allow_current:
            raw = "."
        else:
            raise ValueError("path must name a file under /world")
    path = PurePosixPath(raw)
    if path.is_absolute():
        raise ValueError("path must be relative to /world")
    if any(part == ".." for part in path.parts):
        raise ValueError("path cannot be current directory or contain ..")
    if str(path) == ".":
        if allow_current:
            return "."
        raise ValueError("path must name a file under /world")
    return str(path)


def safe_default_path_part(value: str, fallback: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in value.strip())
    return safe or fallback


def content_slug_part(content: str, max_length: int = 64) -> str:
    for raw_line in content.splitlines():
        line = raw_line.strip().strip("#*`-=|:[](){}<> ")
        if not line or not any(ch.isalnum() for ch in line):
            continue
        parts: list[str] = []
        previous_was_separator = False
        for ch in line.lower():
            if "a" <= ch <= "z" or "0" <= ch <= "9":
                parts.append(ch)
                previous_was_separator = False
            elif not previous_was_separator:
                parts.append("_")
                previous_was_separator = True
        slug = "".join(parts).strip("_")
        if not slug:
            continue
        if len(slug) > max_length:
            slug = slug[:max_length].rstrip("_")
            boundary = slug.rfind("_")
            if boundary >= max_length // 2:
                slug = slug[:boundary]
        return slug
    return ""


def default_write_path(tool_name: str, wake_id: str, call_index: int, content: str = "") -> str:
    safe_tool_name = safe_default_path_part(tool_name, "tool")
    safe_wake_id = safe_default_path_part(wake_id, "wake")
    slug = content_slug_part(content)
    suffix = f"_{slug}" if slug else ""
    return f"_finn/{safe_wake_id}/{safe_tool_name}_{call_index:04d}{suffix}.md"


NORMALIZABLE_SHELL_COMMANDS = {
    "awk",
    "bash",
    "cat",
    "cd",
    "cp",
    "echo",
    "find",
    "grep",
    "ls",
    "mkdir",
    "mv",
    "printf",
    "python",
    "python3",
    "rm",
    "sed",
    "sh",
    "tee",
    "touch",
}


def _next_shell_word(command: str, index: int) -> tuple[str, int]:
    if index < len(command) and command[index] == "/":
        index += 1
    start = index
    while index < len(command) and (command[index].isalnum() or command[index] in "_-"):
        index += 1
    return command[start:index], start


def normalize_model_shell_command(command: str) -> str:
    """Repair common model shell punctuation mistakes without touching quotes."""
    command = command.strip()
    output: list[str] = []
    quote: str | None = None
    escaped = False
    index = 0
    while index < len(command):
        char = command[index]
        if escaped:
            output.append(char)
            escaped = False
            index += 1
            continue
        if char == "\\":
            output.append(char)
            escaped = True
            index += 1
            continue
        if quote:
            output.append(char)
            if char == quote:
                quote = None
            index += 1
            continue
        if char in {"'", '"'}:
            quote = char
            output.append(char)
            index += 1
            continue
        if char == ",":
            lookahead = index + 1
            while lookahead < len(command) and command[lookahead].isspace():
                lookahead += 1
            word, word_start = _next_shell_word(command, lookahead)
            if word in NORMALIZABLE_SHELL_COMMANDS:
                output.append("; ")
                index = word_start
                continue
        if char == "/":
            previous = "".join(output).rstrip()
            word, _ = _next_shell_word(command, index)
            if word in NORMALIZABLE_SHELL_COMMANDS and (not previous or previous[-1] in ";&|\n"):
                index += 1
                continue
        output.append(char)
        index += 1
    return "".join(output)


def should_default_run_script_path(value: Any, error: str) -> bool:
    raw = str(value).strip()
    if raw in {"", ".", "/world", "/world/"}:
        return True
    if raw.endswith("/") and ".." not in PurePosixPath(raw).parts:
        return True
    return error in {"path is required", "path must name a file under /world"} and not raw


class ToolRunner:
    def __init__(
        self,
        sandbox: Sandbox,
        maker_place: MakerPlace,
        wake_id: str,
        fetch_timeout_seconds: int = 30,
        max_tool_output_chars: int = 20000,
        normalize_shell_commands: bool = False,
        list_files_preview_chars: int = 0,
    ):
        self.sandbox = sandbox
        self.maker_place = maker_place
        self.wake_id = wake_id
        self.fetch_timeout_seconds = fetch_timeout_seconds
        self.max_tool_output_chars = max_tool_output_chars
        self.normalize_shell_commands = normalize_shell_commands
        self.list_files_preview_chars = max(0, list_files_preview_chars)

    def run(self, name: str, args: dict[str, Any], call_index: int) -> tuple[dict[str, Any], bool]:
        if name == "shell":
            return self._shell(args, call_index), False
        if name == "run_script":
            return self._run_script(args, call_index), False
        if name == "write_file":
            return self._write_file(args, call_index), False
        if name == "append_file":
            return self._write_file(args, call_index, tool_name="append_file", force_append=True), False
        if name == "list_files":
            return self._list_files(args, call_index), False
        if name == "read_file":
            return self._read_file(args, call_index), False
        if name == "search":
            return self._search(args), False
        if name == "fetch":
            return self._fetch(args), False
        if name == "sleep_or_finish":
            result = {"ok": True, "finished": True}
            self.maker_place.append_event("tool_call", self.wake_id, tool=name, arguments={})
            return result, True
        result = {"ok": False, "error": f"unknown tool: {name}"}
        self.maker_place.append_event("tool_call_error", self.wake_id, tool=name, arguments=args, error=result["error"])
        return result, False

    def _shell(self, args: dict[str, Any], call_index: int) -> dict[str, Any]:
        original_command = str(args.get("command", ""))
        command = normalize_model_shell_command(original_command) if self.normalize_shell_commands else original_command
        if command != original_command:
            self.maker_place.append_event(
                "shell_command_normalized",
                self.wake_id,
                original_command=original_command,
                command=command,
            )
        self.maker_place.append_event("tool_call", self.wake_id, tool="shell", command=command)
        result = self.sandbox.exec_bash(command)
        summary = result.for_tool(self.max_tool_output_chars)
        if self.maker_place.store_raw_outputs:
            raw_name = f"{call_index:04d}-shell"
            summary["raw_stdout_path"] = self.maker_place.write_raw_output(self.wake_id, f"{raw_name}.stdout.txt", result.stdout)
            summary["raw_stderr_path"] = self.maker_place.write_raw_output(self.wake_id, f"{raw_name}.stderr.txt", result.stderr)
        self.maker_place.append_event(
            "shell_result",
            self.wake_id,
            command=command,
            exit_code=result.exit_code,
            timed_out=result.timed_out,
            elapsed_seconds=result.elapsed_seconds,
            stdout=summary["stdout"],
            stderr=summary["stderr"],
        )
        return {"ok": result.exit_code == 0 and not result.timed_out, **summary}

    def _run_script(self, args: dict[str, Any], call_index: int) -> dict[str, Any]:
        script = str(args.get("script", ""))
        try:
            path = safe_world_relative_path(args.get("path", ""))
        except ValueError as exc:
            if script and should_default_run_script_path(args.get("path", ""), str(exc)):
                path = default_write_path("run_script", self.wake_id, call_index, script)
                if path.endswith(".md"):
                    path = path[:-3] + ".sh"
                self.maker_place.append_event(
                    "run_script_path_defaulted",
                    self.wake_id,
                    tool="run_script",
                    path=path,
                    arguments=args,
                )
            else:
                result = {"ok": False, "error": str(exc)}
                self.maker_place.append_event(
                    "tool_call_error",
                    self.wake_id,
                    tool="run_script",
                    arguments=args,
                    error=result["error"],
                )
                return result

        try:
            safe_world_relative_path(path)
        except ValueError as exc:
            result = {"ok": False, "error": str(exc)}
            self.maker_place.append_event(
                "tool_call_error",
                self.wake_id,
                tool="run_script",
                arguments=args,
                error=result["error"],
            )
            return result

        command = (
            f"target={shlex.quote(path)}; "
            'mkdir -p -- "$(dirname -- "$target")" && '
            'cat > "$target" && '
            'chmod +x "$target" && '
            'bash "$target"'
        )
        self.maker_place.append_event(
            "tool_call",
            self.wake_id,
            tool="run_script",
            path=path,
            script=summarize_text(script, 1000),
        )
        result = self.sandbox.exec_bash_with_input(command, script)
        summary = result.for_tool(self.max_tool_output_chars)
        if self.maker_place.store_raw_outputs:
            raw_name = f"{call_index:04d}-run_script"
            summary["raw_stdout_path"] = self.maker_place.write_raw_output(
                self.wake_id,
                f"{raw_name}.stdout.txt",
                result.stdout,
            )
            summary["raw_stderr_path"] = self.maker_place.write_raw_output(
                self.wake_id,
                f"{raw_name}.stderr.txt",
                result.stderr,
            )
        listing = self._world_listing()
        self.maker_place.append_event(
            "run_script_result",
            self.wake_id,
            path=path,
            exit_code=result.exit_code,
            timed_out=result.timed_out,
            elapsed_seconds=result.elapsed_seconds,
            stdout=summary["stdout"],
            stderr=summary["stderr"],
            world_listing=listing,
        )
        return {
            "ok": result.exit_code == 0 and not result.timed_out,
            "path": path,
            "bytes": len(script.encode("utf-8", errors="replace")),
            "world_listing": listing,
            **summary,
        }

    def _world_listing(self) -> dict[str, Any]:
        command = (
            'if [ -z "$(find . -mindepth 1 -maxdepth 1 -print -quit)" ]; then exit 0; fi; '
            'find . -mindepth 1 -maxdepth 3 -printf "%y %s %p\\n" | sort | head -n 200'
        )
        result = self.sandbox.exec_bash(command)
        if result.exit_code != 0 or result.timed_out:
            detail = result.stderr or result.stdout
            return {
                "ok": False,
                "error": summarize_text(detail, self.max_tool_output_chars),
            }
        return {
            "ok": True,
            "listing": summarize_text(result.stdout, self.max_tool_output_chars),
        }

    def _write_file(
        self,
        args: dict[str, Any],
        call_index: int,
        *,
        tool_name: str = "write_file",
        force_append: bool | None = None,
    ) -> dict[str, Any]:
        content = str(args.get("content", ""))
        try:
            path = safe_world_relative_path(args.get("path", ""))
        except ValueError as exc:
            if str(exc) == "path is required" and content:
                path = default_write_path(tool_name, self.wake_id, call_index, content)
                self.maker_place.append_event(
                    "write_file_path_defaulted",
                    self.wake_id,
                    tool=tool_name,
                    path=path,
                    arguments=args,
                )
            else:
                result = {"ok": False, "error": str(exc)}
                self.maker_place.append_event(
                    "tool_call_error",
                    self.wake_id,
                    tool=tool_name,
                    arguments=args,
                    error=result["error"],
                )
                return result

        try:
            safe_world_relative_path(path)
        except ValueError as exc:
            result = {"ok": False, "error": str(exc)}
            self.maker_place.append_event(
                "tool_call_error",
                self.wake_id,
                tool=tool_name,
                arguments=args,
                error=result["error"],
            )
            return result

        append = force_append if force_append is not None else args.get("append", False) is True
        operator = ">>" if append else ">"
        command = (
            f"target={shlex.quote(path)}; "
            'mkdir -p -- "$(dirname -- "$target")" && '
            f'cat {operator} "$target" && '
            'printf "%s\\n" "$target"'
        )
        self.maker_place.append_event(
            "tool_call",
            self.wake_id,
            tool=tool_name,
            path=path,
            append=append,
            content=summarize_text(content, 1000),
        )
        result = self.sandbox.exec_bash_with_input(command, content)
        summary = result.for_tool(self.max_tool_output_chars)
        if self.maker_place.store_raw_outputs:
            raw_name = f"{call_index:04d}-{tool_name}"
            summary["raw_stdout_path"] = self.maker_place.write_raw_output(self.wake_id, f"{raw_name}.stdout.txt", result.stdout)
            summary["raw_stderr_path"] = self.maker_place.write_raw_output(self.wake_id, f"{raw_name}.stderr.txt", result.stderr)
        self.maker_place.append_event(
            f"{tool_name}_result",
            self.wake_id,
            path=path,
            append=append,
            exit_code=result.exit_code,
            timed_out=result.timed_out,
            elapsed_seconds=result.elapsed_seconds,
            stdout=summary["stdout"],
            stderr=summary["stderr"],
        )
        return {
            "ok": result.exit_code == 0 and not result.timed_out,
            "path": path,
            "bytes": len(content.encode("utf-8", errors="replace")),
            "append": append,
            **summary,
        }

    def _list_files(self, args: dict[str, Any], call_index: int) -> dict[str, Any]:
        try:
            path = safe_world_relative_path(args.get("path", "."), allow_current=True)
        except ValueError as exc:
            result = {"ok": False, "error": str(exc)}
            self.maker_place.append_event(
                "tool_call_error",
                self.wake_id,
                tool="list_files",
                arguments=args,
                error=result["error"],
            )
            return result

        command = (
            f"target={shlex.quote(path)}; "
            'if [ ! -e "$target" ]; then printf "path not found: %s\\n" "$target" >&2; exit 1; fi; '
            'if [ -f "$target" ]; then '
            'find "$target" -maxdepth 0 -printf "%y %s %p\\n"; '
            "else "
            'find "$target" -mindepth 1 -maxdepth 3 -printf "%y %s %p\\n" | sort | head -n 200; '
            "fi"
        )
        preview_file_limit = 0
        if self.list_files_preview_chars > 0:
            preview_chars = min(self.list_files_preview_chars, self.max_tool_output_chars)
            preview_file_limit = max(1, min(24, self.max_tool_output_chars // max(1, preview_chars)))
            command += (
                f"; preview_chars={preview_chars}; "
                f"preview_file_limit={preview_file_limit}; "
                'printf "\\n# File previews\\n"; '
                'if [ -f "$target" ]; then '
                'find "$target" -maxdepth 0 -type f; '
                "else "
                'find "$target" -mindepth 1 -maxdepth 3 -type f -printf "%T@ %p\\n" | '
                'sort -rn | head -n "$preview_file_limit" | cut -d " " -f2-; '
                "fi | "
                'while IFS= read -r file; do '
                'printf "\\n## %s\\n" "$file"; '
                'head -c "$preview_chars" -- "$file"; '
                'printf "\\n"; '
                "done"
            )
        self.maker_place.append_event(
            "tool_call",
            self.wake_id,
            tool="list_files",
            path=path,
            preview_chars=self.list_files_preview_chars,
            preview_file_limit=preview_file_limit,
        )
        result = self.sandbox.exec_bash(command)
        summary = result.for_tool(self.max_tool_output_chars)
        if self.maker_place.store_raw_outputs:
            raw_name = f"{call_index:04d}-list_files"
            summary["raw_stdout_path"] = self.maker_place.write_raw_output(self.wake_id, f"{raw_name}.stdout.txt", result.stdout)
            summary["raw_stderr_path"] = self.maker_place.write_raw_output(self.wake_id, f"{raw_name}.stderr.txt", result.stderr)
        self.maker_place.append_event(
            "list_files_result",
            self.wake_id,
            path=path,
            exit_code=result.exit_code,
            timed_out=result.timed_out,
            elapsed_seconds=result.elapsed_seconds,
            stdout=summary["stdout"],
            stderr=summary["stderr"],
        )
        return {
            "ok": result.exit_code == 0 and not result.timed_out,
            "path": path,
            "listing": summary["stdout"],
            **summary,
        }

    def _read_file(self, args: dict[str, Any], call_index: int) -> dict[str, Any]:
        try:
            path = safe_world_relative_path(args.get("path", ""))
        except ValueError as exc:
            result = {"ok": False, "error": str(exc)}
            self.maker_place.append_event(
                "tool_call_error",
                self.wake_id,
                tool="read_file",
                arguments=args,
                error=result["error"],
            )
            return result

        command = (
            f"target={shlex.quote(path)}; "
            'if [ ! -f "$target" ]; then printf "not a regular file: %s\\n" "$target" >&2; exit 1; fi; '
            f'head -c {self.max_tool_output_chars + 1} -- "$target"'
        )
        self.maker_place.append_event("tool_call", self.wake_id, tool="read_file", path=path)
        result = self.sandbox.exec_bash(command)
        summary = result.for_tool(self.max_tool_output_chars)
        if self.maker_place.store_raw_outputs:
            raw_name = f"{call_index:04d}-read_file"
            summary["raw_stdout_path"] = self.maker_place.write_raw_output(self.wake_id, f"{raw_name}.stdout.txt", result.stdout)
            summary["raw_stderr_path"] = self.maker_place.write_raw_output(self.wake_id, f"{raw_name}.stderr.txt", result.stderr)
        self.maker_place.append_event(
            "read_file_result",
            self.wake_id,
            path=path,
            exit_code=result.exit_code,
            timed_out=result.timed_out,
            elapsed_seconds=result.elapsed_seconds,
            stdout=summary["stdout"],
            stderr=summary["stderr"],
        )
        return {
            "ok": result.exit_code == 0 and not result.timed_out,
            "path": path,
            "text": summary["stdout"],
            **summary,
        }

    def _search(self, args: dict[str, Any]) -> dict[str, Any]:
        query = str(args.get("query", ""))
        self.maker_place.append_event("tool_call", self.wake_id, tool="search", query=query)
        try:
            result = search_public_web(query, timeout=self.fetch_timeout_seconds)
        except Exception as exc:
            result = {"ok": False, "query": query, "error": str(exc)}
        self.maker_place.append_event("search_result", self.wake_id, query=query, result=result)
        return result

    def _fetch(self, args: dict[str, Any]) -> dict[str, Any]:
        url = str(args.get("url", ""))
        self.maker_place.append_event("tool_call", self.wake_id, tool="fetch", url=url)
        try:
            result = fetch_public_url(url, timeout=self.fetch_timeout_seconds, max_chars=self.max_tool_output_chars)
        except BlockedTarget as exc:
            result = {"ok": False, "blocked": True, "url": url, "error": str(exc)}
        except Exception as exc:
            result = {"ok": False, "url": url, "error": str(exc)}
        self.maker_place.append_event("fetch_result", self.wake_id, url=url, result=result)
        return result


def tool_result_message(
    tool_call_id: str,
    name: str,
    result: dict[str, Any],
    mode: str = "json",
) -> dict[str, Any]:
    normalized_mode = mode.strip().lower().replace("_", "-")
    if normalized_mode == "read-file-preview" and name == "read_file":
        text = result.get("text")
        if isinstance(text, dict) and isinstance(text.get("preview"), str):
            content = text["preview"]
        else:
            content = json.dumps(result, ensure_ascii=False)
    elif normalized_mode in {"json", "read-file-preview"}:
        content = json.dumps(result, ensure_ascii=False)
    else:
        raise ValueError(f"unknown TOOL_RESULT_MESSAGE_MODE: {mode}")
    return {
        "role": "tool",
        "tool_call_id": tool_call_id,
        "name": name,
        "content": content,
    }
