"""Run one prompt through one harness, headless, and return the factory's own result shape."""

import os
import shutil
import subprocess
import tempfile
import time
from collections.abc import Mapping
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from factory.config import ModelChoice
from factory.drivers import Driver, HarnessError


class AskResult(BaseModel):
    """One answer, the same shape whichever harness gave it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    harness: str
    model: str
    text: str
    duration_ms: int
    session_id: str = ""
    cost_usd: float | None = None
    input_tokens: int | None = None
    cached_input_tokens: int | None = None
    output_tokens: int | None = None


def ask(
    driver: Driver,
    prompt: str,
    choice: ModelChoice,
    *,
    cwd: Path,
    timeout_s: float = 300,
    env: Mapping[str, str] | None = None,
) -> AskResult:
    """Send `prompt` on stdin to one headless run and read its answer.

    `env` replaces the environment of the run; tests use it to put fake harnesses on PATH.
    """
    path = (os.environ if env is None else env).get("PATH")
    executable = shutil.which(driver.executable, path=path)
    if executable is None:
        raise HarnessError(
            f"`{driver.executable}` is not installed or not on PATH; see docs/factory/vps-setup.md"
        )

    with tempfile.TemporaryDirectory(prefix="factory-") as tmp:
        scratch = Path(tmp)
        argv = [executable, *driver.command(choice, scratch)[1:]]
        started = time.monotonic()
        try:
            run = subprocess.run(
                argv,
                input=prompt,
                capture_output=True,
                text=True,
                cwd=cwd,
                timeout=timeout_s,
                env=None if env is None else dict(env),
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise HarnessError(f"{driver.name} gave no answer within {timeout_s:g} s") from exc
        duration_ms = round((time.monotonic() - started) * 1000)
        if run.returncode != 0:
            output = _tail(run.stderr or run.stdout)
            raise HarnessError(f"{driver.name} exited with code {run.returncode}: {output}")
        reply = driver.parse(run.stdout, scratch)

    return AskResult(
        harness=driver.name,
        model=reply.model or choice.model or "default",
        text=reply.text,
        duration_ms=duration_ms,
        session_id=reply.session_id,
        cost_usd=reply.cost_usd,
        input_tokens=reply.input_tokens,
        cached_input_tokens=reply.cached_input_tokens,
        output_tokens=reply.output_tokens,
    )


def _tail(output: str, limit: int = 400) -> str:
    text = " ".join(output.split())
    return text if len(text) <= limit else "…" + text[-limit:]
