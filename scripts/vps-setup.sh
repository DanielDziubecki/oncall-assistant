#!/usr/bin/env bash
# Sets up the factory VPS (Ubuntu 24.04), the scripted version of docs/factory/vps-setup.md.
#
# Run as root, one section at a time, from your computer:
#   ssh vps 'bash -s -- <section>' < scripts/vps-setup.sh
# Sections, in order: base user docker tools repos check harden
# ssh-access is only for servers whose AllowUsers leaves dev out. Run it yourself, before harden.
# tailnet-only (F1) closes SSH to the internet. Run it yourself, after harden.
#
# Every section checks before it changes anything, so running it again is safe.
# Logins (Claude, Codex, Pi, GitHub) are never done here: `check` lists what is left for you.
set -euo pipefail

DEV_USER="${DEV_USER:-dev}"
REPOS=(oncall-assistant shopfront)
REPO_OWNER="DanielDziubecki"

say() { printf '\n== %s\n' "$*"; }
need_root() { [ "$(id -u)" -eq 0 ] || { echo "run this as root" >&2; exit 1; }; }
as_dev() { sudo -u "$DEV_USER" -H bash -lc "cd ~ || exit 1; $*"; }
has() { command -v "$1" >/dev/null 2>&1; }

# Tailscale gives every device an address in these ranges (IPv4 100.64.0.0/10, IPv6 fd7a:115c:a1e0::/48).
TAILNET_FROM='(100\.(6[4-9]|[7-9][0-9]|1[01][0-9]|12[0-7])\.[0-9]+\.[0-9]+|fd7a:115c:a1e0:[0-9a-fA-F:]*)'

# True if the dev user logged in with a key after SSH's settings last changed, from an address
# matching $1 (default: any). A real login is the only proof that covers allow and deny lists,
# groups and keys. _UID=0 stops forged entries.
dev_login_proven() {
    local changed from="${1:-[^ ]+}"
    changed="$(stat -c %Y /etc/ssh/sshd_config /etc/ssh/sshd_config.d /etc/ssh/sshd_config.d/* | sort -n | tail -n 1)"
    # not grep -q: it stops reading early, which pipefail would report as a failure
    journalctl -q -o cat --since "@$changed" _UID=0 _COMM=sshd \
        | grep -E "^Accepted publickey for $DEV_USER from $from " >/dev/null
}

# Guide step 3: base packages, a firewall that only lets SSH in, automatic security updates.
section_base() {
    say "base packages"
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -q
    apt-get install -y -q git make curl ca-certificates tmux gh ufw unattended-upgrades
    say "firewall: allow SSH only"
    ufw allow OpenSSH
    ufw --force enable
}

# Guide step 1: your everyday user. It logs in with the same key as root and can use sudo.
section_user() {
    if id "$DEV_USER" >/dev/null 2>&1; then
        say "user $DEV_USER exists"
    else
        say "creating user $DEV_USER"
        adduser --disabled-password --gecos "" "$DEV_USER"
    fi
    usermod -aG sudo "$DEV_USER"
    install -d -m 700 -o "$DEV_USER" -g "$DEV_USER" "/home/$DEV_USER/.ssh"
    if [ -s /root/.ssh/authorized_keys ] && [ ! -s "/home/$DEV_USER/.ssh/authorized_keys" ]; then
        install -m 600 -o "$DEV_USER" -g "$DEV_USER" /root/.ssh/authorized_keys "/home/$DEV_USER/.ssh/authorized_keys"
        say "copied root's SSH key to $DEV_USER"
    fi
}

# Guide step 4: Docker. Membership of the docker group equals root on this machine.
section_docker() {
    if has docker; then
        say "docker already installed: $(docker --version)"
    else
        say "installing Docker"
        curl -fsSL https://get.docker.com | sh
    fi
    usermod -aG docker "$DEV_USER"
}

