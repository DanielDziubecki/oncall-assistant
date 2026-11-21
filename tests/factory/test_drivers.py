from pathlib import Path

import pytest

from factory.config import ModelChoice
from factory.drivers import HarnessError
from factory.drivers.claude import ClaudeDriver
from factory.drivers.codex import LAST_MESSAGE_FILE, CodexDriver

FIXTURES = Path(__file__).parent / "fixtures"
CLAUDE_RESULT = (FIXTURES / "claude-result.json").read_text()
CODEX_EVENTS = (FIXTURES / "codex-exec.synthetic.jsonl").read_text()


# Claude


def test_claude_runs_headless_without_tools_or_project_config(tmp_path: Path) -> None:
    argv = ClaudeDriver().command(ModelChoice(), tmp_path)

    assert argv[:2] == ["claude", "-p"]
    assert argv[argv.index("--output-format") + 1] == "json"
    assert argv[argv.index("--tools") + 1] == ""
    assert "--safe-mode" in argv
    assert "--no-session-persistence" in argv
    assert "--model" not in argv
    assert "--effort" not in argv


def test_claude_passes_model_and_effort_when_set(tmp_path: Path) -> None:
    argv = ClaudeDriver().command(ModelChoice(model="haiku", effort="low"), tmp_path)

    assert argv[argv.index("--model") + 1] == "haiku"
    assert argv[argv.index("--effort") + 1] == "low"


def test_claude_reads_text_model_cost_and_tokens(tmp_path: Path) -> None:
    reply = ClaudeDriver().parse(CLAUDE_RESULT, tmp_path)

    assert reply.text == "OK"
    assert reply.model == "example-small-model"
    assert reply.session_id == "00000000-0000-4000-8000-000000000001"
    assert reply.cost_usd == pytest.approx(0.00062689)
    # Claude counts cache reads and writes apart from input_tokens; the reply adds them back.
    assert reply.input_tokens == 2 + 649 + 3091
    assert reply.cached_input_tokens == 649
    assert reply.output_tokens == 4


def test_claude_error_result_is_a_harness_error(tmp_path: Path) -> None:
    failed = CLAUDE_RESULT.replace('"is_error": false', '"is_error": true').replace(
        '"result": "OK"', '"result": "Credit balance is too low"'
    )

    with pytest.raises(HarnessError, match="Credit balance is too low"):
        ClaudeDriver().parse(failed, tmp_path)


def test_claude_output_that_is_not_a_result_is_a_harness_error(tmp_path: Path) -> None:
    with pytest.raises(HarnessError, match="unexpected result"):
        ClaudeDriver().parse("Welcome to Claude Code!", tmp_path)


# Codex


def test_codex_runs_read_only_ephemeral_and_reads_the_prompt_from_stdin(tmp_path: Path) -> None:
    argv = CodexDriver().command(ModelChoice(), tmp_path)

    assert argv[:3] == ["codex", "exec", "--json"]
    assert argv[argv.index("--sandbox") + 1] == "read-only"
    assert "--ephemeral" in argv
    assert "--skip-git-repo-check" in argv
    assert argv[argv.index("--disable") + 1] == "hooks"
    assert argv[argv.index("--output-last-message") + 1] == str(tmp_path / LAST_MESSAGE_FILE)
    assert argv[-1] == "-"
    assert "--model" not in argv
    assert "-c" not in argv


def test_codex_passes_model_and_reasoning_effort_when_set(tmp_path: Path) -> None:
    argv = CodexDriver().command(ModelChoice(model="small-codex", effort="low"), tmp_path)

    assert argv[argv.index("--model") + 1] == "small-codex"
    assert argv[argv.index("-c") + 1] == 'model_reasoning_effort="low"'
    assert argv[-1] == "-"


def test_codex_reads_text_from_the_last_message_and_numbers_from_events(tmp_path: Path) -> None:
    (tmp_path / LAST_MESSAGE_FILE).write_text("OK\n")

    reply = CodexDriver().parse(CODEX_EVENTS, tmp_path)

    assert reply.text == "OK"
    assert reply.session_id == "00000000-0000-4000-8000-0000000000c1"
    assert reply.input_tokens == 2400
    assert reply.cached_input_tokens == 1800
    assert reply.output_tokens == 5
    assert reply.cost_usd is None


def test_codex_skips_lines_it_does_not_recognize(tmp_path: Path) -> None:
    (tmp_path / LAST_MESSAGE_FILE).write_text("OK")
    events = "not json\n" + '{"type":"something.new","payload":[1,2]}\n' + CODEX_EVENTS

    reply = CodexDriver().parse(events, tmp_path)

    assert reply.text == "OK"
    assert reply.output_tokens == 5


def test_codex_without_a_final_message_reports_the_last_error(tmp_path: Path) -> None:
    events = '{"type":"turn.failed","error":{"message":"usage limit reached"}}\n'

    with pytest.raises(HarnessError, match="usage limit reached"):
        CodexDriver().parse(events, tmp_path)
