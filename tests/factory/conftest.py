"""Shared fixtures. Fake harnesses come from `factory.testing`, so no test calls a model.

`fixtures/claude-result.json` is a recorded `claude -p` result with the model name and ids
replaced. `fixtures/codex-exec.synthetic.jsonl` is synthetic: written from the documented
event names, not recorded. Replace it with a recorded run once Codex runs on the VPS.
"""

from pathlib import Path

import pytest


@pytest.fixture
def fake_bin(tmp_path: Path) -> Path:
    """An empty directory for fake executables; use it as PATH."""
    directory = tmp_path / "bin"
    directory.mkdir()
    return directory
