# First Run

Use the mock model first. It verifies the controller, sandbox, Maker Place, and
world volume without requiring OpenRouter or Ollama.

## Steps

```bash
cp .env.example .env
docker build -f Dockerfile.sandbox -t maker-finn-sandbox:latest .
GOBIN="$HOME/.local/bin" go install ./cmd/maker
MOCK_MODEL=1 scripts/run-once.sh
```

Expected result:

- The command prints JSON with `wake_id` and `end_reason`.
- `end_reason` should be `sleep_or_finish`.
- Maker Place files are written under `maker-place/`.
- The mock wake writes `mock-wake.txt` into `/world`.

## Inspect The Result

```bash
maker status
maker show last
maker events --last 20
maker world
```

You can also inspect with scripts:

```bash
scripts/show-last.sh
scripts/inspect-world.sh
```

## Next Runs

After the mock path works, configure OpenRouter or Ollama in `.env`, then run:

```bash
scripts/run-once.sh
```

Restart the controller loop after changing `.env`.

## Related

- [Installation](installation.md)
- [Common workflows](common-workflows.md)
- [CLI reference](../reference/cli.md)
