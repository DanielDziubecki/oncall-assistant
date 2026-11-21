from collections.abc import Sequence
from pathlib import Path

from factory.doctor import TOOLS, Output, Status, diagnose, render

CLAUDE_LOGGED_IN = '{"loggedIn": true, "authMethod": "oauth_token", "configDirectory": "/x"}'
CLAUDE_LOGGED_OUT = '{"loggedIn": false}'


class FakeMachine:
    """Answers the doctor's commands from a table; a missing program returns None."""

    def __init__(self, answers: dict[tuple[str, ...], Output]) -> None:
        self.answers = answers

    def __call__(self, argv: Sequence[str]) -> Output | None:
        return self.answers.get(tuple(argv))


def ready_machine() -> dict[tuple[str, ...], Output]:
    answers = {tool.argv: Output(0, f"{tool.name} 1.0\n", "") for tool in TOOLS}
    answers[("claude", "--version")] = Output(0, "2.1.330 (Claude Code)\n", "")
    answers[("claude", "auth", "status", "--json")] = Output(0, CLAUDE_LOGGED_IN, "")
    answers[("codex", "--version")] = Output(0, "codex-cli 0.171.0\n", "")
    answers[("codex", "login", "status")] = Output(0, "Logged in using ChatGPT\n", "")
    return answers


Answers = dict[tuple[str, ...], Output]


def by_name(answers: Answers, tmp_path: Path) -> dict[str, tuple[Status, str]]:
    meminfo = tmp_path / "meminfo"
    meminfo.write_text("MemTotal:       16384000 kB\nMemFree:         1000 kB\n")
    os_release = tmp_path / "os-release"
    os_release.write_text('NAME="Ubuntu"\nPRETTY_NAME="Ubuntu 24.04.3 LTS"\n')
    checks = diagnose(FakeMachine(answers), os_release=os_release, meminfo=meminfo, home=tmp_path)
    return {check.name: (check.status, check.detail) for check in checks}


def test_a_ready_machine_has_no_failures(tmp_path: Path) -> None:
    checks = by_name(ready_machine(), tmp_path)

    assert all(status is not Status.FAIL for status, _ in checks.values())
    assert checks["os"] == (Status.OK, "Ubuntu 24.04.3 LTS")
    assert checks["memory"][1].startswith("15.6 GiB total")
    assert checks["claude"] == (Status.OK, "2.1.330 (Claude Code), logged in (oauth_token)")
    assert checks["codex"] == (Status.OK, "codex-cli 0.171.0, Logged in using ChatGPT")
    assert checks["harness"] == (Status.OK, "ready: claude, codex")


def test_a_missing_required_tool_fails(tmp_path: Path) -> None:
    answers = ready_machine()
    del answers[("docker", "version", "--format", "{{.Server.Version}}")]

    status, detail = by_name(answers, tmp_path)["docker"]

    assert status is Status.FAIL
    assert detail.startswith("not installed")


def test_docker_without_access_to_its_daemon_fails_with_the_reason(tmp_path: Path) -> None:
    answers = ready_machine()
    answers[("docker", "version", "--format", "{{.Server.Version}}")] = Output(
        1, "", "permission denied while trying to connect to the docker API\n"
    )

    status, detail = by_name(answers, tmp_path)["docker"]

    assert status is Status.FAIL
    assert detail.startswith("permission denied")


def test_a_missing_optional_tool_only_warns(tmp_path: Path) -> None:
    answers = ready_machine()
    del answers[("hc", "--version")]

    assert by_name(answers, tmp_path)["hc"][0] is Status.WARN


def test_one_logged_in_harness_is_enough(tmp_path: Path) -> None:
    answers = ready_machine()
    answers[("codex", "login", "status")] = Output(1, "Not logged in\n", "")

    checks = by_name(answers, tmp_path)

    assert checks["codex"] == (Status.WARN, "codex-cli 0.171.0, not logged in")
    assert checks["harness"] == (Status.OK, "ready: claude")


def test_no_logged_in_harness_fails(tmp_path: Path) -> None:
    answers = ready_machine()
    answers[("claude", "auth", "status", "--json")] = Output(1, CLAUDE_LOGGED_OUT, "")
    del answers[("codex", "--version")]

    checks = by_name(answers, tmp_path)

    assert checks["claude"][0] is Status.WARN
    assert checks["codex"] == (Status.WARN, "Codex CLI is not installed")
    assert checks["harness"][0] is Status.FAIL


def test_the_report_shows_fixes_for_problems_only(tmp_path: Path) -> None:
    answers = ready_machine()
    del answers[("git", "--version")]
    meminfo = tmp_path / "meminfo"
    meminfo.write_text("MemTotal: 16384000 kB\n")
    checks = diagnose(
        FakeMachine(answers), os_release=tmp_path / "none", meminfo=meminfo, home=tmp_path
    )

    report = render(checks)

    assert "fail  git" in report
    assert "fix: sudo apt-get install -y git" in report
    assert "fix: curl -LsSf https://astral.sh/uv/install.sh" not in report
    assert report.splitlines()[-1].startswith("1 problem(s) to fix")
