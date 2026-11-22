# Set up the VPS from your computer

Claude Code on your Windows computer runs [`scripts/vps-setup.sh`](../../scripts/vps-setup.sh)
on the VPS over SSH, one section at a time, and explains each one. You approve every command.
The script is the repeatable version of [`vps-setup.md`](vps-setup.md), which explains why
each step exists.

Tested in an Ubuntu 24.04 container: the `user`, `tools`, `repos` and `check` sections, run
twice, and the safety refusals of `harden`. Not testable in a container, so first tested on
your VPS: `base` (the firewall), `docker` (the daemon) and the SSH restart in `harden`.

## 1. You: on your Windows computer

1. **Git for Windows**, which Claude Code uses for its shell: <https://git-scm.com/download/win>.
2. **Claude Code**, in PowerShell:

   ```powershell
   irm https://claude.ai/install.ps1 | iex
   ```

   Run `claude` once and log in with your subscription.
3. **An SSH key**, in PowerShell (press Enter to accept the default path; a passphrase is recommended):

   ```powershell
   ssh-keygen -t ed25519
   ```

4. **This repo**, cloned anywhere, for example `git clone https://github.com/DanielDziubecki/oncall-assistant.git`.

## 2. You: give the VPS your key

netcup sends the root password for a new server by email. Log in with it once to add your
key. Replace `<vps-ip>` with your server's address:

```powershell
type $env:USERPROFILE\.ssh\id_ed25519.pub | ssh root@<vps-ip> "mkdir -p ~/.ssh && chmod 700 ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
```

Then add this to `%USERPROFILE%\.ssh\config` (create the file if it doesn't exist):

```
Host vps
    HostName <vps-ip>
    User root
```

`ssh vps` should now log you in without a password.

## 3. Claude Code: run the setup

In the repo folder, start `claude` and give it this prompt:

```
Set up my VPS with scripts/vps-setup.sh. Read it and docs/factory/vps-setup.md first.
Run one section at a time as root with: ssh vps 'bash -s -- <section>' < scripts/vps-setup.sh
in this order: base, user, docker, tools, repos, check.
Before each section, tell me in two sentences what it changes and why. After it, tell me
what happened. If a section fails, explain the cause and propose a fix to the script; don't
work around it on the server by hand.
Never run the harden section yourself, never handle my passwords or logins, and stop after
check to give me the list of what is left for me.
```

## 4. You: logins and the password

`check` ends with a list of what is left. In your own terminal:

1. `ssh vps`, then `passwd dev` to give `dev` a password (sudo needs it).
2. `ssh dev@<vps-ip>`, then log in to each tool: `claude`, `codex login --device-auth`, `gh auth login` and `gh auth setup-git`.
3. While still logged in as `dev`, run `sudo true` to prove sudo works.

If SSH refuses `dev`, the server may have an `AllowUsers` list. You can still do steps 2 and 3
from a root session with `su - dev`. To let `dev` in from your Tailscale network, run this
yourself in Git Bash, then log in through the server's Tailscale name:

```bash
ssh vps 'bash -s -- ssh-access' < scripts/vps-setup.sh
```

## 5. You: close root login

Only after step 4 worked, including a real SSH login as `dev` (`su - dev` doesn't count, and
`harden` checks). This also ends any root fallback login, so make sure you can reach your
provider's console. From your computer, in Git Bash (PowerShell rejects the `<`):

```bash
ssh vps 'CONFIRM_DEV_LOGIN=yes bash -s -- harden' < scripts/vps-setup.sh
```

Then change `User root` to `User dev` in `%USERPROFILE%\.ssh\config`. From now on you log
in as `dev`, and root login is off.

## 6. Then

The Herdr app (step 6 of `vps-setup.md`, with the `vps` host from your SSH config) and the
Pi trial (step 8).
