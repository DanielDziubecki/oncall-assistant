import pytest

from oncall import __version__
from oncall.cli import main


def test_version_flag_prints_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--version"])

    assert exc.value.code == 0
    assert capsys.readouterr().out.strip() == f"oncall {__version__}"


def test_no_arguments_exits_cleanly() -> None:
    assert main([]) == 0
