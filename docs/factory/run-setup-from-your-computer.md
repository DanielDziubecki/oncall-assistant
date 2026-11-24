# Set up the VPS from your computer

Claude Code on your Windows computer runs [`scripts/vps-setup.sh`](../../scripts/vps-setup.sh)
on the VPS over SSH, one section at a time, and explains each one. You approve every command.
The script is the repeatable version of [`vps-setup.md`](vps-setup.md), which explains why
each step exists.

Every section, `ssh-access` and `harden` included, worked on a real Ubuntu 24.04 VPS on
2026-11-22. That server already had a firewall, Tailscale and an `AllowUsers` list; a fresh
server has only been tried in a container (`user`, `tools`, `repos` and `check`).

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

Then add this to `%USERPROFILE%\.ssh\config` (create the file if it doesn't exist). `vps` is
root, for the setup; `vps-dev` is your everyday login. If the server is on Tailscale, use its
Tailscale name as both `HostName`s. If your key has another name, change `IdentityFile`.

```
Host vps
    HostName <vps-ip>
    User root
    IdentityFile ~/.ssh/id_ed25519
    IdentitiesOnly yes

Host vps-dev
    HostName <vps-ip>
    User dev
    IdentityFile ~/.ssh/id_ed25519
    IdentitiesOnly yes
```

Run `ssh vps` once yourself and accept the server's fingerprint; Claude Code can't answer that
question. From then on it should log you in without a password.

## 3. Claude Code: run the setup

In the repo folder, start `claude` and give it this prompt:

```
Set up my VPS with scripts/vps-setup.sh. Read it and docs/factory/vps-setup.md first.
Run one section at a time as root with: ssh vps 'bash -s -- <section>' < scripts/vps-setup.sh
in this order: base, user, docker, tools, repos, check.
Before each section, tell me in two sentences what it changes and why. After it, tell me
what happened. If a section fails, explain the cause and propose a fix to the script; don't
work around it on the server by hand.
Never run the ssh-access or harden sections yourself, never handle my passwords or logins,
and stop after check to give me the list of what is left for me.
```

## 4. You: logins and the password

`check` ends with a list of what is left. In your own terminal:

1. `ssh vps`, then `passwd dev` to give `dev` a password (sudo needs it).
2. `ssh vps-dev`, then `cd ~/src/oncall-assistant && bash scripts/logins.sh`. It runs each
   login in turn (Claude Code, Codex, GitHub, ChatGPT in Pi) and skips those that already work.
   Use a GitHub account without admin rights and approve it in a private browser window; the
   script names the account at the end.
3. While still logged in as `dev`, run `sudo true` to prove sudo works.

If SSH refuses `dev`, the server may have an `AllowUsers` list. You can still do steps 2 and 3
from a root session with `su - dev`. To let `dev` in from your Tailscale network, run this
yourself in PowerShell, in the repo folder (PowerShell itself rejects the `<`, so it goes
through Git Bash), then log in with `ssh vps-dev`:

```powershell
& "C:\Program Files\Git\bin\bash.exe" -c "ssh vps 'bash -s -- ssh-access' < scripts/vps-setup.sh"
```

## 5. You: close root login

`harden` ends every root SSH login, fallbacks included. Before you run it:

1. Make sure step 4 worked, including a real `ssh vps-dev` login (`su - dev` doesn't count,
   and `harden` checks).
2. **If you reach the server over Tailscale, turn off its key expiry** (Machines → the server →
   Disable key expiry). Otherwise you are locked out on the day the key expires.
3. **Test your provider's console:** log in there as `dev`, run `sudo true`, then `exit`. It
   will be your only rescue, and its keyboard layout may garble your password.
4. Open `ssh vps` in another terminal and keep it open until you have tested the result.

Then, in PowerShell in the repo folder:

```powershell
& "C:\Program Files\Git\bin\bash.exe" -c "ssh vps 'CONFIRM_DEV_LOGIN=yes bash -s -- harden' < scripts/vps-setup.sh"
```

In a new terminal, `ssh vps-dev` must work and `ssh vps` must be refused. If `vps-dev` fails,
undo it in the session you kept open, or on the console with `sudo` in front of both commands:

```bash
rm /etc/ssh/sshd_config.d/00-hardening.conf
systemctl restart ssh
```

From now on you log in with `ssh vps-dev`. The `ssh vps` commands above no longer work, so run
a section on the server instead:

```bash
cd ~/src/oncall-assistant && git pull && sudo bash scripts/vps-setup.sh check
```

## 6. Then

Pi's packages and a check that both subscriptions work in Pi (step 8 of `vps-setup.md`). As
`dev`, in `~/src/oncall-assistant`, or by asking Claude Code to run them over `ssh vps-dev`:

```bash
bash scripts/pi-setup.sh install && bash scripts/pi-setup.sh check && bash scripts/pi-setup.sh answers
```

Then the Herdr app (step 6 of `vps-setup.md`, with the `vps-dev` host from your SSH config).

## 7. You: SSH only from your Tailscale devices (F1)

After `harden`, SSH still answers on the server's public address, so every bot on the internet
can knock. The `tailnet-only` section makes the firewall accept SSH only on Tailscale. Before
you run it:

1. **Point `vps-dev` at Tailscale.** In `%USERPROFILE%\.ssh\config`, set its `HostName` to the
   server's Tailscale name or its `100.x` address (shown by `tailscale ip -4` on the server, or
   in the Tailscale app), not the public IP. Then log in once with `ssh vps-dev`.
