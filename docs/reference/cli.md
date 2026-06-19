# CLI Reference

The Go CLI lives in `cmd/maker/main.go`.

Run directly:

```bash
go run ./cmd/maker COMMAND
```

Build:

```bash
go build -o bin/maker ./cmd/maker
bin/maker COMMAND
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
go run ./cmd/maker status
go run ./cmd/maker events --last 20
go run ./cmd/maker wakes
go run ./cmd/maker show [WAKE_ID|last]
go run ./cmd/maker world --max-depth 5
go run ./cmd/maker doctor
go run ./cmd/maker probe-model --provider ollama --model llama3.1:8b
go run ./cmd/maker count-model-responses --wake current
go run ./cmd/maker evaluate --wake current --last-responses 10
go run ./cmd/maker dashboard --interval 10 --events 8 --last-responses 10
```

`dashboard` also accepts `--once` and `--no-clear`.

## Input And Output Routing

Examples:

```bash
go run ./cmd/maker --output /tmp/maker-events.txt events --last 50
go run ./cmd/maker --output /tmp/maker-dashboard.txt dashboard --once --no-clear
cat maker-place/events.jsonl | go run ./cmd/maker --input - evaluate --wake current --last-responses 10
```

`events`, `count-model-responses`, `evaluate`, and `dashboard` can use stdin
where supported by their implementation. `show` can read a wake JSON object from
`--input`.

## Related

- [Common workflows](../guides/common-workflows.md)
- [File layout](../architecture/file-layout.md)
- [Environment variables](env.md)
