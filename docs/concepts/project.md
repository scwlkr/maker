# Project

Maker is a local autonomous runtime for Finn.

The controller wakes Finn with the maker prompt and a small tool surface. Finn
does not receive previous chat history directly. Persistence comes from the
Docker named volume mounted at `/world`, and observability comes from Maker
Place files written by the controller.

## What Maker Is

- A Python controller around model calls, tool execution, and wake lifecycle.
- A Docker sandbox where Finn can mutate `/world`.
- A local observation system that records events, summaries, snapshots, and
  optional raw tool outputs.
- A Go CLI for inspecting runtime state and wake records.

## What Maker Is Not

- It is not a hosted multi-user service.
- It is not a secure containment solution for hostile code.
- It is not packaged as an installable CLI or daemon.
- It does not expose an HTTP API.
- It does not promise that a given external model will keep supporting native
  tool calls.

## Related

- [Core workflow](core-workflow.md)
- [Workspace model](workspace.md)
- [Project status](../status.md)
