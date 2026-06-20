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


def safe_world_relative_path(value: Any) -> str:
    raw = str(value)
    if not raw.strip():
        raise ValueError("path is required")
    if "\x00" in raw:
        raise ValueError("path cannot contain NUL bytes")
    path = PurePosixPath(raw)
    if path.is_absolute():
        raise ValueError("path must be relative to /world")
    if str(path) == "." or any(part == ".." for part in path.parts):
        raise ValueError("path cannot be current directory or contain ..")
    return str(path)


class ToolRunner:
    def __init__(
        self,
        sandbox: Sandbox,
        maker_place: MakerPlace,
        wake_id: str,
        fetch_timeout_seconds: int = 30,
        max_tool_output_chars: int = 20000,
    ):
        self.sandbox = sandbox
        self.maker_place = maker_place
        self.wake_id = wake_id
        self.fetch_timeout_seconds = fetch_timeout_seconds
        self.max_tool_output_chars = max_tool_output_chars

    def run(self, name: str, args: dict[str, Any], call_index: int) -> tuple[dict[str, Any], bool]:
        if name == "shell":
            return self._shell(args, call_index), False
        if name == "write_file":
            return self._write_file(args, call_index), False
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
        command = str(args.get("command", ""))
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

    def _write_file(self, args: dict[str, Any], call_index: int) -> dict[str, Any]:
        try:
            path = safe_world_relative_path(args.get("path", ""))
        except ValueError as exc:
            result = {"ok": False, "error": str(exc)}
            self.maker_place.append_event(
                "tool_call_error",
                self.wake_id,
                tool="write_file",
                arguments=args,
                error=result["error"],
            )
            return result

        content = str(args.get("content", ""))
        append = args.get("append", False) is True
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
            tool="write_file",
            path=path,
            append=append,
            content=summarize_text(content, 1000),
        )
        result = self.sandbox.exec_bash_with_input(command, content)
        summary = result.for_tool(self.max_tool_output_chars)
        if self.maker_place.store_raw_outputs:
            raw_name = f"{call_index:04d}-write_file"
            summary["raw_stdout_path"] = self.maker_place.write_raw_output(self.wake_id, f"{raw_name}.stdout.txt", result.stdout)
            summary["raw_stderr_path"] = self.maker_place.write_raw_output(self.wake_id, f"{raw_name}.stderr.txt", result.stderr)
        self.maker_place.append_event(
            "write_file_result",
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


def tool_result_message(tool_call_id: str, name: str, result: dict[str, Any]) -> dict[str, Any]:
    return {
        "role": "tool",
        "tool_call_id": tool_call_id,
        "name": name,
        "content": json.dumps(result, ensure_ascii=False),
    }
