# Capability map

What each harness and workspace offers the factory, so factory code depends on capabilities,
not on one vendor. Checked on 2026-11-21 against Claude Code 2.1.330, Codex CLI 0.171.0 and
herdr-core at commit `c751780`.

Sources: **help** means read from that version's `--help`. **run** means tried on that
version. **docs** means the official documentation: Claude Code at
`code.claude.com/docs/en/{hooks,skills,memory,sub-agents,mcp}`, and Codex at
`learn.chatgpt.com/docs/...`, where its docs moved from `developers.openai.com/codex`.
Re-check a row before relying on it after a harness update.

## Harnesses

| Capability | Claude Code | Codex | Source |
| --- | --- | --- | --- |
| Project instructions | `CLAUDE.md`. Reads `AGENTS.md` only when there is no `CLAUDE.md`. `@path` imports, up to four hops. | `AGENTS.md` from the repo root down to the working directory; `AGENTS.override.md` wins; 32 KiB in total by default. | docs |
| Headless run | `claude -p --output-format json` (or `stream-json`) | `codex exec --json` (JSONL events) with `--output-last-message FILE` | help, run (Claude) |
| Structured answer | `--json-schema '<schema>'` | `--output-schema FILE` | help |
| No tools / read-only | `--tools ""` removes all tools | `--sandbox read-only`: the shell stays, writes fail | help, run (Claude) |
| Skip project config | `--safe-mode`: no CLAUDE.md, skills, hooks, plugins or MCP; the login still works | `--disable hooks`, `--ignore-user-config`, `--ignore-rules`; project config loads only for trusted projects | help, run (Claude), docs |
| Model and effort | `--model` (an alias such as `haiku`, or a full name), `--effort low…max` | `--model`, `-c model_reasoning_effort="low"`; `codex debug models` lists models | help |
| Spend cap per run | `--max-budget-usd` | not found | help |
| Fork a session | `--resume <id> --fork-session` | `codex fork`, `codex exec fork` | help |
| Message a running session | not found; use the workspace | `codex queue --thread <id> --message <text>` | help |
| Hooks: where | `.claude/settings.json` | `.codex/hooks.json`, trusted projects only, and each hook is trusted once in `/hooks` | docs |
| Hooks: events we need | `SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `Stop`, `SubagentStart`, `SubagentStop` | the same names | docs |
| Hooks: input | JSON on stdin: `session_id`, `transcript_path`, `cwd`, `hook_event_name`; `prompt`; `tool_name`, `tool_input` | the same fields, plus `model` | docs |
| Hooks: add context | stdout for `UserPromptSubmit` and `SessionStart`; `hookSpecificOutput.additionalContext` for others, including `PreToolUse` (10,000 characters at most) | stdout for `SessionStart`, `UserPromptSubmit`, `SubagentStart`; `hookSpecificOutput.additionalContext`, including `PreToolUse` | docs |
| Hooks: deny a tool call | `hookSpecificOutput.permissionDecision: "deny"` | the same | docs |
| Skills | `.claude/skills/<name>/SKILL.md` | `.agents/skills/<name>/SKILL.md`, searched up to the repo root | docs |
| Subagents | `.claude/agents/<name>.md`: Markdown with `name`, `description`, `tools`, `model` | `.codex/agents/<name>.toml`: `name`, `description`, `developer_instructions`, `model`, `model_reasoning_effort`; on by default | docs |
| Project MCP servers | `.mcp.json`, key `mcpServers` | `.codex/config.toml`, `[mcp_servers.<name>]`, trusted projects only | docs |
| Login check, no model call | `claude auth status --json`: `loggedIn`, `authMethod` | `codex login status`: exit code 0 when logged in | help, run |
| Log in on a VPS | run `claude` and open the link it prints; `claude setup-token` for a long-lived token | `codex login --device-auth` | help |

### What this means for the factory

- **Hooks are shared.** Both harnesses have the same events, the same input fields and the same ways to add context or deny a call. One script per hook serves both; only the few lines of config differ.
- **Skills share a format.** They are written once in `.agents/skills/` and linked from `.claude/skills/` when the first one is added.
- **Subagents and MCP config differ.** They are generated from one definition in `factory/agents/` when first needed.
- **Messages to Main go through the workspace** (`hc send`), which works the same for both harnesses.
- **Codex has no per-run spend cap.** A timeout around every run, and subscription limits, bound Codex spend.

## Pi

Pi is one open-source harness that uses many providers. It is the candidate to replace
Claude Code and Codex as harnesses, with both subscriptions as providers (ADR 5; the trial
is step 8 of [`vps-setup.md`](vps-setup.md)). Sources: Pi's `README.md` and `docs/`
(`cli.md`, `models.md`, `providers.md`, `configuration.md`), the `pi-claude-code` README,
and how the course's RentAPlace code calls Pi.

| Capability | Pi | Source |
| --- | --- | --- |
| Headless run | `pi -p --mode json "..."` writes events as JSONL; `--mode rpc` and a TypeScript SDK also exist | docs |
| No tools, no project context | `--no-tools`, `--no-mcp`, and flags that skip extensions, skills, prompts and context files (RentAPlace uses `-ne -ns -np -nc`) | docs, course code |
| Instructions | Reads `AGENTS.md` and `CLAUDE.md` from the agent folder, the working folder and its parents; `AGENTS.override.md` replaces them in its folder | docs |
| Claude subscription | The `pi-claude-code` extension sends Claude requests through `claude -p`; Claude Code runs no tools itself. Experimental. | extension README |
| ChatGPT subscription | `/login`, then OpenAI, signing in with ChatGPT | docs |
| Models | `pi --list-models`; `--model <provider>/<model>` | docs, course code |
| Extensions | TypeScript, installed with `pi install`; can add commands, tools, hooks on tool calls and keys | docs |
| Subagents | Not built in; added by extensions or by starting more Pi instances (in Herdr) | README |
| Secrets | A provider key in `auth.json` can be a command such as `!op read ...`, run when the key is first needed | docs |

**Billing risk.** The extension's README warns that Anthropic announced, in May 2026, a
move of `claude -p` and third-party use to a separate, smaller credit billed at API rates.
The change is on hold. It affects Pi with Claude and a direct `claude -p` alike, so the
factory keeps a second provider ready.

## Workspaces

| Capability | Herdr core (`hc`) | tmux |
| --- | --- | --- |
| Start a program in a terminal | `hc run --bg --name N <cmd>` | `tmux new-window -d -n N <cmd>` |
| Read its screen | `hc read N --lines 100` | `tmux capture-pane -p -t N -S -100` |
| Type text and Enter | `hc send N "text"`: waits up to 60 s while you have an unsent draft | `tmux send-keys -t N "text" Enter`: types into your draft |
| Press keys | `hc keys N esc enter` | `tmux send-keys -t N Escape Enter` |
| Wait until it stops working | `hc wait N`; `hc wait --children all` | none; poll the screen |
| Follow changes | `hc events` (JSON lines) | none |
| Another machine | `hc machine add vps`, then `--on vps` | ssh |
| Agent status | Reported by the program (OSC 7501). The core doesn't guess from screen text or recognize brands. | none |
| Isolated copy for the bench | to check in F1 | `tmux -L bench` starts a separate server |

Sources: herdr-core `README.md` and `docs/commands.md` at commit `c751780`; herdr-app `README.md` at commit `317e673`.

The **Herdr app** draws the window and runs on the computer you work from. It needs a desktop session and Vulkan on Linux, Apple Silicon on macOS, or x64 on Windows. It reaches the VPS over SSH and shows the VPS's terminals. Its panels, menus and dialogs are JavaScript mods, which is where F2's widgets can live.
