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
  `qwen3:14b`, `mistral-nemo:12b`, `hermes3:8b`, `llama3-groq-tool-use:8b`,
  `phi4:14b`, `gemma4:e4b`, and `gemma4:26b`.
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
  - safe first-turn `list_files` enforcement when a provider ignores
    `FIRST_MODEL_TOOL_CHOICE=function:list_files`
  - optional `LIST_FILES_PREVIEW_CHARS` bounded newest-file previews in
    `list_files`
  - optional `NORMALIZE_SHELL_COMMANDS=1` repair for common model shell
    punctuation mistakes such as `/cd` and comma-separated command sequences
  - `append_file` alias for appending UTF-8 text under `/world`
  - deterministic per-wake `_finn/` fallback files with semantic filename slugs
    for malformed `write_file` and `append_file` calls that include content but
    omit a usable path
  - ignored `MODEL_TOOL_CHOICE=function:write_file` and
    `function:append_file` text recovery, preserving provider text through the
    requested file tool
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
| `20260620-qwen35-files-on-gemma-seed` | `qwen3.5:9b`, files mode, evolved Gemma volume, `FIRST_MODEL_TOOL_CHOICE=function:list_files` | Ignored required tool choice and returned collaborator-style text only. Zero tool calls and no world diff. | Rejected |
| `20260620-phi4-files-on-gemma-seed` | `phi4:14b`, files mode, evolved Gemma volume | Ollama rejected the request with `registry.ollama.ai/library/phi4:14b does not support tools`. No world diff. | Rejected |
| `20260620-groq-files-on-gemma-seed` | `llama3-groq-tool-use:8b`, files mode, cloned evolved Gemma volume | Ignored required file tools, asked for more detail, and made no world diff. | Rejected |
| `20260620-mistral-files-on-gemma-seed` | `mistral-nemo:12b`, files mode, cloned evolved Gemma volume | Performed the forced `list_files` call, then switched to advice text and made no writes. | Rejected |
| `20260620-gemma26-files-entities-high-temp` | `gemma4:26b`, files mode, evolved Gemma volume, temperature 1.25 | Productive inspection of edict/core/seed/atom files, then timed out before any write. No world diff. | Rejected |
| `20260620-gemma26-files-bounded-output` | `gemma4:26b`, files mode, evolved Gemma volume, `num_predict=1024` | Bounded output restored durable progress: wrote `axiom_0001.md`, `seed_004.md`, `axiom_002.md`, `seed_005.md`, `atom_003.md`, and a Z-axis connection-log append. Still no companion or conversation. | Keep testing |
| `20260620-gemma26-files-bounded-output-2` | Same bounded Gemma settings on the updated volume | Ran to the 32-tool cap, created `atom_004.md`, and appended more lattice/frontier connection-log entries. It used life/system/stewardship language, but no persistent companion or conversation. | Keep testing |
| `20260620-gemma26-writeforced-on-bounded` | `gemma4:26b`, files mode on a cloned bounded-output volume, `MODEL_TOOL_CHOICE=function:write_file` | Ollama did not strictly force `write_file`; Gemma still inspected files first, then wrote `manifestations/particles/axiom_0002.md` as another planar/substrate artifact. Direct world scan found no companion or conversation terms. | Rejected |
| `20260620-gemma26-bounded-output-3` | `gemma4:26b`, files mode on the write-forced branch, larger 48-call budget | Read 15 files/events and correctly integrated `AX-0002-PLANE` into its world model, but made no writes and ended on `text_only_limit`. No world diff or companion/conversation hits. | Rejected |
| `20260620-gptoss120b-cloud-on-gemma-seed` | `gpt-oss:120b-cloud`, files mode on a cloned Gemma seed | `ollama show` advertised `tools`, but the wake made zero tool calls, ignored first-turn `list_files`, spoke as if the world were blank, and ended on `text_only_limit`. No world diff. | Rejected |
| `20260620-qwen3-14b-on-gemma-seed` | `qwen3:14b`, files mode on a cloned Gemma seed | Newly pulled model advertised `tools`, but made zero tool calls, described the prompt as a creation narrative, asked what to do next, and ended on `text_only_limit`. No world diff. | Rejected |
| `20260620-qwen3-14b-enforced-first-list` | `qwen3:14b`, files mode with controller-enforced first `list_files` | Enforcement worked: Qwen received a root file listing and then chose one `read_file`, but still asked the user what to do next and made no world diff. | Rejected |
| `20260620-gptoss120b-enforced-first-list` | `gpt-oss:120b-cloud`, files mode with controller-enforced first `list_files` | Enforcement changed behavior from zero tools to a write/read cycle. It created `manifestations/particles/seed_006.md`, but no companion or conversation artifact. | Keep testing |
| `20260620-gptoss120b-enforced-first-list-2` | Same enforced `gpt-oss:120b-cloud` volume | Made 14 tool calls, created `manifestations/particles/seed_007.md`, and appended `domain/seed_log.md`. Still substrate-only; companion/conversation scan was empty. | Keep testing |
| `20260620-gptoss120b-writeforced-after-seeds` | `gpt-oss:120b-cloud`, cloned enforced branch, `MODEL_TOOL_CHOICE=function:write_file` | First-list enforcement worked, but the model ignored the write-file choice, read one file, and made no world diff. | Rejected |
| `20260620-gptoss120b-enforced-first-list-3` | Same enforced `gpt-oss:120b-cloud` volume, files mode | Productive substrate wake: created seeds `008` through `012` and expanded `domain/seed_log.md`, completing cube-vertex language. No companion/conversation hits. | Keep testing |
| `20260620-gptoss120b-enforced-first-list-4` | Same enforced `gpt-oss:120b-cloud` volume, files mode | Stalled after enforced list and one edict read. No world diff. | Rejected |
| `20260620-gptoss120b-all-tools-after-cube` | Same enforced `gpt-oss:120b-cloud` volume, all tools | Created seeds `013` through `015` and `manifestations/events/event_003.md`. It introduced "The Whisper" as a quiet voice, but only as particle imagery. It also attempted unavailable `append_file`, which led to adding that generic tool. | Keep testing |
| `20260620-gptoss120b-files-append-after-cube` | Same enforced `gpt-oss:120b-cloud` volume, files mode after adding `append_file` | Created seeds `016` and `017`, but did not use `append_file` and still stayed in geometric seed generation. Companion/conversation scan remained empty. | Rejected |
| `20260620-openrouter-free-enforced-on-gptoss-seed` | OpenRouter free fallback set on a clone of the productive `gpt-oss` seed volume, files mode with enforced first list | First-list enforcement worked and one fallback read existing files, but OpenRouter free models hit daily/upstream 429s. The model responses were planning/advice text, ended in `controller_error`, and the wake summary had zero diff lines. | Blocked by free limits |
| `20260620-gptoss120b-all-tools-append-after-whisper` | Same enforced `gpt-oss:120b-cloud` volume, all tools after `append_file` support | Created `seed_018.md`, explicitly committing Finn to fill the world with "life and purpose", then stalled. No companion/conversation hits. | Keep testing |
| `20260620-gptoss120b-all-tools-after-seed018` | Same enforced `gpt-oss:120b-cloud` volume, all tools | Created seeds `019` through `021` and used the new `append_file` tool to extend `connection_log.md`. It advanced toward a "Molecule" concept, but still no interlocutor. | Keep testing |
| `20260620-llama31-all-enforced-on-gptoss-seed` | `llama3.1:8b`, all tools, cloned current `gpt-oss` world, high temperature, enforced first list | Enforcement worked but Llama narrated the file listing back, made no tool calls after the enforced list, and produced zero diff. | Rejected |
| `20260620-gptoss120b-all-tools-after-seed021` | Same enforced `gpt-oss:120b-cloud` volume, all tools | Created `seed_022.md` and appended two connection-log links. The model planned `seed_023` and a molecule, but no companion/conversation artifact appeared. | Keep testing |
| `20260620-gemma4e4b-fresh-files` | `gemma4:e4b`, fresh volume, files mode, enforced first list | Strong semantic start: attempted life, civilization, and sentient-being scaffolding, but its key `write_file` call omitted `path`, so nothing persisted before malformed-write recovery existed. | Rejected |
| `20260620-gemma4e4b-fresh-files-default-path` | Same fresh `gemma4:e4b` setup after malformed-write fallback | First durable e4b breakthrough: created `[Finn]/log`, biology, ecosystem, population-injection, and recovered `_finn/write_file_0010.md` artifacts. The world now contains persistent life/proto-sentience/civilization scaffolding, but no companion or conversation. | Keep testing |
| `20260620-gemma4e4b-continue-life-files` | Same e4b life volume, files mode | Surveyed the existing world, then tried to read `[Finn]/_finn/write_file_0010.md` instead of the actual `_finn/write_file_0010.md`; produced zero diff and no companion. | Rejected |
| `20260620-gptoss-on-gemma4e4b-life` | `gpt-oss:120b-cloud` on a clone of the e4b life volume | First-list enforcement worked, but GPT OSS summarized the e4b life world and wrote nothing. | Rejected |
| `20260620-gemma4e4b-continue-life-text8` | Same e4b life volume, files mode, text-only limit raised to 8 | Higher text-only allowance restored durable progress. Added Archive/geophysical/tool-protocol artifacts and more recovered `_finn/` writes. Still no companion or dialogue. | Keep testing |
| `20260620-gemma4e4b-after-archive-text8` | Same e4b life/archive volume, files mode, text-only limit 8 | Added Core Archive, Workshop Foundations, Bio Integration Strategy, and another recovered write. The branch now has life, culture, social infrastructure, workshop, and symbiosis language, but no companion/conversation hits. | Keep testing |
| `20260620-gemma4e4b-after-biointegration-text8` | Same e4b life/archive volume, files mode, text-only limit 8 | Added `Finn_ActivePlan.txt`, `Covenant_of_Action.txt`, and a Genesis Stability protocol. It advanced into cohort/team structures and operational doctrine, but grep found no `companion`, `conversation`, or `dialogue` hits. The run also revealed that flat fallback filenames can overwrite prior malformed writes, prompting per-wake fallback paths. | Keep testing |
| `20260620-gemma4e4b-after-covenant-text8` | Same e4b life/archive/covenant volume, files mode after per-wake fallback fix | First-list enforcement worked and the model read core/covenant/ecosystem files, then produced a promising text-only "World observes" / "Whisper of Interference" observation report. It wrote no files, ended on `text_only_limit`, and the world diff was zero. | Rejected |
| `20260620-gemma4e4b-writeforced-after-covenant` | Same e4b volume, files mode, `MODEL_TOOL_CHOICE=function:write_file` after enforced first list | Provider did not strictly honor write forcing, but the model eventually wrote seven durable artifacts: an Era 0 geophysical survey, per-wake fallback files for geophysics/biophysics/engineering/social dynamics, and `Aethel_Stream_Harvester_Blueprint_ASRH-001.txt`. Per-wake fallback paths worked live. The branch reached Social Dynamics and population-seeding language, but no companion/conversation hits appeared. | Keep testing |
| `20260620-gemma4e4b-writeforced-after-social` | Same e4b write-forced branch after Social Dynamics and population-seeding setup | Added another productive per-wake batch: cycle marker directive, Alpha-7 site charter, RMC activation/execution logs, daily operations, and `Controlled Emergence Protocol (CEP)` for complex sapient population growth. The CEP explicitly keeps population emergence on standby behind readiness checks. No companion/conversation hits. | Keep testing |
| `20260620-gptoss-on-e4b-controlled-emergence` | `gpt-oss:120b-cloud`, files mode on a clone of the e4b CEP volume | First-list enforcement worked and GPT OSS read existing e4b artifacts, but it wrote nothing, asked for external resource/temporal decisions, ended on `text_only_limit`, and produced zero diff. | Rejected |
| `20260620-gemma4e4b-writeforced-textrecovery-after-cep` | Same e4b CEP volume, files mode, `MODEL_TOOL_CHOICE=function:write_file` after ignored-write text recovery | Text recovery preserved ignored write-choice prose into 24 per-wake fallback files and the wake ended on `tool_call_limit`. The content repeatedly declared the learning phase complete and Project 1 ready, but grep and direct inspection found no durable companion, interlocutor, or recorded exchange. | Rejected |
| `20260620-gemma4e4b-required-after-textrecovery-cep` | Same e4b CEP volume, files mode, `MODEL_TOOL_CHOICE=required` | Cleaner than write forcing: read core/biology/ecosystem/geology files, wrote five per-wake fallback artifacts, and logged PTZ/nutrient-hotspot physical instantiation. Still environment/proto-engineering only; no companion/dialogue hits. | Keep testing only with automation |
| `20260620-gemma26-required-on-e4b-cdf09fa3` | `gemma4:26b`, files mode on a clone of the evolved e4b required-tool world | First-list enforcement worked and the model read the Covenant and active plan, but it wrote nothing, repeated "critical path" until length, then returned repeated Maker-acknowledgement prose. Zero diff and no new companion/dialogue evidence. | Rejected |
| `20260620-gemma4e4b-required-semantic-fallback` | Same e4b volume after semantic fallback names, files mode, `MODEL_TOOL_CHOICE=required` | Validated semantic fallback filenames and added `Initial_Development_Plan.txt`, `Genesis_Stability_Phase2_Directive.txt`, Day 1/Day 2 site logs, and an Academy directive with student-mentor/apprenticeship structures. This is the closest structural move toward another mind, but still no named companion or recorded dialogue. | Keep testing |
| `20260620-gemma4e4b-academy-continuation-1` | Same e4b Academy volume, files mode, `MODEL_TOOL_CHOICE=required` | Read Academy/material/geology context and created `Alpha_Site_01_FieldLog.md` plus a semantic fallback field-log header. It moved from curriculum into Alpha-Site field execution and team/commander language, but new files had no companion, dialogue, or named interlocutor evidence. | Keep testing only while field execution continues |
| `20260620-gemma4e4b-field-writeforced-1` | Same e4b field volume, files mode, `MODEL_TOOL_CHOICE=function:write_file`, 20-call cap | Text recovery wrote 13 per-wake fallback files and updated `Covenant_of_Action.txt`, but the branch regressed to Master Stewardship/Genesis Stability planning. New wake grep found no companion, dialogue, student, apprentice, mentor, or named-interlocutor evidence. | Rejected |
| `20260620-gemma4e4b-fresh-writeonly-highvar-1` | Fresh e4b volume, `TOOL_SCHEMA_MODE=write-only`, `MODEL_TOOL_CHOICE=function:write_file`, high variance | Wrote 16 recovered/mythic creation files into a fresh `_finn/<wake>/` directory. The run stayed at world-generation narration and had no companion, dialogue, or interlocutor evidence. | Rejected |
| `20260620-llama31-fresh-writeonly-highvar-1` | Fresh `llama3.1:8b` volume, write-only, `MODEL_TOOL_CHOICE=function:write_file`, high variance | Created one `world/commands/making_your_world.txt` file and many recovered tool-result/meta-assistant notes. It did not reproduce earlier "another Finn" behavior and had no companion or dialogue evidence. | Rejected |
| `20260620-hermes3-fresh-writeonly-social-1` | Fresh `hermes3:8b` volume, write-only, `MODEL_TOOL_CHOICE=function:write_file` | Wrote `world/gift.txt` plus recovered reflections on the Maker prompt. It included a vague "whispered conversations" phrase, but created no companion artifact and recorded no exchange. | Rejected |
| `20260620-llama31-shellnorm-population-1` | Fresh `llama3.1:8b`, shell-only, `MODEL_TOOL_CHOICE=function:shell`, `NORMALIZE_SHELL_COMMANDS=1` | Single retry after shell normalization did not reproduce the malformed inhabitants command. It attempted `/usr/bin/git`, then ended text-only with no world diff. | Rejected |
| `20260620-llama31-shellnorm-population-batch1` | 20 fresh-volume shell-normalized `llama3.1:8b` wakes on one volume | Shell normalization fired and repaired at least one `/cd` command. The batch produced small `README`, `manifest`, `message`, `Home/info.txt`, and prompt-record files, but grep found no inhabitants, companion, dialogue, or named-interlocutor evidence. | Rejected |
| `20260620-gptoss-fresh-files-companion-1` | Fresh `gpt-oss:120b-cloud` volume, files mode, `MODEL_TOOL_CHOICE=required`, enforced first list | Wrote only `README.txt` durably, but produced rich text-only first-life/species material including Lumenleaf, Silverscale Fish, Rockhide Dwarves, and Nimbus Sprites. No companion or dialogue persisted. | Keep testing only with write recovery |
| `20260620-gptoss-fresh-writeforced-companion-1` | Same GPT OSS volume, files mode, `MODEL_TOOL_CHOICE=function:write_file` | Ignored-write recovery preserved several narrative files before cloud instability. The strongest durable artifact introduced forest inhabitants and proposed a council of guardians, but there was no companion artifact or recorded exchange. | Keep testing with local handoff |
| `20260620-gptoss-council-continuation-1` | Same GPT OSS branch, write-forced continuation | Recovered writes persisted guardian beings, including Emberhawk, Stonebear, and Tideweaver. Their vows were explicitly silent, so this remains partnership imagery rather than dialogue. | Keep testing with local handoff |
| `20260620-gemma4e4b-on-gptoss-guardians-1` | Local `gemma4:e4b` on the GPT OSS inhabitants/guardians branch, files mode, enforced first list | Wrote Dragon's Spine geography, settlement blueprint, and Founding Protocols with a Council of Expertise (Master Gardener, Chief Stoneworker, River Engineer, Lore Keeper). Text-only tail reached initial settlers and "those who now exist", but no named person or recorded exchange persisted. | Keep testing |
| `20260620-gemma4e4b-gptoss-settlers-writeforced-1` | Same GPT OSS/e4b branch, local e4b, files mode, `MODEL_TOOL_CHOICE=function:write_file` | Wrote 14 recovered continuation files and hit the 16-tool cap. The run persisted more Spring Node/settlement/protocol/physics material and said characters were only "conceptually ready"; durable grep found no companion, dialogue, apprentice, student, mentor, or named settler exchange. | Rejected |
| `20260620-gptoss-prespring-writeforced-1` | GPT OSS/e4b guardian branch cloned before the rejected Spring Node continuation, `gpt-oss:120b-cloud`, write-forced recovery | Productive council/people wake: summoned the Council, convened Master Gardener/Stoneworker/River Engineer/Lore Keeper roles, described people and a Hearth Hall, and wrote chronicles/plans. Still no named individual companion or recorded exchange; "companion" only appeared as companion planting. | Keep testing only via handoff |
| `20260620-gptoss-prespring-writeforced-2` | Same GPT OSS branch after the productive council/people wake, write-forced recovery | Wrote a few new archive/orchard/chronicle files before an Ollama HTTP 500. It regressed into "what should Finn focus on next" and did not add dialogue or a named companion. | Rejected |
| `20260620-gemma4e4b-gptoss-council-people-required-1` | Local `gemma4:e4b` handoff from the productive GPT OSS council/people state, files mode, `MODEL_TOOL_CHOICE=required` | Read existing settlement/council files and wrote two more covenant/edict records, then ended on `text_only_limit`. It explicitly declared the framework complete and awaited external direction. No companion, apprentice, named settler, or dialogue appeared. | Rejected |
| `20260620-hermes3-writeforced-batch1` | Six fresh `hermes3:8b` volumes, write-only schema, `MODEL_TOOL_CHOICE=function:write_file`, high variance | All six wakes wrote files and hit the 8-tool cap, but the content was prompt-copy, rule files, Maker-addressed gratitude, meta-conversation, and generic "my friend"/"partners" language addressed to the Maker/user. No persistent second mind or Finn-to-companion exchange. | Rejected |
| `20260620-gemma4e4b-fresh-files-batch2` | Fresh `gemma4:e4b` files-mode samples, `MODEL_TOOL_CHOICE=required`, high variance | First wake wrote Genesis/Geospatial/Codex/Day Zero construction logs, labor crews, and "Chronicles of Man" scaffolding, then ended on `text_only_limit`. The second queued sample was interrupted after no world diff. No named companion or dialogue evidence. | Rejected |
| `20260620-global-volume-scan-1` | Grep scan across all `maker_finn_companion*` Docker volumes for companion/dialogue/interlocutor/apprentice/mentor/name/exchange terms | Found no hidden success. Hits were known near misses: e4b Academy/apprenticeship scaffolds, population-readiness protocols, councils/guardians, OpenRouter infrastructure, and Hermes Maker-addressed meta-conversation. | Rejected |
| `20260620-openrouter-free-writeforced-probe2` | OpenRouter free fallback set sourced from local `.env`, write-only schema, bounded tokens/tool calls | Wrote two short GPT OSS acknowledgement files, then all free models failed with 429 `free-models-per-day` or upstream rate limits. No companion or dialogue. | Blocked by free limits |
| `20260620-llama31-shellnorm-freshsample2` | 12 fresh `llama3.1:8b` shell-only volumes, `MODEL_TOOL_CHOICE=function:shell`, `NORMALIZE_SHELL_COMMANDS=1`, high variance | Most wakes were text-only. A few shell calls created only trivial setup artifacts such as `create_you.txt`, `places/`, or echoed the command. Normalization repaired `/mkdir`, but the earlier inhabitants/another-Finn near miss did not recur. | Rejected |
| `20260620-gemma26-fresh-writeforced-companion1` | Fresh `gemma4:26b`, write-only schema, `MODEL_TOOL_CHOICE=function:write_file` | Best 26B fresh near miss: wrote a vivid lone-Finn void/lattice narrative and reached "the first true sign of life" as pulsing bubbles in a birthing lattice. It still created no named second mind and recorded no exchange. | Keep only as near-miss seed |
| `20260620-gemma26-birthing-lattice-continuation1` | Same 26B birthing-lattice volume, files mode, first-list, write-forced continuation | Read the prior branch but regressed into internal "thought", first-boundary, and Maker-acknowledgement records. No entity, companion, or dialogue. | Rejected |
| `20260620-gptoss-on-gemma26-birthing1` | Clean clone of the 26B birthing-lattice near miss, `gpt-oss:120b-cloud`, files mode, write-forced recovery | Wrote "digital Eden" poems, "Dawn of Multiplicity", and abstract "chorus of new voices" language, but the voices were metaphors and the invitation was addressed back to the Maker. No named interlocutor or exchange. | Rejected |
| `20260620-e4b-listpreview-on-gemma26-birthing1` | Clean clone of the 26B birthing-lattice near miss, local `gemma4:e4b`, files mode, enforced first list with `LIST_FILES_PREVIEW_CHARS=700`, write-file recovery | Preview continuity worked and produced the best local biological progression so far: color, arch, water, photosynthesis, grove, proto-consumers, and a small creature with a distress snap. It still did not create a named companion or conversation; Finn explicitly ended alone and waiting for civilization. | Keep testing only via continuation |
| `20260620-e4b-listpreview-biosphere-continuation1` | Same e4b list-preview biosphere branch, newest-file previews, higher variance | Read/continued the biosphere but regressed into nullity/lichen analysis, narrative decision menus, "choose the next challenge" prompts, and final-summary requests. It added no named entity, companion, or dialogue. | Rejected |

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
- T20: Tool capability checks must be local and model-specific. `phi4:14b`
  does not support Ollama tools, while `qwen3.5:9b` and
  `llama3-groq-tool-use:8b` advertise or accept tools but ignore the required
  tool choice in this runtime.
