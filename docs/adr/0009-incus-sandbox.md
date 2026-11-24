# 9. Agents work in an Incus sandbox

Date: 2026-11-24 · Status: accepted

## Context

Pi runs tools without asking (ADR 8). On the VPS it runs as `dev`, which holds Daniel's logins, can use `sudo`, and is in the `docker` group, which equals root. A wrong command, or one an agent was tricked into by text it read, could leak those logins or change the firewall, SSH or Tailscale. Until now the only protection was ADR 8's rule: Pi runs with `--no-tools` or while Daniel watches. The factory's direction (ADR 5) needs agents that work while he is away, so the limit has to live outside the model.

Options considered: no isolation; a separate Linux user with rootless Docker; an Incus system container. A separate user protects the logins and the server but gives no snapshots, and per-user network rules are hard. A full VM per project, as in the course author's lab, needs hardware virtualization the VPS doesn't offer.

## Decision

- **Agents work in an Incus system container per project**, `oncall` for this one, built by [`scripts/sandbox.sh`](../../scripts/sandbox.sh): Ubuntu 24.04, Docker allowed inside it (`security.nesting`), memory limited to 10 GiB.
- **Inside, agents run as `agent`**, with no `sudo`. `agent` may use the sandbox's own Docker, which is root of the sandbox only, so shopfront and the lab can run there.
- **The sandbox has its own logins** (Claude, ChatGPT in Pi, GitHub), made inside it. `dev`'s logins are never copied in, so revoking the sandbox's leaves Daniel's untouched.
- **The inside is built by the same sections as the VPS** (`scripts/vps-setup.sh`: `user`, `docker`, `tools`, `repos` for `agent`), then saved as the snapshot `clean`. `restore` puts the whole sandbox back, after confirmation.
- **Nothing reaches the sandbox from outside.** Its outgoing traffic is not limited yet; that comes with F2.

## Consequences

- Daniel enters with `sudo bash scripts/sandbox.sh shell`, or from a Herdr pane with `incus exec oncall -- su -l agent`. `dev` joins `incus-admin` for that, which, like `docker`, equals root on the VPS: `dev` is the person, not an agent.
- On the VPS, the firewall blocks traffic passing through it (`deny (routed)`) and Docker on the host drops it too. `install` adds `ufw` rules for `incusbr0` and a service that lets the sandbox's traffic through Docker's `DOCKER-USER` chain. Neither could be tested in a container; `provision` stops with an explanation if the sandbox has no internet.
- Once shopfront and the lab run in the sandbox, Docker on the VPS itself can be switched off, which also ends `dev`'s root-equivalent `docker` group.
- The container shares the VPS's kernel, so a kernel exploit could escape it. A VM would be stronger; this is the practical balance on one VPS.
- `incus admin init --minimal` uses a plain directory for storage, which doesn't enforce disk quotas. The memory limit is enforced.
