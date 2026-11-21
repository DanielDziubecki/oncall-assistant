import io
import json
from pathlib import Path

import pytest

from factory import __version__, cli
from factory.config import Size, load_models
from factory.doctor import Check, Status
from factory.drivers import DRIVERS
from factory.testing import prints, recorded_argv, write_fake

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fake_claude(fake_bin: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("PATH", str(fake_bin))
    return write_fake(fake_bin, "claude", prints(FIXTURES / "claude-result.json"))


def test_version_flag_prints_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(["--version"])

    assert exc.value.code == 0
    assert capsys.readouterr().out.strip() == f"factory {__version__}"


def test_ask_prints_the_answer(fake_claude: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["ask", "--harness", "claude", "Is 7 prime?"]) == 0

    assert capsys.readouterr().out == "OK\n"


def test_ask_uses_the_configured_model_unless_overridden(fake_claude: Path) -> None:
    configured = load_models()["claude"].for_size(Size.SMALL).model

    cli.main(["ask", "--harness", "claude", "hi"])
    configured_argv = recorded_argv(fake_claude)
    cli.main(["ask", "--harness", "claude", "--model", "other-model", "hi"])
    overridden_argv = recorded_argv(fake_claude)

    assert configured_argv[configured_argv.index("--model") + 1] == configured
    assert overridden_argv[overridden_argv.index("--model") + 1] == "other-model"


def test_ask_json_prints_the_whole_result(
    fake_claude: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cli.main(["ask", "--harness", "claude", "--json", "hi"])

    result = json.loads(capsys.readouterr().out)
    assert result["harness"] == "claude"
    assert result["text"] == "OK"
    assert result["cached_input_tokens"] == 649


def test_ask_reads_the_prompt_from_stdin(
    fake_claude: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("Summarize: retries need idempotency keys."))

    assert cli.main(["ask", "--harness", "claude"]) == 0
    assert capsys.readouterr().out == "OK\n"


def test_an_empty_prompt_is_refused(fake_claude: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["ask", "--harness", "claude", "  "]) == 2
    assert "empty" in capsys.readouterr().err


def test_a_harness_error_exits_1_with_the_reason(
    fake_bin: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("PATH", str(fake_bin))

    assert cli.main(["ask", "--harness", "codex", "hi"]) == 1
    assert "`codex` is not installed" in capsys.readouterr().err


def test_every_driver_has_models_for_both_sizes() -> None:
    models = load_models()

    assert set(DRIVERS) <= set(models)


def test_doctor_exits_1_when_a_check_fails(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    checks = [
        Check(name="git", status=Status.OK, detail="git version 2.43.0"),
        Check(name="docker", status=Status.FAIL, detail="not installed", fix="see the guide"),
    ]
    monkeypatch.setattr(cli, "diagnose", lambda: checks)

    assert cli.main(["doctor", "--json"]) == 1
    printed = json.loads(capsys.readouterr().out)
    assert [c["status"] for c in printed] == ["ok", "fail"]
