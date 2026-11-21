"""Check that this machine can run the factory: tools, harness logins, memory and disk.

`factory doctor` only runs version and login-status commands. It never calls a model,
so it is free and safe to run any time.
"""

import shutil
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

SETUP_GUIDE = "docs/factory/vps-setup.md"


class Status(StrEnum):
    OK = "ok"
    WARN = "warn"
    FAIL = "fail"


class Check(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    status: Status
    detail: str
    fix: str = ""


@dataclass(frozen=True)
class Output:
    code: int
    stdout: str
    stderr: str

    def first_line(self) -> str:
        """The first non-empty line, from stdout if it has one, else from stderr."""
        for text in (self.stdout, self.stderr):
            for line in text.splitlines():
                if line.strip():
                    return line.strip()
        return ""


Run = Callable[[Sequence[str]], Output | None]
"""Runs a command and returns its output, or None when the program is not installed."""


def run_command(argv: Sequence[str]) -> Output | None:
    executable = shutil.which(argv[0])
    if executable is None:
        return None
    try:
        done = subprocess.run(
            [executable, *argv[1:]], capture_output=True, text=True, timeout=20, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return Output(code=-1, stdout="", stderr=str(exc))
    return Output(code=done.returncode, stdout=done.stdout, stderr=done.stderr)


@dataclass(frozen=True)
class Tool:
    name: str
    argv: tuple[str, ...]
    required: bool
    needed_for: str
    fix: str


TOOLS = (
    Tool("git", ("git", "--version"), True, "everything", "sudo apt-get install -y git"),
    Tool(
        "uv",
        ("uv", "--version"),
        True,
        "the Python projects",
        "curl -LsSf https://astral.sh/uv/install.sh | sh",
    ),
    Tool(
        "docker",
        ("docker", "version", "--format", "{{.Server.Version}}"),
        True,
        "shopfront and the incident lab",
        f"see {SETUP_GUIDE}, section Docker",
    ),
    Tool(
        "docker compose",
        ("docker", "compose", "version", "--short"),
        True,
        "shopfront and the incident lab",
        f"see {SETUP_GUIDE}, section Docker",
    ),
    Tool(
        "gh",
        ("gh", "--version"),
        False,
        "pull requests from this machine",
        f"see {SETUP_GUIDE}, section GitHub CLI",
    ),
    Tool(
        "hc",
        ("hc", "--version"),
        False,
        "the Herdr workspace from F1: Main and helper panes",
        "curl -fsSL https://releases.herdr.dev/core/install.sh | sh",
    ),
    Tool(
        "tmux",
        ("tmux", "-V"),
        False,
        "a fallback workspace where Herdr is not available",
        "sudo apt-get install -y tmux",
    ),
)


def check_tool(tool: Tool, run: Run) -> Check:
    output = run(tool.argv)
    if output is not None and output.code == 0:
        return Check(name=tool.name, status=Status.OK, detail=output.first_line())
    status = Status.FAIL if tool.required else Status.WARN
    problem = "not installed" if output is None else output.first_line() or "failed"
    return Check(
        name=tool.name,
        status=status,
        detail=f"{problem} (needed for {tool.needed_for})",
        fix=tool.fix,
    )


class _ClaudeAuth(BaseModel):
    model_config = ConfigDict(extra="ignore")

    logged_in: bool = Field(default=False, alias="loggedIn")
    auth_method: str = Field(default="", alias="authMethod")


def check_claude(run: Run) -> Check:
    version = run(("claude", "--version"))
    if version is None or version.code != 0:
        return Check(
            name="claude",
            status=Status.WARN,
            detail="Claude Code is not installed",
            fix=f"see {SETUP_GUIDE}, section Claude Code and Codex",
        )
    status = run(("claude", "auth", "status", "--json"))
    try:
        auth = _ClaudeAuth.model_validate_json(status.stdout) if status else _ClaudeAuth()
    except ValidationError:
        auth = _ClaudeAuth()
    if not auth.logged_in:
        return Check(
            name="claude",
            status=Status.WARN,
            detail=f"{version.first_line()}, not logged in",
            fix="run `claude` and log in with your subscription account",
        )
    return Check(
        name="claude",
        status=Status.OK,
        detail=f"{version.first_line()}, logged in ({auth.auth_method or 'unknown method'})",
    )


def check_codex(run: Run) -> Check:
    version = run(("codex", "--version"))
    if version is None or version.code != 0:
        return Check(
            name="codex",
            status=Status.WARN,
            detail="Codex CLI is not installed",
            fix=f"see {SETUP_GUIDE}, section Claude Code and Codex",
        )
    status = run(("codex", "login", "status"))
    if status is None or status.code != 0:
        return Check(
            name="codex",
            status=Status.WARN,
            detail=f"{version.first_line()}, not logged in",
            fix="run `codex login --device-auth` and log in with your ChatGPT account",
        )
    return Check(
        name="codex", status=Status.OK, detail=f"{version.first_line()}, {status.first_line()}"
    )


def check_harnesses(claude: Check, codex: Check) -> Check:
    ready = [c.name for c in (claude, codex) if c.status is Status.OK]
    if not ready:
        return Check(
            name="harness",
            status=Status.FAIL,
            detail="no harness is installed and logged in, so `factory ask` can't run",
            fix="install and log in to Claude Code or Codex, ideally both",
        )
    return Check(name="harness", status=Status.OK, detail=f"ready: {', '.join(ready)}")


def check_os(os_release: Path) -> Check:
    name = ""
    if os_release.exists():
        for line in os_release.read_text().splitlines():
            if line.startswith("PRETTY_NAME="):
                name = line.split("=", 1)[1].strip().strip('"')
    return Check(name="os", status=Status.OK, detail=name or "unknown (no /etc/os-release)")


def check_memory(meminfo: Path, *, warn_below_gib: float = 8) -> Check:
    total_kib = 0
    if meminfo.exists():
        for line in meminfo.read_text().splitlines():
            if line.startswith("MemTotal:"):
                total_kib = int(line.split()[1])
    if total_kib == 0:
        return Check(name="memory", status=Status.WARN, detail="unknown (no /proc/meminfo)")
    total_gib = total_kib / 1024**2
    status = Status.WARN if total_gib < warn_below_gib else Status.OK
    return Check(
        name="memory",
        status=status,
        detail=f"{total_gib:.1f} GiB total; shopfront with stack A uses about 2 GiB",
    )


def check_disk(path: Path, *, warn_below_gib: float = 20) -> Check:
    free_gib = shutil.disk_usage(path).free / 1024**3
    status = Status.WARN if free_gib < warn_below_gib else Status.OK
    return Check(
        name="disk",
        status=status,
        detail=f"{free_gib:.0f} GiB free in {path}",
        fix="free space: Docker images and uv caches need about 20 GiB"
        if status is Status.WARN
        else "",
    )


def diagnose(
    run: Run = run_command,
    *,
    os_release: Path = Path("/etc/os-release"),
    meminfo: Path = Path("/proc/meminfo"),
    home: Path | None = None,
) -> list[Check]:
    checks = [check_os(os_release), check_memory(meminfo), check_disk(home or Path.home())]
    checks += [check_tool(tool, run) for tool in TOOLS]
    claude, codex = check_claude(run), check_codex(run)
    checks += [claude, codex, check_harnesses(claude, codex)]
    return checks


def render(checks: Sequence[Check]) -> str:
    width = max(len(c.name) for c in checks)
    lines: list[str] = []
    for check in checks:
        lines.append(f"{check.status.value:<4}  {check.name:<{width}}  {check.detail}")
        if check.fix and check.status is not Status.OK:
            lines.append(f"{'':<4}  {'':<{width}}  fix: {check.fix}")
    failures = sum(c.status is Status.FAIL for c in checks)
    warnings = sum(c.status is Status.WARN for c in checks)
    lines.append("")
    if failures:
        lines.append(
            f"{failures} problem(s) to fix before the factory can run; {warnings} warning(s)."
        )
    else:
        lines.append(f"Ready. {warnings} warning(s).")
    return "\n".join(lines)
