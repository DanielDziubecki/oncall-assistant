#!/usr/bin/env bash
# The logins the factory needs, one after another, for you to complete as dev on the VPS:
#   bash scripts/logins.sh
# A login that already works is skipped, so running it again is safe. Each one is the tool's own
# login command; this script never reads or prints a credential. For GitHub, use an account
# without admin rights on the repos, and approve it in a private browser window.
set -uo pipefail
export PATH="$HOME/.local/bin:$PATH"

failed=0

# login <name> <command that succeeds when logged in> <login command...>
login() {
    local name=$1 check=$2
    shift 2
    if bash -c "$check" >/dev/null 2>&1; then
        printf '  done     %s\n' "$name"
        return
    fi
    printf '\n== %s: %s\n' "$name" "$*"
    if "$@" && bash -c "$check" >/dev/null 2>&1; then
        printf '  done     %s\n' "$name"
    else
        printf '  failed   %s: run this script again\n' "$name"
        failed=1
    fi
}

login "Claude Code" "claude auth status --text" claude auth login
login "Codex" "codex login status" codex login --device-auth
login "GitHub" "gh auth status" gh auth login --hostname github.com --git-protocol https --web
login "ChatGPT in Pi" "pi auth check --provider openai-codex" pi auth login openai-codex --no-browser

if gh auth status >/dev/null 2>&1; then
    gh auth setup-git
    printf '  note     GitHub account: %s (must not be an admin of the repos)\n' "$(gh api user --jq .login)"
fi
passwd -S "$USER" 2>/dev/null | grep -q " P " \
    || printf '  todo     a password for %s: as root, passwd %s (sudo needs it)\n' "$USER" "$USER"

exit "$failed"