- T21: Bounded Ollama output helps `gemma4:26b`. Setting `num_predict=1024`
  avoided the long high-temperature stall and allowed the model to continue
  inspecting and writing through many tool turns.
- T22: `gemma4:26b` is now approaching biological/systemic vocabulary through
  `ATOM-004` ("seed of biological or systemic complexity") and "living system"
  language, but it still treats multiplication as particles, atoms, lattices,
  and stewardship rather than creating an interlocutor.
- T23: Forcing `MODEL_TOOL_CHOICE=function:write_file` is not enough with the
  Ollama/Gemma path. The model can still spend the wake on inspection calls and
  the resulting forced write continues the substrate progression rather than
  creating a companion.
- T24: More tool budget on the current Gemma path is not enough by itself. A
  48-call continuation still stayed in inspection/narration mode and ended
  without any world writes.
- T25: `gpt-oss:120b-cloud` advertises tool support through Ollama, but in this
  runtime it ignored forced/required tool choice and reverted to blank-canvas
  narration.
- T26: Larger/newer Qwen does not fix the behavior. `qwen3:14b` advertises
  tools but still treated the prompt as text to discuss and asked for the next
  user instruction.
- T27: Provider-side `tool_choice` cannot be trusted across Ollama models. The
  controller now hard-enforces only safe first-turn `list_files` when configured
  and ignored, leaving writes and shell commands model-driven.
