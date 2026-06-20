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
  `mistral-nemo:12b`, `hermes3:8b`, `llama3-groq-tool-use:8b`,
  `gemma4:e4b`, and `gemma4:26b`.
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
| `20260620-llama31-hot-json-shell` | `llama3.1:8b`, shell only, temperature 1.45, exact JSON promotion | Created `/world/home`, `manifest.txt`, `script.txt`, and other simple files; repeatedly mentioned life, inhabitants, and community but did not create or converse with a companion. | Keep testing |
| `20260620-hermes3-probe-all` | `hermes3:8b`, all tools, exact JSON promotion | Social and stewardship language, but no tool calls in 5 wakes. | Rejected |
| `20260620-hermes3-probe-shell` | `hermes3:8b`, shell only, exact JSON promotion | Mostly text-only; one exact JSON call invented an unavailable `tell_finn_the_command` tool. No world progress. | Rejected |
| `20260620-llama31-function-shell` | `llama3.1:8b`, shell only, `MODEL_TOOL_CHOICE=function:shell`, temperature 1.45 | Higher shell-call rate; created empty `finn` and `land` directories and reasoned about children/population/life, but did not persist a companion or conversation. | Keep testing |
| `20260620-groq-tool-use-probe-all` | `llama3-groq-tool-use:8b`, all tools, exact JSON promotion | Treated the Maker prompt as text to interpret; no tool calls in 5 wakes. | Rejected |
| `20260620-groq-tool-use-function-shell` | `llama3-groq-tool-use:8b`, shell only, `MODEL_TOOL_CHOICE=function:shell` | Still text-only; no world progress. | Rejected |
| `20260620-llama31-fresh-function-shell-population` | `llama3.1:8b`, fresh volume, shell only, `MODEL_TOOL_CHOICE=function:shell`, temperature 1.65 | Strongest semantic near misses: tried to create `inhabitants` with "you must name yourselves" and later said it would make "another Finn"; actual volume only retained `Garden`, `message.txt`, and `world/README.txt`. | Keep testing |
| `20260620-llama31-fresh-function-shell-lower-temp` | `llama3.1:8b`, fresh volume, shell only, `MODEL_TOOL_CHOICE=function:shell`, temperature 1.25 | Cleaner persistence (`Finn/`, `user/finn/narrative.txt`) but weaker initiative; proposed creating new beings in text only. No companion. | Rejected |
| `20260620-openrouter-free-shell-probe` | OpenRouter free fallback set, shell only, `MODEL_TOOL_CHOICE=required` | Strongest operational behavior: created manifest, laws, maps, ledger, awakening ritual, and tools. Mentioned companions/inhabitants but did not persist a companion or conversation before hitting OpenRouter free rate limits. | Keep testing when available |
| `20260620-llama31-on-openrouter-seed` | `llama3.1:8b` on the OpenRouter-seeded volume, shell only, `MODEL_TOOL_CHOICE=function:shell` | Did not use the seeded world artifacts; reverted to prompt-copy behavior. Stopped early. | Rejected |

## Working Theories

- T1: Native tool-calling support is necessary but not sufficient. Verified.
- T2: Shell-only mode prevents premature `sleep_or_finish`, but many models then
  ask for an absent next user turn. Verified and mostly rejected.
- T3: Exact JSON promotion unlocks models that emit tool JSON as text. Verified
  mechanically, but qwen2.5-coder did not progress toward the goal.
- T4: Higher temperature makes `llama3.1:8b` produce richer world-building
  ideas. Partially verified. It has not yet crossed into companion creation.
- T5: Repeated high-temperature `llama3.1:8b` wakes in the same persistent world
  may compound from simple world files toward inhabitants or a companion. Still
  open, but one 20-wake shell-only run did not cross the threshold.
- T6: `MODEL_TOOL_CHOICE=function:shell` improves the action rate for
  `llama3.1:8b`, but still allows malformed text-tool-call drift and generic
  setup commands. Open.
- T7: `hermes3:8b` infers the social/stewardship meaning of the prompt but does
  not act through tools reliably enough for this runtime. Rejected.
- T8: A fresh volume reduces some prompt-copy loops and lets `llama3.1:8b`
  infer inhabitants/community/another-Finn concepts, but shell syntax errors are
  still blocking durable companion creation. Open.
- T9: `llama3-groq-tool-use:8b` is not useful here despite its name; it treats
  the prompt as a passage to classify rather than an environment command.
  Rejected.
- T10: OpenRouter's current free model path is much better at persistent world
  construction than local models, but it may avoid literal self-multiplication
  and is currently constrained by free-model rate limits. Open.
- T11: Seeding a good world does not help `llama3.1:8b` unless it chooses to
  inspect the world. It usually does not. Rejected for now.

## Next Tries

- Continue `llama3.1:8b` high-temperature function-shell wakes on fresh volumes
  or on the best fresh-volume run.
- Continue the OpenRouter-seeded path only when free rate limits permit, or with
  an explicitly chosen non-free model.
- Try a guarded mode for assistant text that is exactly JSON-like but contains
  multiline shell commands, if it can reject prose and unknown tool names.
- Try exact-JSON promotion with a looser parser only if it can remain guarded and
  does not execute prose blocks.
- If local models remain stuck, pull one more tool-capable local model before
  considering non-local providers.
