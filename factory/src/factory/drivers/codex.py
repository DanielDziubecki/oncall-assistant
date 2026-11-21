"""Codex driver: `codex exec` with JSONL events.

Flags, checked against `codex exec --help`:
- `--sandbox read-only`: commands the model runs may read files, not write them.
- `--ephemeral`: the run leaves no session files.
- `--disable hooks`: the factory's own hooks can't trigger themselves.
- `--skip-git-repo-check`: runs also work in a copy of the project without `.git`.
- `--output-last-message FILE`: the final answer, read from a file instead of from events.
- `-`: the prompt comes from stdin.

The answer text comes from the file, a documented flag. The events only add the session id
and token counts, and lines we don't recognize are skipped, so a change in the event format
loses those numbers, never the answer.
"""

from pathlib import Path

from pydantic import BaseModel, ConfigDict, ValidationError

from factory.config import ModelChoice
from factory.drivers.base import HarnessError, Reply

LAST_MESSAGE_FILE = "last-message.txt"


class _Usage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0


class _Error(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: str = ""


class _Event(BaseModel):
    """One JSONL line from `codex exec --json`, reduced to the fields we use."""

    model_config = ConfigDict(extra="ignore")

    type: str = ""
    thread_id: str = ""
    usage: _Usage | None = None
    message: str = ""
    error: _Error | None = None


class CodexDriver:
    name = "codex"
    executable = "codex"

    def command(self, choice: ModelChoice, scratch: Path) -> list[str]:
        argv = [
            self.executable,
            "exec",
            "--json",
            "--sandbox",
            "read-only",
            "--ephemeral",
            "--skip-git-repo-check",
            "--disable",
            "hooks",
            "--output-last-message",
            str(scratch / LAST_MESSAGE_FILE),
        ]
        if choice.model:
            argv += ["--model", choice.model]
        if choice.effort:
            argv += ["-c", f'model_reasoning_effort="{choice.effort}"']
        argv.append("-")
        return argv

    def parse(self, stdout: str, scratch: Path) -> Reply:
        session_id = ""
        usage: _Usage | None = None
        errors: list[str] = []
        for line in stdout.splitlines():
            try:
                event = _Event.model_validate_json(line)
            except ValidationError:
                continue
            if event.type == "thread.started" and event.thread_id:
                session_id = event.thread_id
            elif event.type == "turn.completed" and event.usage:
                usage = event.usage
            elif event.type in {"error", "turn.failed"}:
                errors.append(event.message or (event.error.message if event.error else ""))

        last_message = scratch / LAST_MESSAGE_FILE
        text = last_message.read_text().strip() if last_message.exists() else ""
        if not text:
            reason = next((e for e in reversed(errors) if e), "no error was reported")
            raise HarnessError(f"codex finished without a final message: {reason}")

        return Reply(
            text=text,
            session_id=session_id,
            input_tokens=usage.input_tokens if usage else None,
            cached_input_tokens=usage.cached_input_tokens if usage else None,
            output_tokens=usage.output_tokens if usage else None,
        )