# Guide steps 2, 5 and 6: everything installed for the dev user, without sudo.
section_tools() {
    if ! has node || [ "$(node -p 'process.versions.node.split(".")[0]')" -lt 22 ]; then
        say "installing Node 22"
        curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
        apt-get install -y -q nodejs
    fi
    say "user tools for $DEV_USER"
    as_dev '
        set -euo pipefail
        grep -q "HOME/.local/bin" ~/.bashrc || echo "export PATH=\"\$HOME/.local/bin:\$PATH\"" >> ~/.bashrc
        export PATH="$HOME/.local/bin:$PATH"
        command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh
        npm config set prefix ~/.local
        command -v codex >/dev/null || npm install -g @openai/codex
        command -v pi >/dev/null || npm install -g --ignore-scripts @earendil-works/pi-coding-agent
        command -v claude >/dev/null || curl -fsSL https://claude.ai/install.sh | bash
        command -v hc >/dev/null || curl -fsSL https://releases.herdr.dev/core/install.sh | sh
    '
}

# Guide step 7: both repos and the product's dependencies.
section_repos() {
    say "repos for $DEV_USER"
    for repo in "${REPOS[@]}"; do
        as_dev "
            set -euo pipefail
            mkdir -p ~/src
            [ -d ~/src/$repo/.git ] || git clone -q https://github.com/$REPO_OWNER/$repo.git ~/src/$repo
        "
    done
    as_dev 'export PATH="$HOME/.local/bin:$PATH"; cd ~/src/oncall-assistant && make install'
}

# Shows what is installed and what you still have to do yourself.
section_check() {
    say "installed for $DEV_USER"
    as_dev '
        export PATH="$HOME/.local/bin:$PATH"
        for tool in git make tmux gh docker uv node codex pi claude hc; do
            if command -v "$tool" >/dev/null; then printf "  ok       %s\n" "$tool"; else printf "  missing  %s\n" "$tool"; fi
        done
        docker info >/dev/null 2>&1 && echo "  ok       docker daemon reachable" || echo "  check    docker daemon (log out and back in after the docker section)"
    '
    say "your steps as $DEV_USER: 'done' is finished, 'todo' is left for you"
    as_dev 'export PATH="$HOME/.local/bin:$PATH"; claude auth status --text >/dev/null 2>&1' \
        && echo "  done     Claude login" || echo "  todo     claude            (log in with your subscription)"
    as_dev 'export PATH="$HOME/.local/bin:$PATH"; codex login status >/dev/null 2>&1' \
        && echo "  done     Codex login" || echo "  todo     codex login --device-auth"
    as_dev 'gh auth status >/dev/null 2>&1' \
        && echo "  done     GitHub login" || echo "  todo     gh auth login, then gh auth setup-git"
    as_dev 'export PATH="$HOME/.local/bin:$PATH"; pi auth check --provider openai-codex >/dev/null 2>&1' \
        && echo "  done     ChatGPT in Pi" || echo "  todo     pi auth login openai-codex --no-browser"
    echo "           (bash scripts/logins.sh, as $DEV_USER in ~/src/oncall-assistant, runs every login above)"
    passwd -S "$DEV_USER" | grep -q " P " \
        && echo "  done     $DEV_USER has a password" || echo "  todo     as root: passwd $DEV_USER   (needed for sudo, and before harden)"
    echo "  then     as $DEV_USER: bash scripts/pi-setup.sh install, then check (docs/factory/vps-setup.md, step 8)"
}

# Run by you, only where AllowUsers leaves the dev user out: lets it in from the tailnet.
section_ssh_access() {
    local settings conf=/etc/ssh/sshd_config.d/01-dev-access.conf
    settings="$(sshd -T)"
    # adding AllowUsers where there is none would lock out everyone else, root included
    if ! grep -q '^allowusers ' <<<"$settings"; then
        say "no AllowUsers list, nothing to change"
        return
    fi
    if grep -qE "^allowusers $DEV_USER(@|\$)" <<<"$settings"; then
        say "$DEV_USER is already in AllowUsers"
        return
    fi
    say "allowing $DEV_USER to log in from the tailnet"
    echo "AllowUsers $DEV_USER@100.64.0.0/10 $DEV_USER@fd7a:115c:a1e0::/48" > "$conf"
    sshd -t || { rm -f "$conf"; echo "undone: sshd rejected the change" >&2; exit 1; }
    systemctl reload ssh
    echo "done: now log in as $DEV_USER from a second terminal"
}