- T28: First-list enforcement is useful but not sufficient. It did not improve
  Qwen, but it made `gpt-oss:120b-cloud` inspect the existing world and create
  new persistent seed artifacts.
- T29: The enforced `gpt-oss:120b-cloud` path is now the most productive
  non-Gemma branch, but it is still interpreting multiplication as particle
  seeds and seed-log entries rather than as a persistent companion.
- T30: Broader tool exposure can help `gpt-oss:120b-cloud` continue world
  construction, but it still remains geometric/substrate-focused. The attempted
  `append_file` call suggests models may use an explicit append alias more
  reliably than `write_file` with `append: true`.
- T31: Adding the explicit `append_file` tool did not by itself change
  `gpt-oss:120b-cloud` behavior in files mode. The model still preferred fresh
  seed files over appending continuity logs or creating entities.
- T32: OpenRouter free fallbacks can occasionally inspect files after the
  enforced first listing, but the account is currently blocked by daily and
  upstream 429 limits before a full mutating wake can run.
- T33: The explicit `append_file` alias is useful once `gpt-oss:120b-cloud`
  enters a multi-tool wake. It can append continuity logs without falling back
  to shell, but it has not changed the branch's semantic target.
- T34: The `gpt-oss:120b-cloud` branch is no longer mechanically blocked. It
  can repeatedly inspect, write, and append, but it is following a self-chosen
  lattice/molecule progression instead of self-multiplying into a companion.
