#!/usr/bin/env bash
# The project sandbox (F1): an Incus system container where agents work, so a wrong command can
# damage the container but not the VPS, your logins or other projects. See ADR 9.
#
# Run as root on the VPS, from ~/src/oncall-assistant:
#   sudo bash scripts/sandbox.sh <command>
# Commands, in order for a new sandbox: install, create, provision, lockdown. Then: shell,
# snapshot, restore, status, denied, and unlock for maintenance. Each checks before it changes
# anything, so running it again is safe.
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
ALLOWLIST="$HERE/../factory/sandbox/allowlist.txt"
ACL="sandbox-egress"
PROXY_PORT=8888
PROXY_CONF=/etc/tinyproxy/tinyproxy.conf
PROXY_FILTER=/etc/tinyproxy/sandbox-allowlist
PROXY_LOG=/var/log/tinyproxy/tinyproxy.log

say() { printf '\n== %s\n' "$*"; }
fail() { echo "$*" >&2; exit 1; }
need_root() { [ "$(id -u)" -eq 0 ] || fail "run this as root (sudo)"; }
exists() { incus info "$NAME" >/dev/null 2>&1; }
# /etc/environment holds the proxy settings after lockdown; incus exec doesn't read it by itself.
inside() { incus exec "$NAME" -- bash -lc "set -a; [ -f /etc/environment ] && . /etc/environment; set +a; $*"; }
bridge_ip() { incus network get "$BRIDGE" ipv4.address | cut -d/ -f1; }

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
    [ "$(incus network get "$BRIDGE" security.acls)" = "$ACL" ] \
        && echo "network: locked down (allowlist: factory/sandbox/allowlist.txt)" \
        || echo "network: OPEN (run lockdown)"
}

# F2 (ADR 10): the sandbox may connect only to the hosts in factory/sandbox/allowlist.txt.
# A proxy on the VPS (tinyproxy) lets through only those names; an Incus ACL on the sandbox
# network drops everything that doesn't go through the proxy. Ends with a self-test.
cmd_lockdown() {
    exists || fail "no sandbox $NAME; run install, create and provision first"
    [ -s "$ALLOWLIST" ] || fail "missing $ALLOWLIST"
    local ip subnet proxy
    ip="$(bridge_ip)"
    subnet="$(incus network get "$BRIDGE" ipv4.address)"
    proxy="http://$ip:$PROXY_PORT"

    if ! command -v tinyproxy >/dev/null; then
        say "installing tinyproxy"
        DEBIAN_FRONTEND=noninteractive apt-get install -y -q tinyproxy
    fi
    say "proxy on $ip:$PROXY_PORT, allowing $(grep -c -v -E '^\s*(#|$)' "$ALLOWLIST") hosts"
    # one exact host per line becomes ^host$, with its dots escaped
    grep -v -E '^\s*(#|$)' "$ALLOWLIST" | sed -E 's/[[:space:]]+//g; s/\./\\./g; s/^/^/; s/$/$/' > "$PROXY_FILTER"
    [ -f "$PROXY_CONF.orig" ] || cp "$PROXY_CONF" "$PROXY_CONF.orig"
    {
        echo "# Written by scripts/sandbox.sh lockdown; the package's original is $PROXY_CONF.orig"
        echo "User tinyproxy"
        echo "Group tinyproxy"
        echo "Port $PROXY_PORT"
        echo "Listen $ip"
        echo "Timeout 600"
        echo "MaxClients 100"
        echo "LogFile \"$PROXY_LOG\""
        echo "LogLevel Connect"
        echo "PidFile \"/run/tinyproxy/tinyproxy.pid\""
        echo "Allow $subnet"
        echo "Filter \"$PROXY_FILTER\""
        echo "FilterType ere"
        echo "FilterDefaultDeny Yes"
        echo "ConnectPort 443"
        # only for a VPS that itself must go through another proxy
        if [ -n "${SANDBOX_UPSTREAM:-}" ]; then echo "Upstream http $SANDBOX_UPSTREAM"; fi
    } > "$PROXY_CONF"
    systemctl enable tinyproxy >/dev/null 2>&1 || true
    systemctl restart tinyproxy

    say "Incus ACL $ACL: from the sandbox network, only DNS and the proxy"
    # without a terminal, `acl create` waits to read a definition from stdin; give it none
    incus network acl show "$ACL" >/dev/null 2>&1 || incus network acl create "$ACL" </dev/null
    printf '%s\n' \
        "description: Sandbox egress, F2 (ADR 10). Written by scripts/sandbox.sh lockdown." \
        "egress:" \
        "- {action: allow, state: enabled, protocol: tcp, destination: $ip/32, destination_port: \"$PROXY_PORT\", description: proxy}" \
        "- {action: allow, state: enabled, protocol: udp, destination: $ip/32, destination_port: \"53\", description: DNS}" \
        "- {action: allow, state: enabled, protocol: tcp, destination: $ip/32, destination_port: \"53\", description: DNS}" \
        "ingress: []" | incus network acl edit "$ACL"
    incus network set "$BRIDGE" security.acls="$ACL" \
        security.acls.default.egress.action=reject security.acls.default.ingress.action=reject

    say "proxy settings inside the sandbox"
    incus exec "$NAME" -- env PROXY="$proxy" AGENT="$AGENT" bash -s <<'INSIDE'
set -euo pipefail
sed -i -E '/^(https?_proxy|HTTPS?_PROXY|no_proxy|NO_PROXY)=/d' /etc/environment
printf '%s\n' "https_proxy=$PROXY" "HTTPS_PROXY=$PROXY" "http_proxy=$PROXY" "HTTP_PROXY=$PROXY" \
    "no_proxy=localhost,127.0.0.1" "NO_PROXY=localhost,127.0.0.1" >> /etc/environment
printf 'Acquire::http::Proxy "%s";\nAcquire::https::Proxy "%s";\n' "$PROXY" "$PROXY" > /etc/apt/apt.conf.d/95sandbox-proxy
if command -v docker >/dev/null; then
    mkdir -p /etc/systemd/system/docker.service.d
    printf '[Service]\nEnvironment=HTTPS_PROXY=%s HTTP_PROXY=%s NO_PROXY=localhost,127.0.0.1\n' "$PROXY" "$PROXY" \
        > /etc/systemd/system/docker.service.d/sandbox-proxy.conf
    systemctl daemon-reload && systemctl restart docker
fi
# containers and image builds started by the agent's Docker get the proxy too
if id "$AGENT" >/dev/null 2>&1; then
    install -d -o "$AGENT" -g "$AGENT" "/home/$AGENT/.docker"
    printf '{"proxies": {"default": {"httpProxy": "%s", "httpsProxy": "%s", "noProxy": "localhost,127.0.0.1"}}}\n' \
        "$PROXY" "$PROXY" > "/home/$AGENT/.docker/config.json"
    chown "$AGENT:$AGENT" "/home/$AGENT/.docker/config.json"
fi
INSIDE

    say "self-test"
    selftest
}

