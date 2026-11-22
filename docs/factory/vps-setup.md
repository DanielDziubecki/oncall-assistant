# VPS setup

Sets up the VPS that runs Main, the factory and shopfront, from a fresh server. It assumes
Ubuntu 24.04 LTS; other Debian-based systems need small changes. Target size: 16 GB RAM,
4 vCPU and at least 40 GB of free disk.

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

From your computer, check that `ssh dev@<vps>` works. **Keep that session open**, then turn off
password and root login. A file of our own in `sshd_config.d` wins over the one many cloud
images ship that turns passwords back on:

```bash
printf 'PasswordAuthentication no\nPermitRootLogin no\n' | sudo tee /etc/ssh/sshd_config.d/00-hardening.conf
sudo systemctl restart ssh
```

Open a second session to confirm you can still log in. Add a `Host vps` entry for it in
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
sudo apt-get update && sudo apt-get install -y git make tmux gh unattended-upgrades
sudo ufw allow OpenSSH && sudo ufw --force enable
```

## 4. Agent: Docker

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker dev
```

Log out and back in, then `docker run --rm hello-world`.

- **Docker group means root.** Anyone, or any agent, that can run Docker controls the whole VPS. Keep this VPS for this project only, with no other secrets on it.
- **Published ports skip the firewall.** Docker writes its own rules, so `ufw` doesn't protect a published port. Shopfront binds every port to `127.0.0.1`; keep it that way, and open Grafana through a tunnel: `ssh -L 3000:127.0.0.1:3000 vps`, then <http://localhost:3000>.

## 5. Agent: uv, .NET, Node and Codex

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
curl -fsSL https://dot.net/v1/dotnet-install.sh | bash -s -- --channel 10.0
echo 'export DOTNET_ROOT="$HOME/.dotnet"; export PATH="$HOME/.dotnet:$PATH"' >> ~/.bashrc
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt-get install -y nodejs
npm config set prefix ~/.local
npm install -g @openai/codex
```

uv runs the Python product, the .NET 10 SDK builds the factory (installed into `~/.dotnet`
without `sudo`), and Node runs Codex. `~/.local/bin` (uv, Codex) must be on `PATH`; the uv
installer offers to add it. Open a new shell afterwards so the `PATH` changes apply.

**You:** run `codex login --device-auth` and sign in with your ChatGPT account.

## 6. You: Herdr

On **your computer**, install the Herdr app: <https://github.com/herdrdev/herdr-app#install>.
In Settings → Machines, add the VPS by its SSH host (`vps`). If the VPS has no core yet, the
app can install it; to install it by hand instead, on the VPS:

```bash
curl -fsSL https://releases.herdr.dev/core/install.sh | sh
```

Terminals you open on the VPS keep running when you close the app or your laptop.

## 7. Agent: the repos and the factory check

```bash
mkdir -p ~/src && cd ~/src
git clone https://github.com/DanielDziubecki/oncall-assistant.git
git clone https://github.com/DanielDziubecki/shopfront.git
cd oncall-assistant && make install && make check
bin/factory doctor
```

**You:** run `gh auth login`, then `gh auth setup-git`, so agents can push branches and open PRs.

The VPS is ready when `factory doctor` reports no failures and both harnesses answer:

```bash
bin/factory ask --harness claude "Reply with OK"
bin/factory ask --harness codex "Reply with OK"
```

## What never goes on this VPS's containers

Your Claude and Codex logins live in `~/.claude` and `~/.codex`. Never mount those
folders, or any API key, into a shopfront or agent container. From step 6 of the project,
the credential proxy is the only holder of the product's API keys.
