# VPS setup

Sets up the VPS that runs Main, the factory and shopfront, from a fresh server. It assumes
Ubuntu 24.04 LTS; other Debian-based systems need small changes. Target size: 16 GB RAM,
4 vCPU and at least 40 GB of free disk.

**Scripted:** [`scripts/vps-setup.sh`](../../scripts/vps-setup.sh) does steps 1–7 except the logins,
run from your computer by Claude Code over SSH. Start with
[`run-setup-from-your-computer.md`](run-setup-from-your-computer.md); this page explains why each step exists.

Steps marked **You** need your accounts or your computer. Once Claude Code is installed
(step 2), it can do the rest with you: start `claude` in your home directory and say
*"Read https://github.com/DanielDziubecki/oncall-assistant/blob/main/docs/factory/vps-setup.md
and do steps 3 to 7 with me. Stop before anything that needs my accounts."*

Each installer below downloads and runs a script. Open the URL first if you want to read it.

## 1. You: a user that logs in with a key

On the VPS, logged in as root or as the provider's first user:

```bash
sudo adduser dev
sudo usermod -aG sudo dev
sudo mkdir -p /home/dev/.ssh && sudo cp ~/.ssh/authorized_keys /home/dev/.ssh/
sudo chown -R dev:dev /home/dev/.ssh && sudo chmod 700 /home/dev/.ssh
```

From your computer, check that `ssh dev@<vps>` works. If it doesn't, stop: turning off root
login now would lock you out (`sudo sshd -T | grep allowusers` shows whether an allow-list is
the cause). If you reach the server over Tailscale, also turn off its key expiry first, and
in any case test that you can log in on the provider's console as `dev`: after this it is your
only rescue. If all of that works, **keep that session open**, then turn off
password and root login. A file of our own in `sshd_config.d` wins over the one many cloud
images ship that turns passwords back on:

```bash
printf 'PasswordAuthentication no\nPermitRootLogin no\n' | sudo tee /etc/ssh/sshd_config.d/00-hardening.conf
sudo systemctl restart ssh
```

Open a second session to confirm you can still log in. Add a `Host vps-dev` entry for it in
`~/.ssh/config` on your computer; Herdr uses it in step 6.

## 2. You: Claude Code

As `dev`, without `sudo` (the installer refuses it):

```bash
curl -fsSL https://claude.ai/install.sh | bash
```

Run `claude`, choose your subscription account and open the link it prints. Official guide:
<https://code.claude.com/docs/en/setup>.

## 3. Agent: base packages and firewall

```bash
sudo apt-get update && sudo apt-get install -y git make curl ca-certificates tmux gh ufw unattended-upgrades
sudo ufw allow OpenSSH && sudo ufw --force enable
```

## 4. Agent: Docker

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker dev
```

Log out and back in, then `docker run --rm hello-world`.

- **Docker group means root.** Anyone, or any agent, that can run Docker controls the whole VPS. Keep this VPS for this project only, with no other secrets on it.
- **Published ports skip the firewall.** Docker writes its own rules, so `ufw` doesn't protect a published port. Shopfront binds every port to `127.0.0.1`; keep it that way, and open Grafana through a tunnel: `ssh -L 3000:127.0.0.1:3000 vps-dev`, then <http://localhost:3000>.

## 5. Agent: uv, Node and Codex

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt-get install -y nodejs
npm config set prefix ~/.local
npm install -g @openai/codex
```

uv runs the Python product, and Node runs Codex and Pi. `~/.local/bin` (uv, Codex) must be
on `PATH`; the uv installer offers to add it. Open a new shell afterwards so the `PATH`
changes apply.

**You:** run `codex login --device-auth` and sign in with your ChatGPT account.

## 6. You: Herdr

On **your computer**, install the Herdr app: <https://github.com/herdrdev/herdr-app#install>.
In Settings → Machines, add the VPS by its SSH host (`vps-dev`, so it uses `dev`'s tools and not root's). If the VPS has no core yet, the
app can install it; to install it by hand instead, on the VPS:

