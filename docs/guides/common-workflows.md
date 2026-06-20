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
maker start
maker stop
```

`maker start` writes `maker-place/controller.pid` and appends output to
`maker-place/controller.log`. `maker stop` creates `maker-place/stop`, asks the
process to stop, removes the pid file, removes active sandbox containers with
the `maker.runtime=finn` label, and clears a stale wake lock when the recorded
lock pid is no longer running. The legacy shell wrappers remain available:
`scripts/start.sh` and `scripts/stop.sh`.

## Watch Runtime Activity

```bash
scripts/watch.sh
maker dashboard
maker dashboard --once --no-clear
maker dashboard --color always
```

## Show Wake Records

```bash
scripts/show-last.sh
scripts/show-wake.sh WAKE_ID
maker wakes
maker show last
```

## Inspect Or Reset World

```bash
scripts/inspect-world.sh
maker world
scripts/reset-world.sh
```

`scripts/reset-world.sh` refuses to reset if the controller pid is running.
Maker Place logs remain after a world reset.

## Change Models

Edit `.env`, then restart the loop:

```bash
maker stop
maker start
```

For one-off testing, exported environment variables override `.env` values.

## Related

- [Lifecycle](../architecture/lifecycle.md)
- [Environment reference](../reference/env.md)
- [Troubleshooting](troubleshooting.md)
