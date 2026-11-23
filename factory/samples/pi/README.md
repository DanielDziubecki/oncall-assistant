# Pi JSON samples

Real output of `pi -p --mode json --no-tools --model <model> "Reply with OK"` from the Pi trial
(ADR 8), Pi 1.6.0, for tests that read Pi's event stream.

| File | Provider and model |
|---|---|
| `claude.jsonl` | `claude-code/claude-haiku-5-5`, through `pi-claude-code` at `d5b5e04` |
| `openai.jsonl` | `openai-codex/gpt-6.2-sol`, ChatGPT subscription |

Replaced before committing; everything else is unchanged:

- session, message, request and response ids, by zero or `SAMPLE` placeholders of the same form
- in `claude.jsonl`, the account's rate-limit state: `utilization`, `resetsAt` and `overageDisabledReason`
