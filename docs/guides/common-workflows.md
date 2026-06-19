# Common Workflows

## Run One Wake

```bash
scripts/run-once.sh
```

Run with the mock model:

```bash
MOCK_MODEL=1 scripts/run-once.sh
```

## Start And Stop The Loop

```bash
scripts/start.sh
scripts/stop.sh
```

`scripts/start.sh` writes `maker-place/controller.pid` and appends output to
`maker-place/controller.log`. `scripts/stop.sh` creates `maker-place/stop`, asks
the process to stop, removes the pid file, and removes active sandbox containers
with the `maker.runtime=finn` label.

## Watch Runtime Activity

```bash
scripts/watch.sh
go run ./cmd/maker dashboard
go run ./cmd/maker dashboard --once --no-clear
```

## Show Wake Records

```bash
scripts/show-last.sh
scripts/show-wake.sh WAKE_ID
go run ./cmd/maker wakes
go run ./cmd/maker show last
```

## Inspect Or Reset World

```bash
scripts/inspect-world.sh
go run ./cmd/maker world
scripts/reset-world.sh
```

`scripts/reset-world.sh` refuses to reset if the controller pid is running.
Maker Place logs remain after a world reset.

## Change Models

Edit `.env`, then restart the loop:

```bash
scripts/stop.sh
scripts/start.sh
```

For one-off testing, exported environment variables override `.env` values.

## Related

- [Lifecycle](../architecture/lifecycle.md)
- [Environment reference](../reference/env.md)
- [Troubleshooting](troubleshooting.md)
