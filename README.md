# Maker

Maker is an autonomous sandbox runtime for Finn.

Finn wakes with the maker prompt and four tools. The Python controller stays
outside the sandbox, starts a disposable Docker container for each wake, mounts
one persistent Docker named volume at `/world`, records observations in Maker
Place, then removes the container.

## Current Status

Maker is an early local runtime with source-backed scripts, a Python controller,
a Docker sandbox, a Go inspection CLI, and pytest coverage. It is not packaged
as an installable product and has no tagged releases yet.

See [Project status](docs/status.md) for implemented, partial, missing, and
unverified behavior.

## Requirements

- Python 3
- Docker CLI and Docker daemon
- Go 1.22 or newer for the `maker` CLI
- OpenRouter API key, unless using `MODEL_PROVIDER=ollama` or `MOCK_MODEL=1`

## Quick Start

```bash
cp .env.example .env
docker build -f Dockerfile.sandbox -t maker-finn-sandbox:latest .
GOBIN="$HOME/.local/bin" go install ./cmd/maker
MOCK_MODEL=1 scripts/run-once.sh
maker status
maker show last
maker world
```

The controller can build the sandbox image automatically if it is missing. The
explicit build step is useful because it fails early when Docker is unavailable.

## Run

Run one wake:

```bash
scripts/run-once.sh
```

Run a local mock wake without OpenRouter:

```bash
MOCK_MODEL=1 scripts/run-once.sh
```

Start and stop the loop:

```bash
scripts/start.sh
scripts/stop.sh
```

The default loop interval is `300` seconds. A wake lock prevents overlapping
wakes.

## Inspect

Maker Place is the local observation directory:

- `maker-place/events.jsonl`
- `maker-place/wakes/WAKE_ID.json`
- `maker-place/world-snapshots/WAKE_ID-before.txt`
- `maker-place/world-snapshots/WAKE_ID-after.txt`
- `maker-place/raw/WAKE_ID/` when `STORE_RAW_OUTPUTS=1`

Useful inspection commands:

```bash
scripts/watch.sh
scripts/show-last.sh
scripts/show-wake.sh WAKE_ID
scripts/inspect-world.sh
maker dashboard --once --no-clear
```

`/world` is a Docker named volume, not a repo directory.

## CLI

The Go CLI is the main debugging surface:

```bash
maker status
maker events --last 20
maker wakes
maker show last
maker world
maker doctor
maker evaluate --wake current --last-responses 10
maker dashboard
```

Install a local binary into `~/.local/bin`:

```bash
GOBIN="$HOME/.local/bin" go install ./cmd/maker
maker dashboard
```

See [CLI reference](docs/reference/cli.md) for global flags, command flags, JSON
output, and file/stdin routing.

## Configure Models

OpenRouter is the default provider:

```bash
MODEL_PROVIDER=openrouter
OPENROUTER_API_KEY=...
MODEL=nex-agi/nex-n2-pro:free
```

Ollama is local and does not require `OPENROUTER_API_KEY`:

```bash
MODEL_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b
OLLAMA_FALLBACKS=qwen3.5:9b
```

Restart the controller after changing `.env`. See
[environment reference](docs/reference/env.md) for all runtime variables.

## Security Boundary

The sandbox is powerful inside its container: it runs as root, can execute
arbitrary bash through `shell`, can use public internet where Docker allows it,
and can create, edit, delete, or corrupt `/world`.

The intended boundary is that the sandbox is not privileged, does not use host
networking, does not receive the Docker socket, does not receive the controller
API key, does not mount the host filesystem except the dedicated `/world` Docker
volume, and does not mount Maker Place.

Controller `fetch()` blocks obvious localhost, private, link-local, reserved,
multicast, unspecified, and metadata targets. Direct shell networking from the
sandbox is intentionally broad.

## Tests

```bash
uvx pytest
```

Docker-backed tests skip automatically when the Docker daemon is unavailable.

## Documentation

Start at [docs/index.md](docs/index.md). AI/Codex agents should load
[docs/map.md](docs/map.md) before task-specific docs.

## Related

- [Project status](docs/status.md)
- [First run guide](docs/guides/first-run.md)
- [Architecture overview](docs/architecture/overview.md)