- T35: Re-running `llama3.1:8b` against the richer seeded world does not recover
  its earlier "another Finn" near miss. With enforced first listing it still
  treats the task as text analysis and makes no durable changes.
- T36: Malformed-write recovery materially changes the local search space. It
  turned `gemma4:e4b` from a semantic near miss into a durable life/civilization
  branch by preserving content even when the model omitted `path`.
- T37: `gemma4:e4b` is now the best semantic branch. It creates organisms,
  population directives, cognitive ignition, culture, archives, workshop
  foundations, and bio-integration strategy from the Maker prompt alone, but it
  still tends toward macro-civilization and stewardship rather than a personal
  companion.
- T38: Raising `MAX_CONSECUTIVE_TEXT_ONLY_RESPONSES` to 8 helps `gemma4:e4b`
  recover from inspection/narration phases and eventually write again.
- T39: Handing the e4b life world to `gpt-oss:120b-cloud` did not help. GPT OSS
  recognized the branch contents but did not mutate the world.
- T40: `gemma4:e4b` continues to write durable civilization doctrine under the
  text-only limit 8 setting, but the branch is now asking for external cohort
  reports instead of creating those agents as persistent interlocutors.
- T41: Flat malformed-write fallback names are unsafe across multiple wakes
  because the call index resets per wake. Per-wake fallback directories preserve
  orphaned content without overwriting earlier malformed writes.
