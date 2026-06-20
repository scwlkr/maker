# Data Flow

## Wake Inputs

- Settings come from process environment and `.env`.
- The model receives the maker prompt and native tool schemas.
- The sandbox receives no OpenRouter API key and no Maker Place mount.

## Model Response Loop

1. The controller calls the selected model.
2. If the call fails, configured fallback models are tried.
3. The controller records a `model_response` event with response metadata.
4. If `FIRST_MODEL_TOOL_CHOICE=function:list_files` was requested and the
   provider ignored it, the controller executes a safe root `list_files` call.
5. Text content is summarized and recorded.
6. If a provider ignores `MODEL_TOOL_CHOICE=function:write_file` or
   `function:append_file` and returns text, the controller preserves that text
   through the requested file tool.
7. Tool calls are normalized and executed in order.
8. Tool results are appended to the conversation as tool messages.

## Tool Execution

- `shell`: runs `bash -lc COMMAND` inside the active Docker sandbox at `/world`.
- `write_file`: writes UTF-8 text to a relative path under `/world`; if a model
  provides content without a path, the controller preserves it in a per-wake
  `_finn/` fallback file.
- `append_file`: appends UTF-8 text to a relative path under `/world`; malformed
  calls with content and no path use the same per-wake fallback behavior.
- `list_files`: lists files and directories under `/world`.
- `read_file`: reads bounded UTF-8 text from a relative file path under
  `/world`.
- `search`: fetches DuckDuckGo HTML search results and parses titles, URLs, and
  snippets.
- `fetch`: fetches public HTTP or HTTPS URLs after blocking local and private
  targets.
- `sleep_or_finish`: marks the wake complete.

## Wake Outputs

- `maker-place/events.jsonl`: JSONL event stream.
- `maker-place/wakes/WAKE_ID.json`: wake summary.
- `maker-place/world-snapshots/WAKE_ID-before.txt`: before snapshot.
- `maker-place/world-snapshots/WAKE_ID-after.txt`: after snapshot.
- `maker-place/raw/WAKE_ID/`: optional raw shell stdout/stderr.
- `/world`: persistent world state in the Docker volume.

## Related

- [Core workflow](../concepts/core-workflow.md)
- [Lifecycle](lifecycle.md)
- [CLI reference](../reference/cli.md)
