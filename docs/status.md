# Project Status

This file is the compact source of truth for current Maker behavior.

## Implemented

- Python controller commands: `python3 controller.py run-once` and
  `python3 controller.py loop`.
- Shell wrappers for run-once, start, stop, watch events, show wakes, inspect
  `/world`, and reset the Docker world volume.
- Docker sandbox lifecycle with a disposable container per wake and one
  persistent Docker named volume mounted at `/world`.
- Sandbox command output decoding replaces malformed UTF-8 byte sequences so
  truncated previews cannot crash a wake.
- Maker Place observation files under `maker-place/`: event log, wake summaries,
  world snapshots, optional raw tool outputs, controller pid/log, stop file, and
  wake lock.
- Wake lock behavior that skips a new wake while another wake is active.
- Model clients for OpenRouter, Ollama, and a local mock model.
- Model fallback attempts for the configured provider.
- Native tool schemas for `shell`, `write_file`, `append_file`, `list_files`,
  `read_file`, `search`, `fetch`, and `sleep_or_finish`.
- `list_files` can optionally include bounded newest-file previews when
  `LIST_FILES_PREVIEW_CHARS` is set.
- `write_file`/`append_file` calls with content but no path are preserved under
  deterministic per-wake `_finn/` fallback files with semantic filename slugs
  when possible, instead of dropping the content.
- If `MODEL_TOOL_CHOICE=function:write_file` or `function:append_file` is
  configured and a provider returns text instead of the requested file tool,
  the controller preserves that text through the requested file tool.
- First-turn tool choice can be enforced by the controller when a provider
  ignores the requested tool choice: unset arguments synthesize a safe root
  `function:list_files`, and `FIRST_MODEL_TOOL_ARGS_JSON` can provide targeted
  arguments for a configured first tool.
- Optional shell command normalization can repair common model punctuation
  mistakes such as `/cd` and comma-separated shell commands when explicitly
  enabled.
- Repeated text-only model responses end the wake after three consecutive
  responses without tool calls.
- `fetch` blocks localhost, private, link-local, multicast, reserved,
  unspecified, and metadata-style targets before fetching.
- Go CLI commands for start, stop, status, events, wakes, show, world, doctor,
  Ollama model probing, response counting, wake evaluation, and dashboard
  rendering.
- Dashboard rendering shows runtime state, the current or latest wake, work
  accomplished, recent wakes, recent events, and colorized terminal output.
- Pytest coverage for controller units, tool blocking, file-write tools,
  scripts, CLI behavior, and Docker-backed sandbox behavior.

## Partial

- `go run ./cmd/maker probe-model` only supports `--provider ollama`.
- Search uses DuckDuckGo HTML parsing and returns a small parsed result list.
- Context usage is estimated from serialized message/tool bytes divided by four.
- Docker Compose configuration exists, but the repo tests exercise the Python
  controller and Docker sandbox directly rather than the compose service.
- Controller `fetch` has network blocking, but `shell` inside the sandbox can
  still make broad network calls when Docker allows it.

## Planned

- No verified roadmap file exists in this repo yet.

## Missing

- No packaged release, installer, or tagged version.
- No HTTP API server.
- No persistent service manager file such as systemd or launchd.
- No authenticated multi-user boundary.
- No OpenRouter model probe command in the Go CLI.
- No checked-in generated Maker Place history except `maker-place/.gitkeep`.

## Needs Verification

- Current OpenRouter free model capability and fallback quality.
- Current Ollama model availability on the host.
- Docker Compose loop behavior against the host Docker socket.
- Long-running controller loop behavior outside the unit and integration tests.

## Related

- [Docs map](map.md)
- [Missing features](todo/missing-features.md)
- [Needs verification](todo/needs-verification.md)
