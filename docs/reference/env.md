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
| `MODEL_TOOL_CHOICE` | empty | Optional provider `tool_choice`; supports `auto`, `none`, `required`, or `function:NAME` |
| `TOOL_SCHEMA_MODE` | `all` | `all` exposes all native tools; `shell-only` exposes only `shell` |
| `TEXT_TOOL_CALL_MODE` | `disabled` | `exact-json` executes assistant text that is exactly a JSON tool call object for an advertised tool |

## Wake And Tool Limits

| Variable | Default | Meaning |
| --- | --- | --- |
| `WAKE_INTERVAL_SECONDS` | `300` | Loop sleep interval between wakes |
| `CONTEXT_LIMIT_TOKENS` | `120000` | Approximate context limit |
| `MODEL_TIMEOUT_SECONDS` | `60` | Model request timeout |
| `FETCH_TIMEOUT_SECONDS` | `30` | Fetch and search timeout |
| `SHELL_TIMEOUT_SECONDS` | `60` | Sandbox shell command timeout |
| `MAX_TOOL_OUTPUT_CHARS` | `20000` | Tool stdout/stderr truncation limit |
| `TEXT_ONLY_DELAY_SECONDS` | `2` | Delay after a text-only model response |

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
