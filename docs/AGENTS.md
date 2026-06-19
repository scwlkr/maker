# Docs Agent Instructions

Use these instructions when editing files under `docs/`.

## Rules

- Keep normal docs factual and verified from source, tests, scripts, config, or
  successful commands.
- Keep planned, external, stale, and uncertain claims in `docs/todo/`.
- Prefer short linked files over one large document.
- Update [docs/map.md](map.md) when adding task-relevant docs.
- Update [docs/status.md](status.md) when project behavior changes.
- Include a `Related` section in each doc when another doc has useful context.

## Verification

Before finishing docs work, run the cheapest relevant checks:

```bash
find docs -name '*.md' -print | sort
uvx pytest
```

Use `go test ./...` when Go code or CLI behavior changes.

## Related

- [Docs index](index.md)
- [Docs map](map.md)
- [Project status](status.md)
