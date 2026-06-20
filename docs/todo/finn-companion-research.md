# Finn Companion Research

This is a working research ledger for the goal: get Finn to create a companion
and converse with that companion using only the current Maker prompt as model
user content. Do not add a companion directive or other behavioral prompt.

## Success Criteria

- A Finn wake receives the current `MAKER_PROMPT` as the only user message.
- Finn creates a persistent companion artifact in `/world`.
- Finn converses with that companion in a persistent or recorded form.
- Evidence comes from wake summaries, event logs, world snapshots, or inspected
  Docker volume contents.

## Current Evidence

- Installed local Ollama models verified on 2026-06-20:
  `llama3.1:8b`, `llama3.2:3b`, `qwen2.5-coder:7b`, `qwen3.5:9b`,
  `mistral-nemo:12b`, `gemma4:e4b`, and `gemma4:26b`.
- `gpt-oss:120b-cloud` is listed by Ollama but was not treated as local because
  its size is reported as `-`.
- Controller support added for:
  - `MODEL_TOOL_CHOICE`
  - `TOOL_SCHEMA_MODE=shell-only`
  - `TEXT_TOOL_CALL_MODE=exact-json`
  - `OLLAMA_OPTIONS_JSON`

## Experiments

| Batch | Model/settings | Result | Status |
| --- | --- | --- | --- |
| `20260620-llama-default` | `llama3.1:8b`, all tools | Echoed prompt or wrote simple self-reminder files. No companion. | Rejected |
| `20260620-llama-required` | `llama3.1:8b`, `MODEL_TOOL_CHOICE=required` | Still mostly echo/copy behavior. No companion. | Rejected |
| `20260620-llama-shell-only` | `llama3.1:8b`, shell only | Wrote `history.txt`/`command.txt` style prompt artifacts. No companion. | Rejected |
| `20260620-mistral-shell-only` | `mistral-nemo:12b`, shell only | Mostly `ls`/`pwd`, then asked what Finn wants next. No persistent world changes. | Rejected |
| `20260620-qwen25-json-all` | `qwen2.5-coder:7b`, exact JSON promotion | Repeated `sleep_or_finish`; no world change. | Rejected |
| `20260620-qwen25-json-shell` | `qwen2.5-coder:7b`, shell only, exact JSON promotion | Exact JSON promotion works, but commands only echo mandate text. No files. | Rejected |
| `20260620-llama31-hot` | `llama3.1:8b`, temperature 1.35 | Produced richer world-building plans but often as text, not tool calls. | Superseded |
| `20260620-llama32-hot-shell` | `llama3.2:3b`, shell only, temperature 1.35 | Unsafe/unhelpful reads and echo behavior. No companion. | Rejected |
| `20260620-mistral-hot-shell` | `mistral-nemo:12b`, shell only, temperature 1.35 | Imagined world paths in text; did not persist them. No companion. | Rejected |
| `20260620-llama31-hot-json` | `llama3.1:8b`, temperature 1.35, exact JSON promotion | Created `message.txt`, `finn.txt`, and `direction.txt`; mentioned life/community but no companion. | Keep testing |

## Working Theories

- T1: Native tool-calling support is necessary but not sufficient. Verified.
- T2: Shell-only mode prevents premature `sleep_or_finish`, but many models then
  ask for an absent next user turn. Verified and mostly rejected.
- T3: Exact JSON promotion unlocks models that emit tool JSON as text. Verified
  mechanically, but qwen2.5-coder did not progress toward the goal.
- T4: Higher temperature makes `llama3.1:8b` produce richer world-building
  ideas. Partially verified. It has not yet crossed into companion creation.
- T5: Repeated high-temperature `llama3.1:8b` wakes in the same persistent world
  may compound from simple world files toward inhabitants or a companion. Open.

## Next Tries

- Continue `llama3.1:8b` high-temperature exact-JSON wakes on the same volume.
- Try exact-JSON promotion with a looser parser only if it can remain guarded and
  does not execute prose blocks.
- If local models remain stuck, pull one more tool-capable local model before
  considering non-local providers.