# Guide step 1, last on purpose: turns off root and password login. It refuses unless the dev
# user has really logged in with a key, can use sudo, and you confirm that you tested both.
section_harden() {
    [ -s "/home/$DEV_USER/.ssh/authorized_keys" ] || { echo "refusing: $DEV_USER has no SSH key" >&2; exit 1; }
    passwd -S "$DEV_USER" | grep -q " P " || { echo "refusing: $DEV_USER has no password, so sudo would not work; run: passwd $DEV_USER" >&2; exit 1; }
    id -nG "$DEV_USER" | grep -qw sudo || { echo "refusing: $DEV_USER is not in the sudo group" >&2; exit 1; }
    dev_login_proven || {
        echo "refusing: no key login by $DEV_USER since SSH's settings last changed. Log in as $DEV_USER from a" >&2
        echo "second terminal; if it is refused, AllowUsers may be the cause (see the ssh-access section)" >&2
        exit 1
    }
    [ "${CONFIRM_DEV_LOGIN:-}" = "yes" ] || {
        echo "refusing: first log in as $DEV_USER from a second terminal (ssh $DEV_USER@<vps>) and run 'sudo true'," >&2
        echo "then run this section again with CONFIRM_DEV_LOGIN=yes" >&2
        exit 1
    }
    say "turning off root and password login"
    local conf=/etc/ssh/sshd_config.d/00-hardening.conf
    printf 'PasswordAuthentication no\nPermitRootLogin no\n' > "$conf"
    sshd -t || { rm -f "$conf"; echo "undone: sshd rejected the change" >&2; exit 1; }
    systemctl restart ssh
    echo "done: log in as $DEV_USER from now on"
}

# F1, run by you after harden: SSH only from your Tailscale devices. It refuses unless Tailscale is
# up, the SSH log shows a key login by the dev user from a tailnet address, and you confirm you can
# open your provider's web console. Opening the tailnet rule first keeps your current session.
section_tailnet_only() {
    has tailscale || { echo "refusing: Tailscale is not installed" >&2; exit 1; }
    tailscale status >/dev/null 2>&1 || { echo "refusing: Tailscale is not connected; run: tailscale up" >&2; exit 1; }
    ip -o link show tailscale0 >/dev/null 2>&1 || { echo "refusing: there is no tailscale0 network interface" >&2; exit 1; }
    dev_login_proven "$TAILNET_FROM" || {
        echo "refusing: no key login by $DEV_USER from a tailnet address since SSH's settings last changed." >&2
        echo "Set HostName in your SSH config to the VPS's Tailscale name or 100.x address, log in as $DEV_USER, run again." >&2
        exit 1
    }
    [ "${CONFIRM_CONSOLE:-}" = "yes" ] || {
        echo "refusing: check that you can open your provider's web console for this server (your way in if" >&2
        echo "Tailscale fails), then run this section again with CONFIRM_CONSOLE=yes" >&2
        exit 1
    }
    say "SSH from the tailnet only"
    ufw allow in on tailscale0 to any port 22 proto tcp comment 'SSH from the tailnet only'
    ufw delete allow OpenSSH >/dev/null 2>&1 || true
    ufw status verbose
    echo "done: SSH answers only on Tailscale. From outside the tailnet, ssh to the public IP now times out."
}

need_root
[ $# -ge 1 ] || { sed -n '2,9p' "$0" 2>/dev/null || echo "usage: <section>"; exit 2; }
for section in "$@"; do
    case "$section" in
        base|user|docker|tools|repos|check|harden) "section_$section" ;;
        ssh-access) section_ssh_access ;;
        tailnet-only) section_tailnet_only ;;
        *) echo "unknown section: $section (base user docker tools repos check ssh-access harden tailnet-only)" >&2; exit 2 ;;
    esac
done