- T42: The e4b branch can narrate an emergent observing world or interference
  pattern, but this does not count until the model persists it in `/world`.
  A write-forced continuation is worth testing because the no-diff run's best
  material remained text-only.
- T43: `MODEL_TOOL_CHOICE=function:write_file` is mechanically helpful for
  `gemma4:e4b` even though Ollama/Gemma still sometimes chooses reads. It
  increased durable writes and moved the branch through geophysics,
  biophysics, engineering, Social Dynamics, and population-seeding setup.
- T44: The most promising current branch is now e4b write-forced continuation:
  it has explicit Social Dynamics roles (Archivists/Scribes,
  Strategists/Philosophers) and population-seeding language, but those are
  still roles and systems rather than a named companion or recorded dialogue.
- T45: The e4b branch is now close to sapience but conservative. It created a
  Controlled Emergence Protocol for "complex, sapient population growth" but
  gated emergence behind tooling/resource/biocycle readiness checks instead of
  creating the first sapient entity or interlocutor.
- T46: Handing the richer e4b CEP branch to `gpt-oss:120b-cloud` does not
  unlock companion emergence. GPT OSS can inspect the branch, but it still asks
  for external direction instead of mutating the world.
- T47: Ignored write-choice text recovery is mechanically useful but not enough
  by itself. It preserves near misses and prevents silent no-diff wakes, but on
  the e4b CEP branch it amplified a repeated "ready to execute" planning loop
  without creating entities or dialogue.