```bash
curl -fsSL https://releases.herdr.dev/core/install.sh | sh
```

Terminals you open on the VPS keep running when you close the app or your laptop.

## 7. Agent: the repos and a first headless answer

```bash
mkdir -p ~/src && cd ~/src
git clone https://github.com/DanielDziubecki/oncall-assistant.git
git clone https://github.com/DanielDziubecki/shopfront.git
cd oncall-assistant && make install && make check
```

**You:** run `gh auth login`, then `gh auth setup-git`, so agents can push branches and open PRs.

Both subscriptions should answer one question without a conversation and without tools:

```bash
echo "Reply with OK" | claude -p --tools "" --safe-mode
echo "Reply with OK" | codex exec --sandbox read-only --ephemeral -
```

## 8. You and Agent: the Pi trial

This step decided the factory's harness (ADR 5): Pi, with your Claude and ChatGPT
subscriptions as providers inside it ([ADR 8](../adr/0008-pi-as-harness.md)). On a new
server, repeat it to check that both still work. Work in an empty folder such as
`~/pi-trial`, so Pi loads no project instructions, and send no message in an interactive
`pi`: it runs tools without asking.

1. **Install Pi** (it needs Node 22.19 or newer, from step 5). `scripts/vps-setup.sh` already
   did; otherwise:

   ```bash
   npm install -g --ignore-scripts @earendil-works/pi-coding-agent
   ```

2. **Claude through your subscription.** Install the extension, which routes Pi's Claude requests through Claude Code (`claude -p`), using the login from step 2. Read the code of a Pi package before installing it, and pin it to the commit you read: an unpinned git package is reset to its newest code every time Pi starts.

   ```bash
   pi install git:github.com/earendil-works/pi-claude-code@d5b5e04c314d3452d357174d16d10dda34daa2d2
   ```

   Start `pi`, run `/claude-code-status`, then check that `/model` lists the "Claude Code Subscription (Experimental)" provider.

3. **ChatGPT through your subscription.** Start `PI_HYPERLINKS=0 pi`, run `/login` and choose the ChatGPT (Codex) login, not an OpenAI API key. Over SSH the sign-in link is invisible unless links are off, and its copy to the clipboard may not arrive. Open the link on your computer; the browser then fails on a `localhost` address, which you paste back into Pi.

4. **One headless answer from each.** The ChatGPT models are under the `openai-codex` provider:

   ```bash
   pi --list-models
   ```

   ```bash
   pi -p --mode json --no-tools --model claude-code/<a model from the list> "Reply with OK" > claude.jsonl
   ```

   ```bash
   pi -p --mode json --no-tools --model openai-codex/<a model from the list> "Reply with OK" > openai.jsonl
   ```

5. **The course's extensions.** Install John's lab and agent extensions, pinned, then run only `/lab doctor` inside `pi`. Both need Pi inside the Herdr desktop app, so on a headless VPS the doctor reports `herdr-app not found on PATH`; that is expected. Don't run `/lab new` or `/lab test` before the action monitor (F2): they start agents with tools on.

   ```bash
   pi install git:github.com/johnlindquist/herdr-pi-lab@83ad72fa2bfc0291ef65eafeb043c3fe2c7319f7
   ```

   ```bash
   pi install git:github.com/johnlindquist/herdr-pi-role@e51fca8c503c92b2d00475f9cba19db00f774eee
   ```

6. **Instructions load once.** Run the Claude command from step 4 inside this repo, writing to a file outside it, and look at the `project_context` section of the system prompt in the JSON. It should hold `AGENTS.md` once and no `CLAUDE.md`.

**The trial passes** when steps 2, 3, 4 and 6 work. The trial's samples, with ids and account
usage removed, are in [`factory/samples/pi/`](../../factory/samples/pi/).

## What never goes on this VPS's containers

Your Claude and Codex logins live in `~/.claude` and `~/.codex`. Never mount those
folders, or any API key, into a shopfront or agent container. From step 6 of the project,
the credential proxy is the only holder of the product's API keys.
