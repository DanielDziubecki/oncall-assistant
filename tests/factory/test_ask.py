from pathlib import Path

import pytest

from factory.ask import ask
from factory.config import ModelChoice
from factory.drivers import HarnessError
from factory.drivers.claude import ClaudeDriver
from factory.drivers.codex import CodexDriver
from factory.testing import (
    codex_answers,
    fails,
    hangs,
    prints,
    recorded_argv,
    recorded_stdin,
    write_fake,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_claude_gets_the_prompt_on_stdin_and_the_driver_flags(
    fake_bin: Path, tmp_path: Path
) -> None:
    fake = write_fake(fake_bin, "claude", prints(FIXTURES / "claude-result.json"))
    choice = ModelChoice(model="haiku")

    result = ask(ClaudeDriver(), "Is 7 prime?", choice, cwd=tmp_path, env={"PATH": str(fake_bin)})

    assert result.harness == "claude"
    assert result.text == "OK"
    assert result.model == "example-small-model"
    assert result.duration_ms >= 0
    assert recorded_stdin(fake) == "Is 7 prime?"
    assert recorded_argv(fake) == ClaudeDriver().command(choice, tmp_path)[1:]
    assert "Is 7 prime?" not in recorded_argv(fake)


def test_codex_answer_comes_from_its_last_message_file(fake_bin: Path, tmp_path: Path) -> None:
    fake = write_fake(
        fake_bin, "codex", codex_answers("OK\n", FIXTURES / "codex-exec.synthetic.jsonl")
    )

    result = ask(
        CodexDriver(), "Is 7 prime?", ModelChoice(), cwd=tmp_path, env={"PATH": str(fake_bin)}
    )

    assert result.harness == "codex"
    assert result.text == "OK"
    assert result.model == "default"
    assert result.output_tokens == 5
    assert recorded_stdin(fake) == "Is 7 prime?"


def test_a_missing_harness_says_how_to_install_it(fake_bin: Path, tmp_path: Path) -> None:
    with pytest.raises(HarnessError, match=r"`codex` is not installed.*vps-setup\.md"):
        ask(CodexDriver(), "hi", ModelChoice(), cwd=tmp_path, env={"PATH": str(fake_bin)})


def test_a_failed_run_reports_its_exit_code_and_stderr(fake_bin: Path, tmp_path: Path) -> None:
    write_fake(fake_bin, "claude", fails(3, "Not logged in. Run /login."))

    with pytest.raises(HarnessError, match=r"exited with code 3: Not logged in\. Run /login\."):
        ask(ClaudeDriver(), "hi", ModelChoice(), cwd=tmp_path, env={"PATH": str(fake_bin)})


def test_a_run_that_takes_too_long_is_stopped(fake_bin: Path, tmp_path: Path) -> None:
    write_fake(fake_bin, "claude", hangs(10))

    with pytest.raises(HarnessError, match=r"no answer within 0\.5 s"):
        ask(
            ClaudeDriver(),
            "hi",
            ModelChoice(),
            cwd=tmp_path,
            timeout_s=0.5,
            env={"PATH": str(fake_bin)},
        )