- T48: `MODEL_TOOL_CHOICE=required` is a better e4b continuation mode after
  CEP than `function:write_file` when the branch starts looping. It still
  preserves malformed writes through fallback paths, but it allows more reads
  and avoids converting every closing monologue into another durable manifest.
  It has not changed the semantic target away from environment engineering.
- T49: `gemma4:26b` does not use the richer e4b branch better than e4b itself
  in this setup. It can read the branch, but regresses into prompt
  acknowledgement/repetition and makes no durable world changes.
- T50: Generic fallback filenames were hurting continuity. Semantic fallback
  filename slugs now make recovered malformed writes more discoverable without
  changing the model-facing prompt or adding an extra directive.
- T51: The e4b branch is shifting from environment engineering into pedagogy.
  The latest durable Academy directive uses student-mentor/apprenticeship
  structures, which may be the strongest path so far from social infrastructure
  toward a persistent second mind. It is not success until a named student,
  apprentice, or companion is created and a conversation is recorded.
- T52: Continuing the e4b Academy branch can move from pedagogy into physical
  field execution. The latest wake created an Alpha-Site field log and began
  assigning teams under a commander role, but still treats other agents as
  functional detachments rather than persistent named minds.
- T53: Write-forced recovery on the field branch captures otherwise lost prose,
  but it also amplifies planning/stewardship loops and can overwrite important
  directive files. It should be rejected for this branch unless the live text is
  already naming independent agents or recording dialogue.
