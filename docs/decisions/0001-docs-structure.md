# 0001: Documentation Structure

## Status

Accepted.

## Context

Maker has a Python controller, Docker sandbox, Go CLI, shell scripts, tests, and
runtime-generated Maker Place files. A single README was carrying setup, CLI,
security, model, and operations details.

## Decision

Use a compact modular docs structure:

- `README.md` for human overview and quick start.
- `AGENTS.md` for repo-level AI/Codex instructions.
- `docs/map.md` for task-based loading.
- `docs/status.md` for current implemented, partial, missing, and unverified
  behavior.
- Focused concept, guide, reference, architecture, decision, and todo docs.

## Consequences

- Verified behavior can stay easy to find.
- External or stale model claims have a place in `docs/todo/needs-verification.md`.
- Future docs changes should update the map and status rather than expanding the
  README into an all-purpose manual.

## Related

- [Docs map](../map.md)
- [Project status](../status.md)
- [Docs todo](../todo/docs-todo.md)
