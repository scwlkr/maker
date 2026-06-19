# Lifecycle

## Run Once

`python3 controller.py run-once` creates one wake. `scripts/run-once.sh` runs
that command from the repo root.

The command exits with:

- `0` when a wake runs and returns a summary.
- `2` when the wake lock prevents a new wake.
- Non-zero when argument parsing or setup raises before a summary is returned.

## Loop

`python3 controller.py loop` repeats wakes until stopped. `scripts/start.sh`
starts it with `nohup`, writes `maker-place/controller.pid`, and appends output
to `maker-place/controller.log`.

The loop checks `maker-place/stop` and handles `SIGTERM` and `SIGINT`.

## Wake End Reasons

Observed end reasons from source:

- `sleep_or_finish`
- `context_exhausted`
- `controller_stopped`
- `controller_error`
- `unknown`

## Cleanup

The controller tries to write the after snapshot, stop the sandbox container,
write the wake summary, append `wake_end`, and release the wake lock in a
`finally` block.

`scripts/stop.sh` also removes active containers with label `maker.runtime=finn`.

## Related

- [Core workflow](../concepts/core-workflow.md)
- [Common workflows](../guides/common-workflows.md)
- [Troubleshooting](../guides/troubleshooting.md)
