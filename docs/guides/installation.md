# Installation

Maker currently runs from the repo.

## Requirements

- Python 3
- Docker CLI and Docker daemon
- Go 1.22 or newer for the Go CLI
- `uvx` if you want to run the documented pytest command
- OpenRouter API key, unless using Ollama or `MOCK_MODEL=1`

## Setup

```bash
cp .env.example .env
docker build -f Dockerfile.sandbox -t maker-finn-sandbox:latest .
GOBIN="$HOME/.local/bin" go install ./cmd/maker
```

The scripts are executable in the current repo. If that changes after copying
the repo, run:

```bash
chmod +x scripts/*.sh
```

## Configure A Provider

For OpenRouter, edit `.env`:

```bash
MODEL_PROVIDER=openrouter
OPENROUTER_API_KEY=...
MODEL=nex-agi/nex-n2-pro:free
```

For Ollama, edit `.env`:

```bash
MODEL_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b
```

For a local smoke test without external model calls, use `MOCK_MODEL=1` in the
command environment.

## Verify

```bash
maker doctor
maker dashboard --once --no-clear
uvx pytest
```

`doctor` checks local runtime readiness. It may show failures for optional
providers that are not configured.

## Related

- [First run](first-run.md)
- [Environment reference](../reference/env.md)
- [Troubleshooting](troubleshooting.md)
