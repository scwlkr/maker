# Docs Map

Use this file to choose the smallest useful doc set for a task.

## Default Load

For any non-trivial Maker task, load:

- [Repo agent instructions](../AGENTS.md)
- [Project status](status.md)
- The task-specific docs below

## Task Routing

| Task | Load |
| --- | --- |
| Understand the project | [Project](concepts/project.md), [Core workflow](concepts/core-workflow.md), [Status](status.md) |
| Run Maker for the first time | [Installation](guides/installation.md), [First run](guides/first-run.md), [Environment](reference/env.md) |
| Start, stop, inspect, or reset | [Common workflows](guides/common-workflows.md), [CLI](reference/cli.md), [Lifecycle](architecture/lifecycle.md) |
| Debug wake behavior | [Troubleshooting](guides/troubleshooting.md), [Data flow](architecture/data-flow.md), [CLI](reference/cli.md) |
| Observe Finn world-code experiments | [Data flow](architecture/data-flow.md), [Workspace model](concepts/workspace.md), [Finn matrix observation](todo/finn-matrix-observation.md) |
| Change model settings | [Configuration model](concepts/configuration.md), [Environment](reference/env.md), [Needs verification](todo/needs-verification.md) |
| Change sandbox behavior | [Architecture overview](architecture/overview.md), [Lifecycle](architecture/lifecycle.md), [Environment](reference/env.md) |
| Change CLI behavior | [CLI](reference/cli.md), [File layout](architecture/file-layout.md), `cmd/maker/main.go`, `cmd/maker/interface.go`, `tests/test_cli.py` |
| Change controller behavior | [Lifecycle](architecture/lifecycle.md), [Data flow](architecture/data-flow.md), `controller.py`, `tests/test_controller_unit.py` |
| Change docs | [Docs agent instructions](AGENTS.md), [Docs todo](todo/docs-todo.md), [Docs structure decision](decisions/0001-docs-structure.md) |

## Source Files By Area

- Controller: `controller.py`, `maker_place.py`, `sandbox.py`, `tools.py`
- CLI: `cmd/maker/main.go`, `go.mod`
- Scripts: `scripts/*.sh`
- Containers: `Dockerfile.sandbox`, `Dockerfile.controller`,
  `docker-compose.yml`
- Tests: `tests/*.py`

## Related

- [Docs index](index.md)
- [Project status](status.md)
- [File layout](architecture/file-layout.md)
