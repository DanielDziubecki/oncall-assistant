"""`lab` command line: run the target with the lab overlay, inject incidents, check for leaks."""

import argparse
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from lab import leakcheck
from lab.injector import Injector
from lab.scenario import find, load_catalog
from lab.stack import LAB_DIR, Stack
from lab.toxiproxy import Toxiproxy

DEFAULT_TARGET = Path(os.environ.get("LAB_TARGET", LAB_DIR.parents[1] / "shopfront"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="lab", description=__doc__)
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET, help="target repo checkout")
    parser.add_argument(
        "--compose-file", type=Path, action="append", default=[], help="extra compose file"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("scenarios", help="list the incident catalog")
    up = sub.add_parser("up", help="start the target with the lab overlay")
    up.add_argument("--no-build", action="store_true")
    down = sub.add_parser("down", help="stop the target")
    down.add_argument("--volumes", action="store_true")
    inject = sub.add_parser("inject", help="inject a scenario (id or part of its title)")
    inject.add_argument("scenario")
    sub.add_parser("reset", help="undo the active scenario")
    sub.add_parser("status", help="show the active scenario")

    check = sub.add_parser("leakcheck", help="scan the target repo and telemetry for leaks")
    check.add_argument("--ref", default="HEAD", help="git ref of the target to scan")
    check.add_argument("--repo-only", action="store_true", help="skip live telemetry")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    catalog = load_catalog()
    stack = Stack(target_dir=args.target.resolve(), extra_files=args.compose_file)
    injector = Injector(stack, Toxiproxy())

    match args.command:
        case "scenarios":
            for s in sorted(catalog.values(), key=lambda s: (s.tier, s.title)):
                trigger = s.ready_when.alert if s.ready_when else "-"
                print(f"{s.id}  {s.tier:<7}  {s.title:<32}  {trigger}")
        case "up":
            stack.up(build=not args.no_build)
        case "down":
            stack.down(volumes=args.volumes)
        case "inject":
            scenario = find(catalog, args.scenario)
            for line in injector.inject(scenario):
                print(line)
            print(f"injected {scenario.id} ({scenario.title})")
        case "reset":
            for line in injector.reset():
                print(line)
        case "status":
            active, injections = injector.active()
            print(
                f"{active} ({catalog[active].title}): {len(injections)} injection(s)"
                if active
                else "nothing injected"
            )
        case "leakcheck":
            matcher = leakcheck.Matcher.load(catalog.values())
            findings = leakcheck.scan_repo(stack.target_dir, args.ref, matcher)
            if not args.repo_only:
                findings += leakcheck.scan_telemetry(leakcheck.Backends(), matcher)
            for f in findings:
                print(f"LEAK [{f.source}] {f.location}: {f.term!r} in {f.excerpt!r}")
            scope = "repo" if args.repo_only else "repo and telemetry"
            print(f"{len(findings)} leak(s) found in {scope} of {stack.target_dir.name}@{args.ref}")
            return 1 if findings else 0
        case _:
            raise AssertionError(args.command)
    return 0


if __name__ == "__main__":
    sys.exit(main())
