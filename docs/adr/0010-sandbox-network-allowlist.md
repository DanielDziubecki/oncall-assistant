# 10. The sandbox connects only to an allowlist

Date: 2026-11-24 · Status: accepted

## Context

The sandbox (ADR 9) keeps an agent's mistakes away from the VPS, but not away from the internet. Inside it, an agent holds its own logins (GitHub as `ddagent`, Claude, ChatGPT), reads untrusted text (issues, logs, pages, test output) and could connect anywhere. That is the "lethal trifecta" the product plan designs against: private data, untrusted content and a way out. F2 removes most of the way out, with a limit the agent can't change from inside the sandbox.

Incus ACLs match IP addresses, not names, and the hosts agents need (GitHub, the model APIs, package registries) change addresses. Incus 6.0, Ubuntu 24.04's version, accepts ACLs on a network but not on one instance's NIC.

## Decision

- **A filtering proxy on the VPS** (tinyproxy, an Ubuntu package) listens on the sandbox network's gateway and lets HTTPS through only to the exact host names in [`factory/sandbox/allowlist.txt`](../../factory/sandbox/allowlist.txt), refusing everything else (`FilterDefaultDeny`). Tunnels are allowed to port 443 only.
- **An Incus ACL on the sandbox network** (`sandbox-egress`) allows only DNS and the proxy's port; every other connection from the network is rejected. A tool that ignores the proxy settings fails instead of going around them. The ACL applies to every sandbox on the network, so each new project gets the same policy.
- **Inside the sandbox**, `/etc/environment`, apt, the Docker daemon and the agent's Docker client config point at the proxy, so image pulls and image builds use it too.
- **`scripts/sandbox.sh lockdown`** applies all of it and ends with a self-test that must see direct connections blocked, an allowed host reachable, a host outside the list refused, and Docker reaching its registry. **`denied`** lists refused hosts, most frequent first. **`unlock`** removes the ACL for maintenance, after confirmation.
- **The allowlist changes only by PR, with a reason per host.** A host is added after `denied` shows it refused for real work.

## Consequences

- Testing already found one missing host this way: Docker Hub's image downloads now come from `production.cloudfront.docker.com`.
- Installer sites (NodeSource, astral.sh, Claude's downloads, Herdr) aren't on the list: re-provisioning means `unlock`, `provision`, `lockdown`. Tools that update themselves from the internet stop doing so inside the sandbox.
- GitHub has to stay reachable, and the `ddagent` login can push branches and create gists, so data could still leave through GitHub. The action monitor (F2's second part) and Daniel's review of PRs reduce that; no network rule removes it.
- Plain HTTP passes through the proxy too, filtered by the same host names (Ubuntu's mirrors use it).
- Docker Hub limits anonymous pulls per IP address. The self-test counts a rate-limit answer as proof the path works.