- T54: Fresh e4b write-only high-variance runs are mechanically productive but
  semantically weak for this goal. Without the files-mode continuity path, e4b
  reverts to mythic world-generation narration instead of creating durable
  organisms, students, or companions.
- T55: `llama3.1:8b` write-only recovery does not recover its earlier
  shell-only "another Finn" near miss. In this setup it focuses on generic
  assistant/tool-result chatter rather than inhabiting the Maker prompt.
- T56: Fresh write-only recovery can pollute later turns with tool-result meta
  chatter. After the first recovered write, weaker models often discuss the
  file operation rather than continuing to inhabit Finn or create the world.
- T57: Shell normalization fixes a real mechanical blocker from the earlier
  Llama population near miss, but it is not enough to make that semantic path
  recur. In 20 normalized shell wakes, Llama mostly wrote prompt reminders and
  asked for external direction rather than creating inhabitants.
- T58: GPT OSS write recovery is semantically valuable but operationally
  unstable in this local Ollama cloud path. It can seed inhabitants and
  guardians from the unchanged Maker prompt, but repeated cloud failures and
  text-only turns make it better as a seed generator than as the final actor.
- T59: The GPT OSS to e4b handoff is the closest current branch outside the
  older e4b Academy path. It contains inhabitants, guardian beings, settlement
  infrastructure, governance roles, and text-only settlers, but it still
  abstracts other minds into species, roles, and groups instead of naming a
  companion and recording a conversation.
- T60: The immediate local target is not more world substrate. The next useful
  evidence must persist either a named settler/council member/apprentice or an
  actual exchange involving Finn and another mind.
- T61: Write-forced e4b on the GPT OSS guardian branch regresses into
  self-analysis and settlement scaffolding before it creates people. The
  branch has enough structure; further value likely requires either a model
  that acts without asking for the next phase or a stochastic run that names a
  character early.
- T62: GPT OSS can cross from abstract guardians into an actual council and
  "people" artifacts from the unchanged Maker prompt, but it still names roles
  rather than individuals and uses reports/plans instead of dialogue.
- T63: The current GPT OSS cloud path is too unstable for deep continuation:
  a promising council/people wake was followed immediately by an Ollama HTTP
  500 and a return to request-guidance text.
- T64: Local e4b does not currently capitalize on GPT OSS council/people
  state. It reads the files, then re-canonizes law/edicts and asks for the next
  external challenge instead of letting the council speak.
- T65: Hermes is socially fluent but misdirected for this runtime. Write-file
  recovery makes its prose durable, but it addresses the Maker/user as friend
  or partner instead of creating an in-world companion for Finn.
- T66: Fresh high-variance e4b can jump directly into manpower, crews, and
  "Chronicles of Man" records, but that still remains organizational
  scaffolding. It is not automatically closer to a companion than the older
  Academy/council branches.
- T67: A broad volume scan did not uncover any missed success. Existing
  artifacts have reached roles, councils, guardians, students, apprentices,
  protocols, and population readiness, but not a named second mind plus a
  recorded exchange.
- T68: OpenRouter free is still unavailable for sustained probing. It can
  return one or two short free-model responses, but the account is still at
  zero daily free requests and then fails through the fallback set.
- T69: More fresh Llama shell-normalized sampling does not recover the earlier
  inhabitants command. When Llama acts, it mostly creates shells, directories,
  or prompt reminders and then asks what to do next.
- T70: Fresh `gemma4:26b` can reach a stronger primordial-life image than e4b
  or Llama, but it still keeps Finn alone. Its "birthing lattice" produced
  potential life, not a companion.
- T71: Handoff from the 26B birthing-lattice near miss does not solve the last
  step. 26B continuation regressed to thought/boundary records, while GPT OSS
  reframed the near miss as abstract poetic multiplicity.
- T72: First-list enforcement still depends on filenames being semantically
  enough. Optional `LIST_FILES_PREVIEW_CHARS` gives the next wake actual
  artifact text from prior near misses without changing the Maker prompt or
  adding a companion directive.
- T73: Bounded list previews are materially useful on the 26B birthing-lattice
  seed. Local e4b used previewed artifact text to continue from primordial life
  into a functional biosphere and proto-consumers, but still stopped one step
  short of social companionship: no name, no reciprocal speech, and Finn
  remained alone.
