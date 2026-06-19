# Configuration Model

Maker configuration comes from process environment and `.env`.

The Python controller loads `.env` with `os.environ.setdefault`, so exported
environment variables override matching `.env` values. The Go CLI reads `.env`
and also lets process environment override matching values.

## Main Groups

- Model provider: OpenRouter, Ollama, or mock model.
- Wake loop: interval, context limit, text-only delay, and timeouts.
- Sandbox: image, world volume, CPU, memory, pids, shell timeout, and tool output
  truncation.
- Maker Place: observation directory and optional raw output storage.

## Provider Selection

When `MODEL_PROVIDER=ollama`, the controller uses `OLLAMA_MODEL` and
`OLLAMA_FALLBACKS`.

When `MODEL_PROVIDER` is unset or any other value, the controller uses
OpenRouter with `MODEL` and `MODEL_FALLBACKS`.

When `MOCK_MODEL=1`, the controller uses the mock model client and does not need
an OpenRouter key.

## Related

- [Environment reference](../reference/env.md)
- [First run guide](../guides/first-run.md)
- [Needs verification](../todo/needs-verification.md)
