# Workspace Model

Maker uses three different storage areas.

## Repo

The repo contains source code, scripts, Dockerfiles, tests, and docs. Generated
runtime data should not be committed.

## World

`/world` is a Docker named volume. It persists across wakes and is mounted into
each sandbox container.

Default volume name:

```bash
maker_finn_world
```

Finn can create, edit, delete, or corrupt files in `/world`.

## Maker Place

`maker-place/` is the controller's local observation directory. It is not mounted
inside the sandbox.

Important files:

- `events.jsonl`
- `wakes/WAKE_ID.json`
- `field-notes/WAKE_ID.md`
- `world-snapshots/WAKE_ID-before.txt`
- `world-snapshots/WAKE_ID-after.txt`
- `raw/WAKE_ID/` when `STORE_RAW_OUTPUTS=1`
- `wake.lock`
- `controller.pid`
- `controller.log`
- `stop`

The repo ignores generated Maker Place contents and keeps only
`maker-place/.gitkeep`.

## Related

- [Core workflow](core-workflow.md)
- [Config files](../reference/config.md)
- [File layout](../architecture/file-layout.md)