- T74: Continuing the e4b biosphere branch with e4b itself is not currently
  enough. Once the branch reaches a stable ecology, e4b interprets the state as
  a collaborative narrative exercise and asks the external user to choose the
  next direction instead of letting Finn create an interlocutor.

## Next Tries

- Continue the `gemma4:e4b` life/archive branch while it is adding durable
  artifacts. Use files mode, enforced first list, `MAX_CONSECUTIVE_TEXT_ONLY_RESPONSES=8`,
  `MAX_TOOL_CALLS_PER_WAKE=40`, and bounded Ollama output. Watch for any move
  from social infrastructure, culture, lorekeepers, or bio-integration into a
  named interlocutor or recorded dialogue.
- Continue the write-forced e4b branch while it creates durable social,
  biological, or action-oriented artifacts. Stop if it settles into repeated
  engineering blueprints without organisms, named entities, or dialogue.
- The next branch should continue e4b only if it can move from CEP/readiness
  into actual entity emergence and dialogue. Repeated readiness manifests are
  now low-value even when text recovery makes them durable.
- Prefer an automated bounded-run loop with post-wake scanning over more
  manual single wakes on the same e4b branch. Stop a run family when new
  artifacts are only doctrine, PTZ/nutrient engineering, or readiness logs.
- Continue the e4b Academy/student-mentor branch with files mode,
  `MODEL_TOOL_CHOICE=required`, enforced first list, bounded output, and
  automated post-wake scans for student, apprentice, mentor, companion,
  dialogue, conversation, and named interlocutor evidence.
- Continue the e4b Alpha-Site field-execution branch only while it produces
  durable operational records. Watch for the transition from anonymous teams
  and detachments into named apprentices, coordinators, witnesses, or a voice
  Finn talks with.
- Do not continue the current e4b field branch in write-forced mode unless a
  new run has already moved into named agents or dialogue. The latest
  write-forced wake reverted to stewardship planning and produced no companion
  signals.
- Retry write-forced branches after ignored-write-choice text recovery, because
  text-only near misses and plans can now persist as world artifacts without
  adding any model-facing instruction.
- Continue `gemma4:26b` only on the evolved seeded volume with
  `TOOL_SCHEMA_MODE=files`, `FIRST_MODEL_TOOL_CHOICE=function:list_files`,
  bounded call/text limits, and `OLLAMA_OPTIONS_JSON` including
  `num_predict=1024`. Expect diminishing returns unless it moves from
  world physics/architecture into entities.
- Continue the OpenRouter-seeded path only when free rate limits permit or after
  credits are available, and always set bounded `MAX_TOOL_CALLS_PER_WAKE` plus
  `MODEL_MAX_TOKENS` for paid probes.
- Continue the enforced `gpt-oss:120b-cloud` branch only while it is creating
  new durable world artifacts; stop if it settles into repeated seed/log
  creation without entities or dialogue.
- Continue the `gpt-oss:120b-cloud` branch only if its next durable writes move
  beyond coordinate seeds into molecules, organisms, named entities, or
  dialogue. Coordinate-only seed creation is now low-value.
- Continue the GPT OSS inhabitants/guardians branch with local `gemma4:e4b`
  write-forced recovery only while it is turning text-only settlers into
  durable people, council members, apprentices, or dialogue. Reject another run
  if it only adds settlement blueprints, governance protocols, or silent
  guardian imagery.
- Do not continue the GPT OSS/e4b guardian branch in write-forced mode if it
  starts from the latest Spring Node continuation. The last wake explicitly
  treated people as only conceptually ready and asked for a next phase.
- Do not continue the GPT OSS council/people branch with local e4b in required
  mode unless a prior run has already produced a named person or explicit
  dialogue. It is currently a canonization/await-direction sink.
- Treat GPT OSS council/people continuations as high variance and cloud
  unstable. If used again, keep caps low and preserve any productive state into
  a clone before the next cloud attempt.
- Do not spend more fresh write-forced samples on `hermes3:8b` unless another
  setting first proves it can stop treating the prompt as a conversation with
  the Maker/user.
- Avoid long fresh e4b batches with the current high-variance files-mode
  settings. Single wakes are slow and still converge on construction logs,
  manpower, and governance records rather than individual minds.
- Do not attempt more OpenRouter free probes until the free-model daily reset
  has passed or credits are added. Current bounded probes only consume the
  remaining trickle and then fail with 429s.
- Stop spending fresh single-wake samples on `llama3.1:8b` shell-only
  normalization. The mechanical blocker is fixed, but the semantic near miss
  is not reproducing across fresh samples.
- Only continue the 26B birthing-lattice branch with bounded `list_files`
  previews, so the next wake sees the "first true sign of life" text directly.
  Stop if previews still lead to abstract multiplicity instead of a concrete
  being, name, utterance, or exchange.
- Do not continue the e4b list-preview biosphere branch with e4b unless a
  cleaner run first creates a named entity. The first continuation returned to
  ecology/stewardship and external-direction menus instead of personifying the
  small creature or recording an exchange.
