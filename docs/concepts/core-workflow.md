# Core Workflow

A wake is the core unit of work.

1. The controller loads `.env` and process environment settings.
2. The controller creates a wake id and tries to acquire `maker-place/wake.lock`.
3. If the lock is already present, the wake is skipped and an event is logged.
4. A Docker sandbox container starts from the sandbox image.
5. The persistent Docker volume is mounted at `/world`.
6. The controller records a before snapshot of `/world`.
7. The model receives the maker prompt and native tool schemas.
8. Tool calls are executed by the controller against the sandbox or public web.
9. The wake ends when `sleep_or_finish`, context exhaustion, repeated text-only
   model responses, controller stop, or controller error occurs.
10. The controller records an after snapshot, diff summary, wake summary, and
   wake end event.
11. The sandbox container is removed, while `/world` and Maker Place persist.

Loop mode repeats this workflow after `WAKE_INTERVAL_SECONDS` unless the stop
file appears or the process receives a stop signal.

## Related

- [Lifecycle](../architecture/lifecycle.md)
- [Data flow](../architecture/data-flow.md)
- [First run guide](../guides/first-run.md)
