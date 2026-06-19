# Troubleshooting

## `OPENROUTER_API_KEY is required unless MOCK_MODEL=1`

Cause: the controller is using OpenRouter and no key is configured.

Fix one of these:

```bash
OPENROUTER_API_KEY=... scripts/run-once.sh
MODEL_PROVIDER=ollama scripts/run-once.sh
MOCK_MODEL=1 scripts/run-once.sh
```

## Docker CLI Or Daemon Fails

Maker uses the Docker CLI for sandbox image inspection, build, container start,
world snapshots, and world inspection.

Check:

```bash
docker info
maker doctor
```

## `controller already running`

Cause: `maker-place/controller.pid` points to a live process.

Inspect or stop it:

```bash
maker status
maker stop
```

## `sandbox image not found`

The Go `world` command requires the sandbox image to exist.

Build it:

```bash
docker build -f Dockerfile.sandbox -t maker-finn-sandbox:latest .
```

The Python controller can auto-build the image when it is missing.

## Ollama Unreachable Or Model Missing

Check local readiness:

```bash
maker doctor
maker probe-model --provider ollama --model llama3.1:8b
```

Install models with `ollama pull MODEL_NAME`.

## Text-Only Model Responses

OpenRouter requests required tool use, but the controller still logs
`required_tool_choice_ignored` if a response has no tool calls. The wake can
continue until context exhaustion if the model never calls a tool.

Inspect:

```bash
maker events --last 50
maker evaluate --wake current --last-responses 10
```

## Related

- [First run](first-run.md)
- [CLI reference](../reference/cli.md)
- [Project status](../status.md)
