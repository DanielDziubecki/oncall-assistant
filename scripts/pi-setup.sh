#!/usr/bin/env bash
# Pi for the factory (ADR 8), the scripted version of step 8 in docs/factory/vps-setup.md.
#
# Run as dev on the VPS, in this repo, without sudo:
#   bash scripts/pi-setup.sh <command>
# Commands:
#   install   install the packages pinned in factory/pi-packages.txt, replacing other pins
#   check     what is installed, which logins work, the lab's doctor; asks no model
#   answers   one "Reply with OK" from each subscription with tools off, and the check that
#             AGENTS.md loads once. Writes Pi's JSON to $PI_TRIAL_DIR (default ~/pi-trial) and
#             copies without ids or account usage to its scrubbed/ folder.
#
# check and answers end with exit code 1 if anything is left to do.
# Logins are never done here: scripts/logins.sh runs them for you.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PACKAGES="$ROOT/factory/pi-packages.txt"
PI_GIT="${PI_CODING_AGENT_DIR:-$HOME/.pi/agent}/git"
CLAUDE_MODEL="${PI_CLAUDE_MODEL:-claude-code/claude-haiku-5-5}"
OPENAI_MODEL="${PI_OPENAI_MODEL:-openai-codex/gpt-6.2-sol}"
OUT="${PI_TRIAL_DIR:-$HOME/pi-trial}"
export PATH="$HOME/.local/bin:$PATH"

left=0
say() { printf '\n== %s\n' "$*"; }
line() { printf '  %-8s %s\n' "$1" "$2"; }
bad() { line "$1" "$2"; left=1; }

pinned() { grep -v '^[[:space:]]*\(#\|$\)' "$PACKAGES"; }
base_of() { printf '%s' "${1%@*}"; }
sha_of() { printf '%s' "${1##*@}"; }
dir_of() { local base; base="$(base_of "$1")"; printf '%s/%s' "$PI_GIT" "${base#git:}"; }
# every source in Pi's settings; `pi list` indents sources by two spaces and their paths by four
installed() { pi list 2>/dev/null | sed -n 's/^  \([^ /][^ ]*\)$/\1/p'; }
# installed sources of the same repo with another pin, or none
other_pins() { awk -v base="$(base_of "$1")" -v want="$1" '$0 != want && ($0 == base || index($0, base "@") == 1)'; }

need_pi() { command -v pi >/dev/null || { echo "pi is not installed: run vps-setup.sh tools first" >&2; exit 1; }; }

cmd_install() {
    need_pi
    local have want old
    have="$(installed)"
    while read -r want; do
        if grep -qxF "$want" <<<"$have"; then
            say "already pinned: $want"
            continue
        fi
        while read -r old; do
            [ -n "$old" ] || continue
            say "removing another pin of the same package: $old"
            pi remove "$old"
        done < <(other_pins "$want" <<<"$have")
        say "installing $want"
        pi install "$want"
    done < <(pinned)
    have="$(installed)"
    while read -r old; do
        [ -n "$old" ] || continue
        grep -qxF "$old" < <(pinned) || line note "$old is installed but not in factory/pi-packages.txt"
    done <<<"$have"
}

# Prints one line per lab doctor check. Missing parts of the Herdr workspace are notes: the lab
# needs the Herdr desktop app beside Pi, which a headless server doesn't have (ADR 8).
LAB_DOCTOR_JS='
let s = "";
process.stdin.on("data", d => s += d).on("end", () => {
  const j = JSON.parse(s);
  for (const c of j.checks) {
    const state = c.ok ? (c.note ? "note" : "ok") : (c.part === "workspace" ? "note" : "check");
    console.log(state + "\t" + c.name + ": " + c.detail);
  }
});'

