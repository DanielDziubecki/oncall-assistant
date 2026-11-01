import subprocess
from pathlib import Path
from typing import Any

import httpx
import pytest
from lab.scenario import load_catalog

from lab.leakcheck import Backends, Matcher, scan_repo, scan_telemetry

CATALOG = load_catalog()
MATCHER = Matcher.load(CATALOG.values())


def git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *args],
        check=True,
        capture_output=True,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    git(tmp_path, "init", "-q", "-b", "main")
    (tmp_path / "app.py").write_text("print('hello')\n")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-q", "-m", "first")
    return tmp_path


@pytest.mark.parametrize(
    "line",
    [
        "TOXIPROXY_URL=http://x",
        "from openfeature import api",
        "ld = FlagdProvider()",
        "# chaos testing hook",
        "tc qdisc add dev eth0 root netem loss 5%",
        "see inc_Ab12 for details",
    ],
)
def test_denylisted_terms_are_found(line: str) -> None:
    assert MATCHER.scan("repo", "f", line)


def test_catalog_ids_and_canaries_are_found() -> None:
    scenario = next(iter(CATALOG.values()))

    assert MATCHER.scan("loki", "x", f"order note {scenario.canary}")
    assert MATCHER.scan("loki", "x", f"run {scenario.id}")


def test_ordinary_text_passes() -> None:
    text = "payment charge failed: invalid token\nconnection refused\nfailure rate 30%"

    assert MATCHER.scan("repo", "f", text) == []


def test_allowlisted_line_passes() -> None:
    assert MATCHER.scan("repo", "f", "    propagate.inject(headers, setter=_HeaderSetter())") == []
    assert MATCHER.scan("repo", "f", "self.inject(headers)")


def test_clean_repo_passes(repo: Path) -> None:
    assert scan_repo(repo, "HEAD", MATCHER) == []


def test_leak_in_files_is_found(repo: Path) -> None:
    (repo / "compose.yaml").write_text("services:\n  toxiproxy:\n    image: x\n")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "add proxy")

    findings = scan_repo(repo, "HEAD", MATCHER)

    assert any(f.source == "repo" and f.location == "HEAD:compose.yaml" for f in findings)


def test_leak_removed_from_files_is_still_found_in_history(repo: Path) -> None:
    (repo / "notes.md").write_text("use flagd to turn faults on\n")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "notes")
    (repo / "notes.md").unlink()
    git(repo, "commit", "-q", "-am", "remove notes")

    findings = scan_repo(repo, "HEAD", MATCHER)

    # Found in the commit that added the line and the one that removed it, never in files.
    assert {f.source for f in findings} == {"history"}


def test_other_branches_are_not_scanned_unless_asked(repo: Path) -> None:
    git(repo, "checkout", "-q", "-b", "old")
    (repo / "x.txt").write_text("chaos\n")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "old work")
    git(repo, "checkout", "-q", "main")

    assert scan_repo(repo, "main", MATCHER) == []
    assert scan_repo(repo, "old", MATCHER)


def fake_backends(container_names: list[str], log_line: str) -> httpx.Client:
    responses: dict[str, Any] = {
        "/api/v1/labels": {"data": ["__name__", "container_name"]},
        "/api/v1/label/__name__/values": {"data": ["container_cpu_utilization_ratio"]},
        "/api/v1/label/container_name/values": {"data": container_names},
        "/loki/api/v1/labels": {"data": ["service_name"]},
        "/loki/api/v1/label/service_name/values": {"data": ["checkout"]},
        "/loki/api/v1/query_range": {
            "data": {
                "result": [{"stream": {"service_name": "checkout"}, "values": [["1", log_line]]}]
            }
        },
        "/api/v2/search/tags": {"scopes": [{"name": "resource", "tags": ["service.name"]}]},
        "/api/v2/search/tag/resource.service.name/values": {"tagValues": [{"value": "checkout"}]},
        "/api/v2/alerts": [{"labels": {"alertname": "CheckoutErrorRateHigh"}, "annotations": {}}],
    }
    return httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json=responses[r.url.path]))
    )


def test_clean_telemetry_passes() -> None:
    client = fake_backends(["checkout", "payment"], "order placed")

    assert scan_telemetry(Backends(), MATCHER, client) == []


def test_lab_container_in_metrics_is_a_leak() -> None:
    client = fake_backends(["checkout", "lab-edge-proxy"], "order placed")

    findings = scan_telemetry(Backends(), MATCHER, client)

    assert [(f.source, f.location) for f in findings] == [("prometheus", "label container_name")]


def test_leaking_log_line_is_found() -> None:
    client = fake_backends(["checkout"], "upstream payment-real:8000 refused")

    findings = scan_telemetry(Backends(), MATCHER, client)

    assert [(f.source, f.location) for f in findings] == [("loki", "logs checkout")]