2. **Key expiry is off** for the server in Tailscale (step 5).
3. **The provider's console works** (step 5). If Tailscale ever stops, it is your way back in.

Then, logged in with `ssh vps-dev`:

```bash
cd ~/src/oncall-assistant && git pull && sudo CONFIRM_CONSOLE=yes bash scripts/vps-setup.sh tailnet-only
```

It refuses unless the SSH log shows your key login as `dev` from a Tailscale address since SSH's
settings last changed, so a config that still points at the public IP can't cut you off.

Test it: `ssh vps-dev` must still work, and from a machine outside your tailnet, or with the
Tailscale app switched off, `ssh dev@<public-ip>` must time out. To undo it, on the console:

```bash
sudo ufw allow OpenSSH
```

## 8. You: the agents' sandbox (F1, ADR 9)

Agents work in an Incus container, `oncall`, not as `dev` on the VPS: a wrong command can then
damage the sandbox, not your logins or the server. Logged in with `ssh vps-dev`, in
`~/src/oncall-assistant`, after `git pull`:

```bash
sudo bash scripts/sandbox.sh install
```

```bash
sudo bash scripts/sandbox.sh create
```

```bash
sudo bash scripts/sandbox.sh provision
```

`install` adds Incus and the firewall rules its network needs, and adds you to `incus-admin`
(log out and in again to use `incus` without `sudo`). `create` makes the container, with a
10 GiB memory limit. `provision` builds the inside (user `agent`, Docker, the tools, both repos)
in a few minutes and saves the snapshot `clean`. If it says the sandbox can't reach GitHub,
send the message: the firewall rules for Incus are the part that couldn't be tested before.

Then make the sandbox's own logins. Enter it as `agent`:

```bash
sudo bash scripts/sandbox.sh shell
```

and inside, in `~/src/oncall-assistant`:

```bash
bash scripts/logins.sh && bash scripts/pi-setup.sh install && bash scripts/pi-setup.sh check
```

Use a GitHub account or token limited to this project's two repos, not your admin account.
Leave with `exit`, then save the result: `sudo bash scripts/sandbox.sh snapshot logged-in`.

From now on, start agents in a Herdr pane with `incus exec oncall -- su -l agent`. Useful:
`sudo bash scripts/sandbox.sh status`, and `sudo CONFIRM_RESTORE=yes bash scripts/sandbox.sh restore clean`
to put the whole sandbox back.
