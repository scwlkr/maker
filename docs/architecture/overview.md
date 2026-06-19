# Architecture Overview

Maker has four main parts.

## Controller

`controller.py` owns wake orchestration, settings, model clients, fallback
attempts, tool-call loops, and stop handling.

## Sandbox

`sandbox.py` wraps Docker CLI operations. It builds or inspects the sandbox
image, creates the world volume, starts a disposable container, runs bash
commands inside `/world`, captures snapshots, inspects container state, and
removes the container.

## Tools

`tools.py` defines native tool schemas and executes tool calls. `shell` runs in
the sandbox. `search` and `fetch` run from the controller process. `fetch`
performs public URL checks before network access.

## Maker Place

`maker_place.py` manages local observation files, event append, wake locks,
snapshots, wake summaries, optional raw output storage, and timestamps.

## Go CLI

`cmd/maker/main.go` reads Maker Place and Docker state for status, events, wake
inspection, world listing, readiness checks, model probing, evaluation, and a
terminal dashboard.

## Related

- [Data flow](data-flow.md)
- [Lifecycle](lifecycle.md)
- [File layout](file-layout.md)
