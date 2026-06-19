# Needs Verification

Claims in this file should not be promoted into normal docs until they are
verified from current source, tests, commands, or live provider checks.

## Moved From Old README

The previous README listed free OpenRouter tool-calling candidates and probe
results. Those claims depend on current external provider behavior and were not
reverified during this docs pass:

- `nex-agi/nex-n2-pro:free`: probe emitted `shell`; real wake wrote files into
  `/world`.
- `poolside/laguna-m.1:free`: probe emitted `shell`.
- `cohere/north-mini-code:free`: probe emitted `search`.
- `openrouter/free`: probe emitted `shell`, but one real wake routed to
  text-only models several times.
- `qwen/qwen3-coder:free`: listed as tool-capable, but local probes hit upstream
  rate limits.
- `openai/gpt-oss-120b:free`: listed `tools` and `tool_choice`, but a local
  probe returned text-only output.

## Runtime Claims To Verify

- Docker Compose controller service starts correctly with the host Docker socket
  and `./maker-place` bind mount.
- Long-running loop behavior over many wake intervals on the intended host.
- Current Ollama model availability and tool-call behavior on this machine.
- Current OpenRouter model availability, pricing/free status, and tool-call
  behavior.

## Related

- [Project status](../status.md)
- [Environment reference](../reference/env.md)
- [Missing features](missing-features.md)
