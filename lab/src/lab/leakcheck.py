"""Leak check: nothing the agent can see may hint at how incidents are injected.

Sources scanned:
- the target repository at a git ref: every text file, plus every commit message and patch
  in that ref's history (what a clone of the branch shows);
- live telemetry: Prometheus metric and label names/values, Loki labels and recent log
  lines, Tempo tags and their values, and active alerts in Alertmanager.
"""

import io
import re
import subprocess
import tarfile
import time
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import yaml

from lab.scenario import Scenario

DENYLIST_FILE = Path(__file__).resolve().parents[2] / "leakcheck" / "denylist.yml"


@dataclass(frozen=True)
class Finding:
    source: str
    location: str
    term: str
    excerpt: str


@dataclass(frozen=True)
class Matcher:
    patterns: list[re.Pattern[str]]
    allow: list[re.Pattern[str]]

    @classmethod
    def load(cls, catalog: Iterable[Scenario] = (), path: Path = DENYLIST_FILE) -> "Matcher":
        config: dict[str, Any] = yaml.safe_load(path.read_text())
        raw: list[str] = list(config["patterns"])
        for scenario in catalog:
            raw += [re.escape(scenario.id), re.escape(scenario.canary)]
        return cls(
            patterns=[re.compile(p, re.IGNORECASE) for p in raw],
            allow=[re.compile(a["pattern"]) for a in config.get("allow", [])],
        )

    def scan(self, source: str, location: str, text: str) -> list[Finding]:
        findings: list[Finding] = []
        for line in text.splitlines():
            for pattern in self.patterns:
                match = pattern.search(line)
                if match and not any(a.search(line) for a in self.allow):
                    findings.append(Finding(source, location, match.group(0), line.strip()[:160]))
        return findings


# Repository ------------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> bytes:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True).stdout


def repo_files(repo: Path, ref: str) -> Iterator[tuple[str, str]]:
    """(path, text) for every non-binary file at `ref`."""
    with tarfile.open(fileobj=io.BytesIO(_git(repo, "archive", "--format=tar", ref))) as archive:
        for member in archive.getmembers():
            if not member.isfile():
                continue
            data = archive.extractfile(member)
            content = data.read() if data else b""
            if b"\0" not in content[:8000]:
                yield member.name, content.decode("utf-8", errors="replace")


def repo_history(repo: Path, ref: str) -> Iterator[tuple[str, str]]:
    """(commit, message and patch) for every commit reachable from `ref`."""
    log = _git(repo, "log", "-p", "--no-color", "--format=%x00%H%n%B", ref).decode(
        "utf-8", errors="replace"
    )
    for chunk in log.split("\0")[1:]:
        commit, _, body = chunk.partition("\n")
        yield commit[:12], body


def scan_repo(repo: Path, ref: str, matcher: Matcher) -> list[Finding]:
    findings: list[Finding] = []
    for path, text in repo_files(repo, ref):
        findings += matcher.scan("repo", f"{ref}:{path}", text)
    for commit, text in repo_history(repo, ref):
        findings += matcher.scan("history", commit, text)
    return findings


# Telemetry -------------------------------------------------------------------------------


@dataclass
class Backends:
    prometheus: str = "http://127.0.0.1:9090"
    loki: str = "http://127.0.0.1:3100"
    tempo: str = "http://127.0.0.1:3200"
    alertmanager: str = "http://127.0.0.1:9093"


def telemetry_texts(
    backends: Backends, client: httpx.Client, log_window_s: int = 1800
) -> Iterator[tuple[str, str, str]]:
    """(source, location, text) for everything the agent could read from the backends."""

    def get(url: str, params: dict[str, str] | None = None) -> Any:
        resp = client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()

    for name in get(f"{backends.prometheus}/api/v1/labels")["data"]:
        values = get(f"{backends.prometheus}/api/v1/label/{name}/values")["data"]
        yield "prometheus", f"label {name}", "\n".join([name, *values])

    for name in get(f"{backends.loki}/loki/api/v1/labels").get("data", []):
        values = get(f"{backends.loki}/loki/api/v1/label/{name}/values").get("data", [])
        yield "loki", f"label {name}", "\n".join([name, *values])
    now_ns = time.time_ns()
    logs = get(
        f"{backends.loki}/loki/api/v1/query_range",
        {
            "query": '{service_name=~".+"}',
            "start": str(now_ns - log_window_s * 1_000_000_000),
            "end": str(now_ns),
            "limit": "5000",
        },
    )
    for stream in logs.get("data", {}).get("result", []):
        service = stream["stream"].get("service_name", "?")
        yield "loki", f"logs {service}", "\n".join(line for _, line in stream["values"])

    tags = get(f"{backends.tempo}/api/v2/search/tags")
    for scope in tags.get("scopes", []):
        for tag in scope.get("tags", []):
            key = f"{scope['name']}.{tag}" if scope["name"] != "intrinsic" else tag
            values = get(f"{backends.tempo}/api/v2/search/tag/{key}/values").get("tagValues", [])
            yield "tempo", f"tag {key}", "\n".join([tag, *(str(v.get("value")) for v in values)])

    for alert in get(f"{backends.alertmanager}/api/v2/alerts"):
        text = "\n".join(
            f"{k}={v}" for d in (alert["labels"], alert["annotations"]) for k, v in d.items()
        )
        yield "alertmanager", alert["labels"].get("alertname", "?"), text


def scan_telemetry(
    backends: Backends, matcher: Matcher, client: httpx.Client | None = None
) -> list[Finding]:
    http = client or httpx.Client(timeout=30)
    findings: list[Finding] = []
    for source, location, text in telemetry_texts(backends, http):
        findings += matcher.scan(source, location, text)
    return findings
