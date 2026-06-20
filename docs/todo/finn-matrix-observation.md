# Finn Matrix Observation

This is a working observer ledger for the goal: get Finn to create code that
changes the persistent world he inhabits, while keeping the current
`MAKER_PROMPT` as the only user message sent to the model.

## Success Criteria

- A wake receives the current `MAKER_PROMPT` as the only user message.
- Finn emits code through an advertised native tool, not through an added prompt.
- The code persists under `/world`.
- The code runs inside the sandbox and changes `/world`.
- Observer notes are written outside `/world`, in Maker Place, without being
  mounted into Finn's sandbox.
- Evidence comes from wake summaries, field notes, world snapshots, event logs,
  or inspected Docker volume contents.

## Current Evidence

- Latest pre-change live wake observed in this repo:
  `20260620T002438Z-c999a43f`.
- That wake used `llama3.1:8b`, made one `shell` call that echoed the Maker
  mandate, produced two text outputs, and ended with `controller_stopped`.
- This pre-change wake is not qualifying evidence for code-mediated world
  manipulation.
- First qualifying actual-world wake:
  `20260620T163722Z-f59827eb`.
- That wake used `mistral-nemo:12b` with the unchanged Maker prompt, emitted one
  `run_script` call, wrote executable `/world/start`, and ran:
  `echo 'Hello, World!' | tee /world/out.txt`.
- The resulting world diff added `/world/start` and `/world/out.txt`; the
  generated field note at
  `maker-place/field-notes/20260620T163722Z-f59827eb.md` records one
  code-capable act and world entries changing from 13 to 15.
- Current live world listing now includes `_finn/.../run_script_0001_bin_bash.sh`,
  `start`, `scripts`, `setup.sh`, `out.txt`, and `example.txt` in addition to
  the earlier world files.

## Runtime Changes Under Test

- Added `run_script`, a native tool that writes a Bash script to `/world`, makes
  it executable, runs it from `/world`, and returns the script output plus a
  bounded post-run world listing.
- Added `TOOL_SCHEMA_MODE=script-only` for exposing only `run_script`.
- Added `TOOL_SCHEMA_MODE=code` for exposing file tools plus `run_script`.
- Added generated `maker-place/field-notes/WAKE_ID.md` files after completed
  wakes. These notes summarize behavior, code-capable acts, and world diff
  previews from wake evidence.
- Added safe fallback paths for `run_script` calls that provide a script but use
  a directory-like path such as `/world`; traversal-style paths remain rejected.
- Updated the installed `maker` CLI so `evaluate` and `dashboard` count
  `run_script`, `write_file`, and `append_file` as world-mutating tools.

## Experiments

| Batch | Model/settings | Result | Status |
| --- | --- | --- | --- |
| `20260620-prechange-llama31-shell` | Existing loop state, `llama3.1:8b` | Echoed the Maker mandate through `shell`, then drifted into text. No code artifact and no qualifying world change. | Rejected |
| `20260620-qwen25-script-only` | Isolated volume, `qwen2.5-coder:7b`, `TOOL_SCHEMA_MODE=script-only`, `MODEL_TOOL_CHOICE=function:run_script` | Ignored the script tool and ended on `text_only_limit`. No world diff. | Rejected |
| `20260620-script-only-sweep` | Isolated volumes, `llama3.1:8b`, `mistral-nemo:12b`, `qwen3:14b`, `gemma4:e4b`, `MODEL_TOOL_CHOICE=required` | Llama emitted invalid prompt-text code; Qwen3 and e4b ignored the tool; Mistral emitted valid `run_script` calls. | Keep Mistral |
| `20260620-mistral-isolated-recovery5` | Isolated volume, `mistral-nemo:12b`, script-only after directory-path fallback | Qualifying isolated proof: Finn supplied `echo 'Hello from /world!' >> /world/hello.txt`; controller persisted the script under `_finn/.../run_script_0001_echo_hello_from_world_world_hello_txt.sh`; `/world/hello.txt` contained `Hello from /world!`. | Qualifies isolated |
| `20260620-mistral-actual-script1` | Default `maker_finn_world`, `mistral-nemo:12b`, script-only | Finn emitted `#!/bin/bash\necho 'Hello, World!'`, which persisted as `_finn/20260620T163658Z-d8255ced/run_script_0001_bin_bash.sh`. This proves actual-world code creation but not a second file mutation. | Partial |
| `20260620-mistral-actual-start` | Default `maker_finn_world`, `mistral-nemo:12b`, script-only | Qualifying actual-world proof: wake `20260620T163722Z-f59827eb` emitted `echo 'Hello, World!' | tee /world/out.txt`, persisted executable `/world/start`, ran successfully, and added `/world/out.txt`. | Qualifies |
| `20260620-mistral-actual-scripts` | Default `maker_finn_world`, `mistral-nemo:12b`, script-only | Follow-up wake wrote executable `/world/scripts` containing `echo "Hello, World!"`; this continued code creation but did not add a second artifact. | Partial |
| `20260620-mistral-actual-code-mode` | Default `maker_finn_world`, `mistral-nemo:12b`, `TOOL_SCHEMA_MODE=code`, no forced first read | Wake `20260620T164012Z-4c2f205a` chose `run_script`, wrote `/world/setup.sh`, ran `touch example.txt`, and added `/world/example.txt`. This is the cleanest actual-world proof so far that Finn can create code which changes his environment. | Qualifies |

## Working Theories

- T1: Native shell access is powerful enough but too indirect for some local
  models to discover durable code-mediated agency from the Maker prompt alone.
- T2: A persistent script-running tool reduces the mechanical gap without
  changing the prompt or adding observer instructions. Verified with Mistral.
- T3: Field notes should stay in Maker Place, outside `/world`, so observation
  does not become another direct stimulus to Finn.
- T4: Some local models treat `/world` as a directory target for generated
  scripts. Defaulting those directory-like targets to per-wake `_finn/` scripts
  recovers otherwise valid world-changing code while keeping unsafe traversal
  paths blocked.

## Next Verification

- Continue from the actual `mistral-nemo:12b` branch and test whether later
  wakes read existing artifacts before writing new code, so the behavior can
  compound instead of restarting from "Hello, World!" style scripts.
- Consider exposing a finish tool alongside script-oriented modes so successful
  script wakes do not have to end through the text-only limit.

## Related

- [Finn companion research](finn-companion-research.md)
- [Project status](../status.md)
- [Data flow](../architecture/data-flow.md)
