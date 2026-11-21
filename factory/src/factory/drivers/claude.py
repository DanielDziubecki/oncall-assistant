"""Claude Code driver: `claude -p` with JSON output.

Flags, checked against `claude --help`:
- `--tools ""`: no built-in tools, so a run answers from its prompt alone.
- `--safe-mode`: no CLAUDE.md, skills, hooks, plugins or MCP servers. Factory jobs get their
  context only from the prompt, and the factory's own hooks can't trigger themselves.
  The login still works, so runs use your subscription.
- `--no-session-persistence`: the run leaves no session on disk.
"""

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from factory.config import ModelChoice
from factory.drivers.base import HarnessError, Reply


class _Usage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    input_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0
    output_tokens: int = 0


class _Result(BaseModel):
    """The fields we read from `claude -p --output-format json`; the rest are ignored."""

    model_config = ConfigDict(extra="ignore")

    subtype: str
    is_error: bool
    result: str = ""
    session_id: str = ""
    total_cost_usd: float | None = None
    usage: _Usage | None = None
    usage_by_model: dict[str, object] = Field(default_factory=dict, alias="modelUsage")


class ClaudeDriver:
    name = "claude"
    executable = "claude"

    def command(self, choice: ModelChoice, scratch: Path) -> list[str]:
        argv = [
            self.executable,
            "-p",
            "--output-format",
            "json",
            "--tools",
            "",
            "--safe-mode",
            "--no-session-persistence",
        ]
        if choice.model:
            argv += ["--model", choice.model]
        if choice.effort:
            argv += ["--effort", choice.effort]
        return argv

    def parse(self, stdout: str, scratch: Path) -> Reply:
        try:
            result = _Result.model_validate_json(stdout)
        except ValidationError as exc:
            raise HarnessError(f"claude printed an unexpected result: {stdout[:300]!r}") from exc
        if result.is_error or result.subtype != "success":
            reason = result.result[:300]
            raise HarnessError(f"claude reported an error ({result.subtype}): {reason}")

        usage = result.usage
        # Claude counts cache reads and writes apart from `input_tokens`; add them back.
        input_tokens = (
            usage.input_tokens + usage.cache_read_input_tokens + usage.cache_creation_input_tokens
            if usage
            else None
        )
        return Reply(
            text=result.result,
            model=next(iter(result.usage_by_model), ""),
            session_id=result.session_id,
            cost_usd=result.total_cost_usd,
            input_tokens=input_tokens,
            cached_input_tokens=usage.cache_read_input_tokens if usage else None,
            output_tokens=usage.output_tokens if usage else None,
        )