# Fails unless direct connections are blocked, an allowed host works through the proxy, and a
# host that isn't allowed is refused by it.
selftest() {
    local ok=1
    if inside 'curl -s -o /dev/null --noproxy "*" --max-time 8 https://example.com'; then
        echo "  FAIL  a direct connection got out: the ACL isn't working"; ok=0
    else
        echo "  ok    direct connections are blocked"
    fi
    if inside 'curl -s -o /dev/null --max-time 15 https://pypi.org'; then
        echo "  ok    an allowed host works through the proxy (pypi.org)"
    else
        echo "  FAIL  pypi.org is unreachable through the proxy"; ok=0
    fi
    if inside 'curl -s -o /dev/null --max-time 15 https://example.com'; then
        echo "  FAIL  a host outside the allowlist got through (example.com)"; ok=0
    else
        echo "  ok    hosts outside the allowlist are refused (example.com)"
    fi
    if inside 'command -v docker >/dev/null'; then
        local pulled
        pulled="$(inside 'docker pull -q hello-world 2>&1' || true)"
        if grep -q 'hello-world' <<<"$pulled" && ! grep -qi 'error' <<<"$pulled"; then
            echo "  ok    Docker pulls images through the proxy"
        elif grep -q '429' <<<"$pulled"; then
            # Docker Hub answered, so the path works; it limits anonymous pulls per IP address
            echo "  ok    Docker reaches its registry through the proxy (Docker Hub is rate-limiting this IP right now)"
        else
            echo "  FAIL  Docker can't pull images through the proxy: $(tail -n 1 <<<"$pulled")"; ok=0
        fi
    fi
    [ "$ok" -eq 1 ] || fail "lockdown self-test failed"
}

# Hosts the proxy refused, most frequent first: each is a candidate for the allowlist, or a
# sign of something an agent shouldn't have tried.
cmd_denied() {
    [ -f "$PROXY_LOG" ] || fail "no proxy log yet; run lockdown"
    grep -o 'refused on filtered domain "[^"]*"' "$PROXY_LOG" | cut -d'"' -f2 | sort | uniq -c | sort -rn | head -n "${1:-20}"
}

# Maintenance only (re-provisioning needs installer sites): removes the ACL, so the sandbox can
# connect anywhere until the next lockdown.
cmd_unlock() {
    [ "${CONFIRM_UNLOCK:-}" = "yes" ] || fail "unlock lets the sandbox connect anywhere until you run lockdown again; run with CONFIRM_UNLOCK=yes"
    incus network unset "$BRIDGE" security.acls
    incus network unset "$BRIDGE" security.acls.default.egress.action
    incus network unset "$BRIDGE" security.acls.default.ingress.action
    echo "unlocked: run lockdown when you're done"
}

need_root
[ $# -ge 1 ] || { sed -n '2,13p' "$0"; exit 2; }
command="$1"; shift
case "$command" in
    install|create|provision|lockdown|shell|snapshot|restore|status|denied|unlock) "cmd_$command" "$@" ;;
    *) fail "unknown command: $command (install create provision lockdown shell snapshot restore status denied unlock)" ;;
esac
