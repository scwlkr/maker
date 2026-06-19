# AGENTS.md

Repo-level instructions for AI/Codex work in Maker.

## Load Order

1. Read this file.
2. Read [docs/map.md](docs/map.md) for task-specific routing.
3. Read [docs/status.md](docs/status.md) before claiming behavior is complete.
4. Read source, tests, scripts, and config before changing runtime behavior.

## Source Truth

- Source code, tests, scripts, Dockerfiles, and `.env.example` beat docs.
- Docs outside `docs/todo/` must describe verified behavior only.
- Put planned, stale, external, or unverified claims in `docs/todo/`.
- Do not invent OpenRouter or Ollama model capability claims. Verify them live
  or keep them in `docs/todo/needs-verification.md`.

## Commands

Setup:

```bash
cp .env.example .env
docker build -f Dockerfile.sandbox -t maker-finn-sandbox:latest .
```

Run:

```bash
MOCK_MODEL=1 scripts/run-once.sh
scripts/start.sh
scripts/stop.sh
```

Inspect:

```bash
go run ./cmd/maker status
go run ./cmd/maker events --last 20
go run ./cmd/maker show last
go run ./cmd/maker dashboard --once --no-clear
scripts/inspect-world.sh
scripts/watch.sh
```

Test:

```bash
uvx pytest
go test ./...
```

## Guardrails

- Do not edit `.env` unless explicitly asked.
- Do not delete or rewrite `maker-place/` logs unless explicitly asked.
- Do not reset the Docker world volume unless the task requires it.
- Treat `maker-place/` as generated observation data; only `.gitkeep` belongs in
  normal source control.
- Keep changes surgical and match the existing Python stdlib, Go stdlib, Bash,
  and Docker patterns.

## Related

- [Docs map](docs/map.md)
- [Project status](docs/status.md)
- [File layout](docs/architecture/file-layout.md)
