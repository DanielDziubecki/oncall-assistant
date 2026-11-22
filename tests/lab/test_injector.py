import json
from collections.abc import Sequence
from pathlib import Path

import httpx
import pytest
from lab.injector import Injector
from lab.scenario import Scenario
from lab.stack import Stack
from lab.toxiproxy import Toxiproxy


class Recorder:
    """Stands in for subprocess: records commands, answers `docker ps` with paused containers."""

    def __init__(self, paused: Sequence[str] = ()) -> None:
        self.commands: list[list[str]] = []
        self.paused = list(paused)

    def __call__(self, args: Sequence[str], env: dict[str, str]) -> str:
        self.commands.append(list(args))
        if list(args[:2]) == ["docker", "ps"]:
            return "\n".join(self.paused)
        return ""

    def docker(self) -> list[list[str]]:
        return [c[1:] for c in self.commands if c[0] == "docker" and c[1] != "compose"]

    def compose_tails(self) -> list[list[str]]:
        tails: list[list[str]] = []
        for c in self.commands:
            if c[:2] == ["docker", "compose"]:
                tails.append(c[c.index("up") :] if "up" in c else c[-2:])
        return tails


class FakeToxiproxy:
    def __init__(self) -> None:
        self.requests: list[tuple[str, str, object]] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else None
        self.requests.append((request.method, request.url.path, body))
        return httpx.Response(200, json={})


def make(tmp_path: Path, paused: Sequence[str] = ()) -> tuple[Injector, Recorder, FakeToxiproxy]:
    recorder = Recorder(paused)
    fake = FakeToxiproxy()
    client = httpx.Client(base_url="http://toxiproxy", transport=httpx.MockTransport(fake.handler))
    stack = Stack(target_dir=tmp_path / "shopfront", runner=recorder, state_dir=tmp_path / "state")
    return Injector(stack, Toxiproxy(client=client)), recorder, fake


def scenario(*injections: dict[str, object]) -> Scenario:
    return Scenario.model_validate(
        {
            "id": "inc_Test",
            "title": "test",
            "tier": "pr",
            "injection": list(injections),
            "ready_when": {"alert": "SomeAlert"},
            "ground_truth": {"component": "x", "fault_type": "application_error", "mechanism": "m"},
            "canary": "cnry-abc123",
        }
    )


def test_toxic_is_added_through_the_api(tmp_path: Path) -> None:
    injector, _, fake = make(tmp_path)

    injector.inject(
        scenario(
            {
                "kind": "toxic",
                "proxy": "payment",
                "type": "latency",
                "attributes": {"latency": 3000},
            }
        )
    )

    assert fake.requests == [
        (
            "POST",
            "/proxies/payment/toxics",
            {
                "name": "lab-latency",
                "type": "latency",
                "stream": "downstream",
                "toxicity": 1.0,
                "attributes": {"latency": 3000},
            },
        )
    ]


def test_settings_redeploy_the_service_with_an_override(tmp_path: Path) -> None:
    injector, recorder, _ = make(tmp_path)

    injector.inject(scenario({"kind": "settings", "service": "payment", "env": {"MODE": "v2"}}))

    assert injector.stack.settings_overrides() == {"payment": {"MODE": "v2"}}
    assert str(injector.stack.override_file) in recorder.commands[-1]
    assert recorder.compose_tails()[-1] == [
        "up", "-d", "--no-deps", "--no-build", "--force-recreate", "payment",
    ]  # fmt: skip


def test_docker_level_injections(tmp_path: Path) -> None:
    injector, recorder, _ = make(tmp_path)

    injector.inject(
        scenario(
            {"kind": "pause", "container": "valkey"},
            {"kind": "cpu_limit", "container": "fulfillment", "cpus": 0.02},
            {"kind": "netem", "container": "catalog", "loss_percent": 15},
            {"kind": "packet_loss", "container": "shipping", "percent": 15},
            {"kind": "restart", "container": "loadgen"},
        )
    )

    docker = recorder.docker()
    assert ["pause", "valkey"] in docker
    assert ["update", "--cpus", "0.02", "fulfillment"] in docker
    assert ["restart", "loadgen"] in docker
    netem, drop = (c for c in docker if c[0] == "run")
    assert netem[netem.index("--network") + 1] == "container:catalog"
    assert netem[-5:] == ["eth0", "root", "netem", "loss", "15%"]
    assert drop[drop.index("--network") + 1] == "container:shipping"
    assert drop[-9:] == [
        "OUTPUT", "-m", "statistic", "--mode", "random", "--probability", "0.1500", "-j", "DROP",
    ]  # fmt: skip


def test_only_one_scenario_at_a_time(tmp_path: Path) -> None:
    injector, _, _ = make(tmp_path)
    injector.inject(scenario({"kind": "pause", "container": "valkey"}))

    with pytest.raises(RuntimeError, match="still active"):
        injector.inject(scenario({"kind": "pause", "container": "valkey"}))


def test_reset_undoes_everything(tmp_path: Path) -> None:
    injector, recorder, fake = make(tmp_path)
    injector.inject(
        scenario(
            {"kind": "settings", "service": "payment", "env": {"MODE": "v2"}},
            {"kind": "pause", "container": "valkey"},
            {"kind": "cpu_limit", "container": "fulfillment", "cpus": 0.02},
            {"kind": "netem", "container": "catalog", "loss_percent": 15},
        )
    )
    recorder.commands.clear()

    injector.reset()

    assert ("POST", "/reset", None) in fake.requests
    assert ["unpause", "valkey"] in recorder.docker()
    tc_del = next(c for c in recorder.docker() if c[0] == "run")
    assert tc_del[-4:] == ["del", "dev", "eth0", "root"]
    assert recorder.compose_tails()[-1][-2:] == ["fulfillment", "payment"]
    assert not injector.stack.override_file.exists()
    assert injector.active() == (None, [])


def test_reset_unpauses_leftovers_without_state(tmp_path: Path) -> None:
    injector, recorder, _ = make(tmp_path, paused=["valkey"])

    injector.reset()

    assert ["unpause", "valkey"] in recorder.docker()
    assert recorder.compose_tails() == [] or all("up" not in t for t in recorder.compose_tails())


def test_failed_injection_is_rolled_back(tmp_path: Path) -> None:
    injector, recorder, fake = make(tmp_path)

    def fail_on_update(args: Sequence[str], env: dict[str, str]) -> str:
        if "update" in args:
            raise RuntimeError("docker update failed")
        return recorder(args, env)

    injector.stack.runner = fail_on_update
    with pytest.raises(RuntimeError, match="docker update failed"):
        injector.inject(
            scenario(
                {"kind": "pause", "container": "valkey"},
                {"kind": "cpu_limit", "container": "fulfillment", "cpus": 0.02},
            )
        )

    assert ["unpause", "valkey"] in recorder.docker()
    assert ("POST", "/reset", None) in fake.requests
    assert injector.active() == (None, [])
