"""`factory` command line: ask a harness one question, or check this machine."""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from factory import __version__
from factory.ask import ask
from factory.config import HarnessModels, Size, load_models
from factory.doctor import Status, diagnose, render
from factory.drivers import DRIVERS, HarnessError

ASK_EXAMPLES = """examples:
  factory ask --harness claude "Name three risks of retrying a payment."
  factory ask --harness codex --size large --json "Review this plan: ..."
  git diff | factory ask --harness claude "Summarize this diff in two lines."
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="factory",
        description="Development factory: runs Claude Code and Codex as interchangeable workers.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    ask_parser = commands.add_parser(
        "ask",
        help="ask one harness one question, headless and without tools",
        description=(
            "Ask one harness one question. The run is headless and has no tools, and it loads "
            "none of the project's instructions, skills or hooks: its only context is the "
            "prompt. The model comes from factory/models.toml for the chosen size."
        ),
        epilog=ASK_EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ask_parser.add_argument(
        "prompt", nargs="?", default="-", help="the question; '-' or nothing reads stdin"
    )
    ask_parser.add_argument("--harness", choices=sorted(DRIVERS), required=True)
    ask_parser.add_argument(
        "--size", choices=[size.value for size in Size], default=Size.SMALL.value
    )
    ask_parser.add_argument("--model", help="use this model for this run only")
    ask_parser.add_argument("--effort", help="use this effort level for this run only")
    ask_parser.add_argument(
        "--timeout", type=float, default=300, help="seconds to wait (default: 300)"
    )
    ask_parser.add_argument(
        "--json", action="store_true", help="print the whole result: text, model, time, tokens"
    )

    doctor_parser = commands.add_parser(
        "doctor",
        help="check this machine: tools, harness logins, memory and disk (no model calls)",
    )
    doctor_parser.add_argument("--json", action="store_true", help="print the checks as JSON")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "ask":
        return _ask(args)
    return _doctor(args)


def _ask(args: argparse.Namespace) -> int:
    prompt: str = sys.stdin.read() if args.prompt == "-" else args.prompt
    if not prompt.strip():
        print("factory ask: the prompt is empty", file=sys.stderr)
        return 2

    driver = DRIVERS[args.harness]
    configured = load_models().get(driver.name, HarnessModels()).for_size(Size(args.size))
    overrides = {key: getattr(args, key) for key in ("model", "effort") if getattr(args, key)}
    choice = configured.model_copy(update=overrides)

    try:
        result = ask(driver, prompt, choice, cwd=Path.cwd(), timeout_s=args.timeout)
    except HarnessError as exc:
        print(f"factory ask: {exc}", file=sys.stderr)
        return 1
    print(result.model_dump_json(indent=2) if args.json else result.text)
    return 0


def _doctor(args: argparse.Namespace) -> int:
    checks = diagnose()
    if args.json:
        print(json.dumps([check.model_dump(mode="json") for check in checks], indent=2))
    else:
        print(render(checks))
    return 1 if any(check.status is Status.FAIL for check in checks) else 0
