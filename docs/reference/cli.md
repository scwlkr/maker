# CLI Reference

The Go CLI lives in `cmd/maker/main.go`.

Run directly:

```bash
go run ./cmd/maker COMMAND
```

Install a local `maker` command:

```bash
GOBIN="$HOME/.local/bin" go install ./cmd/maker
maker COMMAND
```

## Global Flags

| Flag | Default | Meaning |
| --- | --- | --- |
| `--maker-place PATH` | `MAKER_PLACE_DIR` or `maker-place` | Maker Place directory |
| `--world-volume NAME` | `WORLD_VOLUME` or `maker_finn_world` | Docker volume mounted at `/world` |
| `--sandbox-image IMG` | `SANDBOX_IMAGE` or `maker-finn-sandbox:latest` | Sandbox image for world inspection |
| `--input FILE|-` | none | Read command input from file or stdin where supported |
| `--output FILE|-` | stdout | Write normal output to file or stdout |
| `--json` | false | Emit JSON where supported |

## Commands

```bash
maker start
maker stop
maker status
maker events --last 20
maker wakes
maker show [WAKE_ID|last]
maker world --max-depth 5
maker doctor
maker probe-model --provider ollama --model llama3.1:8b
maker count-model-responses --wake current
maker evaluate --wake current --last-responses 10
maker dashboard --interval 10 --events 8 --last-responses 10
```

`start` starts the controller loop in the background and writes
`maker-place/controller.pid` plus `maker-place/controller.log`. `stop` creates
the stop file, terminates the recorded controller when present, removes the pid
file, removes active Finn sandbox containers, and clears a stale wake lock when
the recorded lock pid is no longer running.

`dashboard` renders runtime state, the current or latest wake, work accomplished,
recent wakes, and recent events. It also accepts `--once`, `--no-clear`, and
`--color auto|always|never`.

## Input And Output Routing

Examples:

```bash
maker --output /tmp/maker-events.txt events --last 50
maker --output /tmp/maker-dashboard.txt dashboard --once --no-clear
cat maker-place/events.jsonl | maker --input - evaluate --wake current --last-responses 10
```

`events`, `count-model-responses`, `evaluate`, and `dashboard` can use stdin
where supported by their implementation. `show` can read a wake JSON object from
`--input`.

## Related

- [Common workflows](../guides/common-workflows.md)
- [File layout](../architecture/file-layout.md)
- [Environment variables](env.md)
