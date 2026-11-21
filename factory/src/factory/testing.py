"""Fake harness executables, for tests and dry runs.

A fake records the argv it got and the text it read on stdin in files next to itself, then
runs a short Python body, usually one that prints a canned answer. Nothing calls a model.
"""

import json
import stat
import sys
from pathlib import Path

_RECORD = """import json, pathlib, sys
here = pathlib.Path(__file__)
here.with_name(here.name + ".argv.json").write_text(json.dumps(sys.argv[1:]))
here.with_name(here.name + ".stdin.txt").write_text(sys.stdin.read())
"""


def write_fake(directory: Path, name: str, body: str) -> Path:
    """Write an executable `name` into `directory` that records its input, then runs `body`."""
    path = directory / name
    path.write_text(f"#!{sys.executable}\n{_RECORD}{body}")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


def prints(path: Path) -> str:
    """A body that prints the contents of `path`, such as a recorded `claude -p` result."""
    return f"sys.stdout.write(pathlib.Path({str(path)!r}).read_text())\n"


def codex_answers(answer: str, events: Path) -> str:
    """A body that writes `answer` where `--output-last-message` points, then prints `events`."""
    return (
        'out = pathlib.Path(sys.argv[sys.argv.index("--output-last-message") + 1])\n'
        f"out.write_text({answer!r})\n"
        f"sys.stdout.write(pathlib.Path({str(events)!r}).read_text())\n"
    )


def fails(code: int, message: str) -> str:
    """A body that prints `message` on stderr and exits with `code`."""
    return f"sys.stderr.write({message!r})\nsys.exit({code})\n"


def hangs(seconds: float) -> str:
    """A body that sleeps, to test timeouts."""
    return f"import time\ntime.sleep({seconds})\n"


def recorded_argv(fake: Path) -> list[str]:
    argv: list[str] = json.loads(fake.with_name(fake.name + ".argv.json").read_text())
    return argv


def recorded_stdin(fake: Path) -> str:
    return fake.with_name(fake.name + ".stdin.txt").read_text()
