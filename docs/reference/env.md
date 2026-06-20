# Environment Variables

Settings come from process environment and `.env`.

## Model Provider

| Variable | Default | Meaning |
| --- | --- | --- |
| `MODEL_PROVIDER` | `openrouter` | `ollama` selects Ollama; other values use OpenRouter |
| `OPENROUTER_API_KEY` | empty | Required for OpenRouter unless `MOCK_MODEL=1` |
| `MODEL` | `openrouter/free` in controller, example uses `nex-agi/nex-n2-pro:free` | OpenRouter primary model |
| `MODEL_FALLBACKS` | empty in controller | Comma-separated OpenRouter fallback models |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama base URL |
| `OLLAMA_MODEL` | `llama3.1:8b` | Ollama primary model |
| `OLLAMA_FALLBACKS` | `qwen3.5:9b` | Comma-separated Ollama fallback models |
| `OLLAMA_OPTIONS_JSON` | empty | Optional JSON object passed as Ollama `options` |
| `MOCK_MODEL` | `0` | `1` uses the local mock model client |
| `MOCK_MODEL_STEPS` | built-in two-step mock | JSON steps for the mock model |
| `MODEL_MAX_TOKENS` | empty | Optional positive `max_tokens` value for OpenRouter requests |
| `MODEL_TOOL_CHOICE` | empty | Optional provider `tool_choice`; supports `auto`, `none`, `required`, or `function:NAME`. If `function:write_file` or `function:append_file` is ignored and the model returns text, the controller preserves that text through the requested file tool. |
| `FIRST_MODEL_TOOL_CHOICE` | empty | Optional provider `tool_choice` override for only the first model request in a wake; supports the same values as `MODEL_TOOL_CHOICE`. If a provider ignores an enforceable first tool choice, the controller executes that first tool call itself. |
| `FIRST_MODEL_TOOL_ARGS_JSON` | empty | Optional JSON object used as arguments when the controller enforces `FIRST_MODEL_TOOL_CHOICE`; unset keeps the safe default root `list_files` behavior. |
| `FIRST_MODEL_TOOL_STRICT` | `0` | `1` replaces the first returned model tool call with the enforceable configured `FIRST_MODEL_TOOL_CHOICE`, instead of only enforcing when the model returns no tool calls. |
| `TOOL_SCHEMA_MODE` | `all` | `all` exposes all native tools; `shell-only` exposes only `shell`; `write-only` exposes only `write_file`; `files` exposes `list_files`, `read_file`, `write_file`, and `append_file` |
| `POST_FIRST_TOOL_SCHEMA_MODE` | empty | Optional tool schema mode used after the first model request in a wake; useful for an enforced first read/list followed by narrower write-only continuation. |
| `TOOL_RESULT_MESSAGE_MODE` | `json` | Tool result format sent back to the model. `json` sends the full structured result; `read-file-preview` sends only the file preview for `read_file` results while preserving structured Maker Place events. |
| `TEXT_TOOL_CALL_MODE` | `disabled` | `exact-json` executes assistant text that is exactly a JSON tool call object for an advertised tool; `exact-literal` also accepts Python literal objects; `fenced-json` and `fenced-literal` unwrap a whole-message code fence before parsing |

## Wake And Tool Limits

| Variable | Default | Meaning |
| --- | --- | --- |
| `WAKE_INTERVAL_SECONDS` | `300` | Loop sleep interval between wakes |
| `CONTEXT_LIMIT_TOKENS` | `120000` | Approximate context limit |
| `MODEL_TIMEOUT_SECONDS` | `60` | Model request timeout |
| `FETCH_TIMEOUT_SECONDS` | `30` | Fetch and search timeout |
| `SHELL_TIMEOUT_SECONDS` | `60` | Sandbox shell command timeout |
| `MAX_TOOL_OUTPUT_CHARS` | `20000` | Tool stdout/stderr truncation limit |
| `LIST_FILES_PREVIEW_CHARS` | `0` | Optional per-file preview size for newest files in `list_files`; `0` keeps listings name-only |
| `TEXT_ONLY_DELAY_SECONDS` | `2` | Delay after a text-only model response |
| `MAX_CONSECUTIVE_TEXT_ONLY_RESPONSES` | `3` | Positive cap on consecutive text-only model responses before ending the wake |
| `MAX_TOOL_CALLS_PER_WAKE` | `80` | Positive cap on executed tool calls in one wake |
| `NORMALIZE_SHELL_COMMANDS` | `0` | `1` repairs common model shell punctuation mistakes outside quotes, such as `/cd` and comma-separated command sequences |

## Storage And Sandbox

| Variable | Default | Meaning |
| --- | --- | --- |
| `MAKER_PLACE_DIR` | `maker-place` | Observation directory |
| `STORE_RAW_OUTPUTS` | `0` | `1` stores raw shell stdout/stderr under Maker Place |
| `WORLD_VOLUME` | `maker_finn_world` | Docker volume mounted at `/world` |
| `SANDBOX_IMAGE` | `maker-finn-sandbox:latest` | Docker sandbox image |
| `SANDBOX_CPUS` | `1.0` | Docker CPU limit |
| `SANDBOX_MEMORY` | `512m` | Docker memory limit |
| `SANDBOX_PIDS_LIMIT` | `256` | Docker pids limit |

## Related

- [Configuration model](../concepts/configuration.md)
- [Config files](config.md)
- [Troubleshooting](../guides/troubleshooting.md)
