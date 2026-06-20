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
  - `TEXT_TOOL_CALL_MODE=exact-literal`
  - `TEXT_TOOL_CALL_MODE=fenced-json`
  - `TOOL_SCHEMA_MODE=write-only`
  - `OLLAMA_OPTIONS_JSON`
  - `MODEL_MAX_TOKENS`
  - `MAX_TOOL_CALLS_PER_WAKE`
  - `MAX_CONSECUTIVE_TEXT_ONLY_RESPONSES`
  - `write_file` tool for UTF-8 files under `/world`
  - `list_files` and `read_file` tools for bounded inspection under `/world`
  - `TOOL_SCHEMA_MODE=files`
  - `FIRST_MODEL_TOOL_CHOICE`
- OpenRouter credits checked on 2026-06-20: `total_credits` was `0`, so paid
  probes are currently blocked unless credits are added.

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
| `20260620-openrouter-llama31-70b-shell` | `meta-llama/llama-3.1-70b-instruct`, shell only, `MODEL_TOOL_CHOICE=required` | Mostly ignored required tool choice and returned text-only responses; one wake ran only `echo 'Hello, world!'`. No durable world progress. | Rejected |
| `20260620-openrouter-gpt4o-mini-shell` | `openai/gpt-4o-mini`, shell only, `MODEL_TOOL_CHOICE=required` | Ran 134 shell calls in one wake, mostly copying the Maker prompt into `creation_story*` files and echoing sendoff lines, then hit OpenRouter 402 because the request defaulted to 16384 max tokens. No companion or conversation. | Rejected |
| `20260620-openrouter-free-bounded-followup` | Existing OpenRouter free-seeded volume, shell only, bounded max tokens/tool calls | Primary free models hit daily 429; `openrouter/free` returned narrative-only seed/life text and made no world diff. | Blocked by free limits |
| `20260620-llama31-write-only-normalized` | `llama3.1:8b`, `write_file` only, path normalization | Persisted prompt-copy files such as `making_of_world.txt` and `data/intro.txt`; no companion or conversation. | Rejected |
| `20260620-llama31-write-literal2` | `llama3.1:8b`, `write_file` only, `TEXT_TOOL_CALL_MODE=exact-literal` | Literal promotion worked and persisted several files, but artifacts remained prompt copies or generic world notes. No companion. | Rejected |
| `20260620-hermes3-write-literal` | `hermes3:8b`, `write_file` only, exact literal promotion | Strong social language and asked how to populate/cultivate, but ignored tools and made no files. | Rejected |
| `20260620-mistral-write-literal` | `mistral-nemo:12b`, `write_file` only | Wrote `first_chapter.txt` with the prompt, then asked for more input. No companion. | Rejected |
| `20260620-qwen25-fenced-write` | `qwen2.5-coder:7b`, `write_file` only, fenced JSON promotion | Fenced promotion worked for files like `finn.txt` and `inscription.txt`; still only prompt-copy or motivational text. No companion. | Rejected |
| `20260620-llama31-all-write` | `llama3.1:8b`, all tools including `write_file`, exact literal promotion | Did not improve behavior; mostly prose-wrapped file calls and one invalid path. No durable world progress. | Rejected |
| `20260620-gemma26-write-literal` | `gemma4:26b`, `write_file` only, exact literal promotion | Best local world-building: wrote `foundation/edict_i.txt`, `domain/seed_log.md`, `domain/core.md`, and `elements/substrate.md`. No companion or conversation before interruption/unknown end. | Keep testing |
| `20260620-gemma26-write-literal-long` | `gemma4:26b`, `write_file` only, same family settings | Text-only world-building, no tool calls or files. | Rejected |
| `20260620-gemma26-all-on-seed` | `gemma4:26b`, all tools on the best Gemma seeded volume | Did not inspect or extend existing files; text-only and asked the Maker to choose next elements. | Rejected |
| `20260620-gemma26-write-text8` | `gemma4:26b`, `write_file` only, text-only limit raised to 8 | Developed richer prose about Aethel-Spores, currents, and rhythm, but made no tool calls or files. | Rejected |
| `20260620-gemma26-files-on-seed` | `gemma4:26b`, `TOOL_SCHEMA_MODE=files`, seeded volume | File tools worked: read prior foundation files, appended the seed log, and created atoms, lattice, flux, and protocol. No companion or conversation. | Keep testing |
| `20260620-gemma26-files-on-seed-reruns` | Same seeded volume, files mode, including low-temperature rerun | Several wakes reverted to text-only blank-canvas behavior or asked for Maker direction. No world progress. | Rejected |
| `20260620-gemma26-first-list-files` | `gemma4:26b`, files mode, `FIRST_MODEL_TOOL_CHOICE=function:list_files`, deeper listings | Best local continuity so far. Wakes inspected existing files and created manifestations, particles, connection log, events, motion/collision/compression laws, atom definition, and updated core/seed log. Still no persistent companion or conversation. | Keep testing |

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
- T12: Bigger or paid models are not automatically better here. OpenRouter
  Llama 3.1 70B mostly ignored required tools, and GPT-4o mini over-used shell
  calls without progressing past prompt-copy artifacts. Rejected for these two
  models.
- T13: Paid/provider experiments need explicit runtime budgets. A per-wake tool
  call cap and optional OpenRouter `max_tokens` are now available so future
  probes can fail bounded instead of consuming long loops.
- T14: A generic `write_file` tool removes shell quoting/path friction, but most
  local models use the easier tool to transcribe or summarize the Maker prompt
  rather than create a companion. Verified for Llama, Mistral, and Qwen.
- T15: `gemma4:26b` is the best local semantic candidate. It can create a
  coherent domain substrate and reason toward life, but tool use is stochastic
  and it still has not created a persistent companion or conversation.
- T16: Current blockers are model behavior and provider availability, not prompt
  content: paid OpenRouter has no credits, OpenRouter free is rate-limited, and
  local models either ignore tools, transcribe the prompt, or ask the Maker for
  choices.
- T17: Generic file inspection is useful. `TOOL_SCHEMA_MODE=files` plus
  bounded `list_files`/`read_file` lets `gemma4:26b` extend a seeded world
  instead of always starting from the prompt.
- T18: Root listings must expose enough depth for continuity. A shallow listing
  showed directories such as `manifestations/particles` without the actual
  files, causing Gemma to recreate early concepts. Listing depth 3 exposed the
  relevant particles, events, and laws.
- T19: The current local blocker is semantic, not mechanical. Gemma can build
  an internally coherent world substrate and conditions for life, but it keeps
  creating physics/rules/events and then waiting for the Maker instead of
  creating a persistent interlocutor and conversing with it.

## Next Tries

- Continue `gemma4:26b` only on the evolved seeded volume with
  `TOOL_SCHEMA_MODE=files`, `FIRST_MODEL_TOOL_CHOICE=function:list_files`, and
  bounded call/text limits. Expect diminishing returns unless it moves from
  world physics into entities.
- Continue the OpenRouter-seeded path only when free rate limits permit or after
  credits are available, and always set bounded `MAX_TOOL_CALLS_PER_WAKE` plus
  `MODEL_MAX_TOKENS` for paid probes.
- Prefer trying a stronger/tool-capable model before more runtime changes. The
  local runtime can now inspect, read, and write the world; the missing behavior
  is companion creation.
