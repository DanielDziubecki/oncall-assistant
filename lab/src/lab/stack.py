"""The target system as the lab runs it: its compose files plus the lab overlay."""

import os
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import yaml

LAB_DIR = Path(__file__).resolve().parents[2]
STATE_DIR = LAB_DIR / ".state"

Runner = Callable[[Sequence[str], dict[str, str]], str]


def run_command(args: Sequence[str], env: dict[str, str]) -> str:
    result = subprocess.run(
        list(args), env={**os.environ, **env}, check=True, capture_output=True, text=True
    )
    return result.stdout


@dataclass
class Stack:
    """Compose project for the target (`target_dir`) with observability stack `stack`."""

    target_dir: Path
    stack: str = "a"
    extra_files: list[Path] = field(default_factory=list[Path])
    runner: Runner = run_command
    state_dir: Path = STATE_DIR

    @property
    def override_file(self) -> Path:
        """Generated compose file holding the settings injections currently applied."""
        return self.state_dir / "settings.override.yml"

    def compose_files(self) -> list[Path]:
        files = [
            self.target_dir / "compose.yaml",
            self.target_dir / "observability" / f"stack-{self.stack}" / "compose.yaml",
            LAB_DIR / "compose" / "overlay.lab.yml",
            *self.extra_files,
        ]
        if self.override_file.exists():
            files.append(self.override_file)
        return files

    def compose(self, *args: str) -> str:
        cmd = ["docker", "compose", "--project-directory", str(self.target_dir)]
        for f in self.compose_files():
            cmd += ["-f", str(f)]
        return self.runner([*cmd, *args], {"LAB_DIR": str(LAB_DIR)})

    def docker(self, *args: str) -> str:
        return self.runner(["docker", *args], {})

    def up(self, build: bool = True) -> None:
        self.compose("up", "-d", "--build" if build else "--no-build")

    def down(self, volumes: bool = False) -> None:
        self.compose("down", *(["-v"] if volumes else []))

    def recreate(self, *services: str) -> None:
        self.compose("up", "-d", "--no-deps", "--no-build", "--force-recreate", *services)

    # Settings overrides -------------------------------------------------------------

    def settings_overrides(self) -> dict[str, dict[str, str]]:
        if not self.override_file.exists():
            return {}
        data = cast(dict[str, Any], yaml.safe_load(self.override_file.read_text()) or {})
        services = cast(dict[str, dict[str, dict[str, str]]], data.get("services", {}))
        return {name: dict(spec.get("environment", {})) for name, spec in services.items()}

    def write_settings_overrides(self, overrides: dict[str, dict[str, str]]) -> None:
        if not overrides:
            self.override_file.unlink(missing_ok=True)
            return
        self.state_dir.mkdir(parents=True, exist_ok=True)
        doc = {"services": {name: {"environment": env} for name, env in overrides.items()}}
        self.override_file.write_text(yaml.safe_dump(doc, sort_keys=True))