cmd_check() {
    say "Pi"
    if command -v pi >/dev/null; then line ok "pi $(pi --version)"; else bad missing "pi (vps-setup.sh tools)"; return; fi

    say "packages pinned in factory/pi-packages.txt"
    local have want dir
    have="$(installed)"
    while read -r want; do
        dir="$(dir_of "$want")"
        if ! grep -qxF "$want" <<<"$have"; then
            bad todo "$(base_of "$want")   (bash scripts/pi-setup.sh install)"
        elif [ "$(git -C "$dir" rev-parse HEAD 2>/dev/null)" != "$(sha_of "$want")" ]; then
            bad check "$dir is not on the pinned commit"
        elif [ -n "$(git -C "$dir" status --porcelain --untracked-files=no)" ]; then
            bad check "$dir has local changes"
        else
            line ok "$(base_of "$want")"
        fi
    done < <(pinned)

    say "logins: 'done' works, 'todo' is left for you (bash scripts/logins.sh)"
    if claude auth status --text >/dev/null 2>&1; then line done "Claude Code, used by the claude-code provider"
    else bad todo "Claude Code login"; fi
    if pi auth check --provider openai-codex >/dev/null 2>&1; then line done "ChatGPT in Pi (openai-codex)"
    else bad todo "ChatGPT in Pi"; fi

    say "models"
    local models provider count
    models="$(pi --list-models 2>/dev/null || true)"
    for provider in claude-code openai-codex; do
        count="$(grep -c "^$provider " <<<"$models" || true)"
        if [ "$count" -gt 0 ]; then line ok "$provider: $count models"; else bad check "$provider lists no models"; fi
    done

    say "course extensions: lab doctor ('note' lines need the Herdr desktop app beside Pi)"
    local lab state text
    lab="$(dir_of "$(pinned | grep '/herdr-pi-lab@')")/lab.mjs"
    if [ ! -f "$lab" ]; then
        bad todo "herdr-pi-lab   (bash scripts/pi-setup.sh install)"
    else
        while IFS=$'\t' read -r state text; do
            if [ "$state" = check ]; then bad check "$text"; else line "$state" "$text"; fi
        done < <(node "$lab" doctor 2>/dev/null | node -e "$LAB_DOCTOR_JS")
    fi
}

# Prints the text of the last assistant message in a Pi JSON file.
REPLY_JS='
const lines = require("fs").readFileSync(process.argv[1], "utf8").trim().split("\n").map(JSON.parse);
const msg = lines.filter(e => e.type === "message_end" && e.message.role === "assistant").pop();
if (msg) console.log(msg.message.content.filter(b => b.type === "text").map(b => b.text).join(""));'

# Prints how many instruction files named AGENTS.md and CLAUDE.md Pi put in its system prompt.
CONTEXT_JS='
const lines = require("fs").readFileSync(process.argv[1], "utf8").trim().split("\n").map(JSON.parse);
const end = lines.find(e => e.type === "agent_end");
const system = end && end.messages.find(m => m.role === "system");
const context = (system && system.sections.project_context) || "";
const paths = [...context.matchAll(/<project_instructions path="([^"]+)">/g)].map(m => m[1]);
const count = name => paths.filter(p => p.endsWith("/" + name)).length;
console.log(count("AGENTS.md") + " " + count("CLAUDE.md"));'

ask_ok() {
    local name=$1 model=$2 folder=$3 reply
    if (cd "$folder" && timeout 180 pi -p --mode json --no-tools --model "$model" "Reply with OK" \
        >"$OUT/$name.jsonl" 2>"$OUT/$name.err"); then
        reply="$(node -e "$REPLY_JS" "$OUT/$name.jsonl")"
        if grep -qiE '^ok\.?$' <<<"$reply"; then line ok "$model replied OK"; return; fi
        bad check "$model replied: ${reply:0:80}"
    else
        bad check "$model failed; see $OUT/$name.err"
    fi
}

cmd_answers() {
    need_pi
    mkdir -p "$OUT/scrubbed"
    say "one answer from each subscription, tools off (files in $OUT)"
    ask_ok claude "$CLAUDE_MODEL" "$OUT"
    ask_ok openai "$OPENAI_MODEL" "$OUT"

    say "instructions load once, in $ROOT"
    ask_ok context "$CLAUDE_MODEL" "$ROOT"
    local agents claude
    read -r agents claude < <(node -e "$CONTEXT_JS" "$OUT/context.jsonl" 2>/dev/null || echo "0 0")
    if [ "$agents" = 1 ] && [ "$claude" = 0 ]; then line ok "AGENTS.md once, no CLAUDE.md"
    else bad check "Pi loaded AGENTS.md $agents times and CLAUDE.md $claude times"; fi

    say "copies without ids or account usage, in $OUT/scrubbed"
    local name
    for name in claude openai; do
        [ -s "$OUT/$name.jsonl" ] || continue
        if uv run --no-project python -I "$ROOT/factory/scrub_pi_samples.py" "$OUT/$name.jsonl" "$OUT/scrubbed/$name.jsonl" >/dev/null; then
            line ok "$name.jsonl"
        else
            bad check "$name.jsonl was not copied: the scrubber found something it can't remove"
        fi
    done
}

[ $# -eq 1 ] || { sed -n '2,14p' "$0"; exit 2; }
case "$1" in
    install) cmd_install ;;
    check) cmd_check ;;
    answers) cmd_answers ;;
    *) echo "unknown command: $1 (install check answers)" >&2; exit 2 ;;
esac
exit "$left"
