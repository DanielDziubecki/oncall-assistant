#!/usr/bin/env bash
# The project sandbox (F1): an Incus system container where agents work, so a wrong command can
# damage the container but not the VPS, your logins or other projects. See ADR 9.
#
# Run as root on the VPS, from ~/src/oncall-assistant:
#   sudo bash scripts/sandbox.sh <command>
# Commands, in order for a new sandbox: install, create, provision. Then: shell, snapshot,
# restore, status. Each checks before it changes anything, so running it again is safe.
#
# Inside the sandbox, agents run as the user "agent". Its logins (Claude, ChatGPT in Pi,
# GitHub) are its own; never copy dev's into it.
set -euo pipefail

NAME="${SANDBOX:-oncall}"
MEMORY="${SANDBOX_MEMORY:-10GiB}"
IMAGE="images:ubuntu/24.04"
BRIDGE="incusbr0"
AGENT="agent"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

say() { printf '\n== %s\n' "$*"; }
fail() { echo "$*" >&2; exit 1; }
need_root() { [ "$(id -u)" -eq 0 ] || fail "run this as root (sudo)"; }
exists() { incus info "$NAME" >/dev/null 2>&1; }
inside() { incus exec "$NAME" -- bash -lc "$*"; }

# Incus, its storage and network, and the firewall rules its network needs on this VPS.
cmd_install() {
    if ! command -v incus >/dev/null; then
        say "installing Incus"
        DEBIAN_FRONTEND=noninteractive apt-get install -y -q incus
    fi
    if [ -z "$(incus storage list --format csv 2>/dev/null)" ]; then
        say "first-time Incus setup: a storage pool and the $BRIDGE network"
        incus admin init --minimal
    fi
    local admin="${SUDO_USER:-}"
    if [ -n "$admin" ] && [ "$admin" != root ]; then
        usermod -aG incus-admin "$admin"
        say "$admin can manage Incus after logging in again (incus-admin equals root, like docker)"
    fi
    if command -v ufw >/dev/null && ufw status | grep -q "Status: active"; then
        say "firewall: let the sandbox get an address and DNS from the VPS, and reach the internet"
        ufw allow in on "$BRIDGE" comment 'Incus sandbox: DHCP and DNS'
        ufw route allow in on "$BRIDGE" comment 'Incus sandbox: outgoing'
        ufw route allow out on "$BRIDGE" comment 'Incus sandbox: replies'
    fi
    if systemctl is-active --quiet docker 2>/dev/null; then
        say "Docker on the VPS drops forwarded traffic; letting the sandbox's through"
        cat > /etc/systemd/system/incus-docker-forward.service <<EOF
[Unit]
Description=Let the Incus sandbox's traffic through Docker's forwarding rules
After=docker.service
Requires=docker.service
PartOf=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/bin/sh -c 'iptables -C DOCKER-USER -i $BRIDGE -j ACCEPT 2>/dev/null || iptables -I DOCKER-USER -i $BRIDGE -j ACCEPT; iptables -C DOCKER-USER -o $BRIDGE -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT 2>/dev/null || iptables -I DOCKER-USER -o $BRIDGE -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT'

[Install]
WantedBy=docker.service
EOF
        systemctl daemon-reload
        systemctl enable --now incus-docker-forward.service
    fi
}

# The container itself: Ubuntu 24.04, Docker allowed inside it (nesting), a memory limit.
cmd_create() {
    command -v incus >/dev/null || fail "run install first"
    if exists; then
        say "sandbox $NAME exists"
    else
        say "creating sandbox $NAME ($IMAGE, memory limit $MEMORY)"
        incus launch "$IMAGE" "$NAME" -c security.nesting=true -c limits.memory="$MEMORY"
    fi
    incus config set "$NAME" limits.memory="$MEMORY"
}

# Waits until the sandbox can reach GitHub over HTTPS, or explains why it can't.
wait_for_internet() {
    for _ in $(seq 1 30); do
        inside 'curl -fsSI --max-time 5 https://github.com >/dev/null 2>&1' && return 0
        sleep 2
    done
    fail "the sandbox can't reach https://github.com. Check: incus list (does $NAME have an address?),
then the firewall rules from 'install' (sudo ufw status verbose) and Docker's (sudo iptables -L DOCKER-USER)."
}

# Everything inside, built by the same sections as the VPS (scripts/vps-setup.sh) for the user
# "agent", then a snapshot called "clean" to return to.
cmd_provision() {
    exists || fail "run create first"
    say "waiting for the sandbox's network"
    wait_for_internet
    say "base packages inside"
    inside 'export DEBIAN_FRONTEND=noninteractive; apt-get update -q && apt-get install -y -q git make curl ca-certificates tmux gh sudo'
    incus file push "$HERE/vps-setup.sh" "$NAME/root/vps-setup.sh"
    say "user, Docker, tools and repos inside, for $AGENT"
    inside "DEV_USER=$AGENT bash /root/vps-setup.sh user docker tools repos"
    # vps-setup adds its user to sudo; inside the sandbox the agent gets no sudo at all
    inside "gpasswd -d $AGENT sudo >/dev/null 2>&1 || true"
    inside "systemctl restart docker"
    if ! incus snapshot list "$NAME" --format csv 2>/dev/null | grep -q '^clean,'; then
        say "snapshot: clean"
        incus snapshot create "$NAME" clean
    fi
    say "done. Next, as $AGENT inside: the logins (bash scripts/logins.sh) and Pi (bash scripts/pi-setup.sh install)"
    echo "  sudo bash scripts/sandbox.sh shell"
}

# A shell as the agent inside the sandbox. Herdr can run the same command in a pane.
cmd_shell() {
    exists || fail "no sandbox $NAME; run install, create and provision"
    exec incus exec "$NAME" -- su -l "$AGENT"
}

cmd_snapshot() {
    [ $# -eq 1 ] || fail "usage: snapshot <name>"
    incus snapshot create "$NAME" "$1"
    incus snapshot list "$NAME"
}

# Puts the whole sandbox back to a snapshot. Everything since then is lost.
cmd_restore() {
    [ $# -eq 1 ] || fail "usage: restore <name>"
    [ "${CONFIRM_RESTORE:-}" = "yes" ] || fail "restoring loses everything in $NAME since snapshot $1; run again with CONFIRM_RESTORE=yes"
    incus snapshot restore "$NAME" "$1"
    echo "restored $NAME to $1"
}

cmd_status() {
    exists || fail "no sandbox $NAME"
    incus list "$NAME" -c ns4
    echo "memory limit: $(incus config get "$NAME" limits.memory)"
    echo "snapshots:"; incus snapshot list "$NAME" --format csv | cut -d, -f1 | sed 's/^/  /'
    inside 'curl -fsSI --max-time 5 https://github.com >/dev/null 2>&1' \
        && echo "internet: ok" || echo "internet: NOT reachable (see install)"
    inside "id $AGENT >/dev/null 2>&1" && echo "agent user: ok" || echo "agent user: missing (run provision)"
}

need_root
[ $# -ge 1 ] || { sed -n '2,12p' "$0"; exit 2; }
command="$1"; shift
case "$command" in
    install|create|provision|shell|snapshot|restore|status) "cmd_$command" "$@" ;;
    *) fail "unknown command: $command (install create provision shell snapshot restore status)" ;;
esac
