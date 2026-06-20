# Data Flow

## Wake Inputs

- Settings come from process environment and `.env`.
- The model receives the maker prompt and native tool schemas.
- The sandbox receives no OpenRouter API key and no Maker Place mount.

## Model Response Loop

1. The controller calls the selected model.
2. If the call fails, configured fallback models are tried.
3. The controller records a `model_response` event with response metadata.
4. Text content is summarized and recorded.
5. Tool calls are normalized and executed in order.
6. Tool results are appended to the conversation as tool messages.

## Tool Execution

- `shell`: runs `bash -lc COMMAND` inside the active Docker sandbox at `/world`.
- `write_file`: writes UTF-8 text to a relative path under `/world`.
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
