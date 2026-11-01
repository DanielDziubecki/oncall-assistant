"""Applies a scenario's injections to the running stack, and undoes them."""

import contextlib
import json
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from pydantic import TypeAdapter

from lab.scenario import CpuLimit, Injection, Netem, Pause, Restart, Scenario, Settings, Toxic
from lab.stack import Stack
from lab.toxiproxy import Toxiproxy

NETEM_IMAGE = "docker.io/nicolaka/netshoot:v0.14"
_injections: TypeAdapter[list[Injection]] = TypeAdapter(list[Injection])


@dataclass
class Injector:
    stack: Stack
    toxiproxy: Toxiproxy
    netem_image: str = NETEM_IMAGE

    @property
    def _state_file(self) -> Path:
        return self.stack.state_dir / "active.json"

    def active(self) -> tuple[str | None, list[Injection]]:
        if not self._state_file.exists():
            return None, []
        data = json.loads(self._state_file.read_text())
        return data["scenario"], _injections.validate_python(data["injections"])

    def _save(self, scenario_id: str | None, injections: list[Injection]) -> None:
        if scenario_id is None:
            self._state_file.unlink(missing_ok=True)
            return
        self.stack.state_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "scenario": scenario_id,
            "injections": _injections.dump_python(injections, mode="json"),
        }
        self._state_file.write_text(json.dumps(payload, indent=2))

    # Applying ------------------------------------------------------------------------

    def inject(self, scenario: Scenario) -> list[str]:
        current, _ = self.active()
        if current is not None:
            raise RuntimeError(f"scenario {current} is still active; run `lab reset` first")
        self._save(scenario.id, list(scenario.injection))
        return [self._apply(injection) for injection in scenario.injection]

    def _apply(self, injection: Injection) -> str:
        match injection:
            case Toxic():
                self.toxiproxy.add_toxic(
                    injection.proxy,
                    f"lab-{injection.type}",
                    injection.type,
                    injection.stream,
                    injection.attributes,
                )
                return f"toxic {injection.type} on proxy {injection.proxy}"
            case Settings():
                overrides = self.stack.settings_overrides()
                overrides.setdefault(injection.service, {}).update(injection.env)
                self.stack.write_settings_overrides(overrides)
                self.stack.recreate(injection.service)
                return f"redeployed {injection.service} with {sorted(injection.env)}"
            case Pause():
                self.stack.docker("pause", injection.container)
                return f"paused {injection.container}"
            case CpuLimit():
                self.stack.docker("update", "--cpus", str(injection.cpus), injection.container)
                return f"limited {injection.container} to {injection.cpus} CPUs"
            case Netem():
                self._tc(injection.container, "replace", *_netem_args(injection))
                return f"netem {' '.join(_netem_args(injection))} on {injection.container}"
            case Restart():
                self.stack.docker("restart", injection.container)
                return f"restarted {injection.container}"

    def _tc(self, container: str, action: str, *args: str) -> None:
        self.stack.docker(
            "run", "--rm", "--network", f"container:{container}", "--cap-add", "NET_ADMIN",
            self.netem_image, "tc", "qdisc", action, "dev", "eth0", "root", *args,
        )  # fmt: skip

    # Undoing -------------------------------------------------------------------------

    def reset(self) -> list[str]:
        """Undo the active scenario. Also clears toxics and pauses left by a crashed run."""
        _, injections = self.active()
        done: list[str] = []

        self.toxiproxy.reset()
        done.append("removed all toxics")

        recreate: set[str] = set(self.stack.settings_overrides())
        self.stack.write_settings_overrides({})
        for injection in injections:
            match injection:
                case Pause():
                    self._try(lambda c=injection.container: self.stack.docker("unpause", c))
                    done.append(f"unpaused {injection.container}")
                case CpuLimit():
                    recreate.add(injection.container)
                case Netem():
                    self._try(lambda c=injection.container: self._tc(c, "del"))
                    done.append(f"removed netem from {injection.container}")
                case Toxic() | Settings() | Restart():
                    pass
        for container in self._paused_containers():
            self.stack.docker("unpause", container)
            done.append(f"unpaused leftover {container}")
        if recreate:
            self.stack.recreate(*sorted(recreate))
            done.append(f"recreated {', '.join(sorted(recreate))} with default settings")

        self._save(None, [])
        return done

    def _paused_containers(self) -> list[str]:
        project = self.stack.target_dir.name
        out = self.stack.docker(
            "ps", "--filter", "status=paused",
            "--filter", f"label=com.docker.compose.project={project}",
            "--format", "{{.Names}}",
        )  # fmt: skip
        return [line for line in out.splitlines() if line.strip()]

    @staticmethod
    def _try(action: Callable[[], object]) -> None:
        """Run an undo step that may already have been undone."""
        with contextlib.suppress(subprocess.CalledProcessError):
            action()


def _netem_args(netem: Netem) -> list[str]:
    args = ["netem"]
    if netem.delay_ms:
        args += ["delay", f"{netem.delay_ms}ms"]
    if netem.loss_percent:
        args += ["loss", f"{netem.loss_percent:g}%"]
    return args
