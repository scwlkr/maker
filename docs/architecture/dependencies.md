# Dependencies

## Runtime

- Python standard library for the controller, tools, Maker Place, and sandbox
  wrapper.
- Docker CLI and Docker daemon for sandbox image, volume, container, shell, and
  snapshots.
- Ubuntu 24.04 base image for the sandbox.
- OpenRouter API when using the default provider.
- Ollama HTTP API when `MODEL_PROVIDER=ollama`.
- DuckDuckGo HTML endpoint for the `search` tool.

## CLI

- Go 1.22 or newer.
- Go standard library only.

## Tests

- `pytest`, commonly run through `uvx pytest`.
- Docker for integration tests. Docker-backed tests skip when the Docker daemon
  is unavailable.
- Public network access for the `https://example.com` fetch test. That test
  skips on network errors.

## Related

- [Installation](../guides/installation.md)
- [Config files](../reference/config.md)
- [Project status](../status.md)
