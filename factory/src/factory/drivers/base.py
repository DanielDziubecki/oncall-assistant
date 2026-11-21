"""What every harness driver provides, and the reply shape all of them return.

A driver is the only code that knows a vendor's command line. Everything else in the
factory sees a `Reply`, so adding a harness means writing one driver.
"""

from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from factory.config import ModelChoice


class HarnessError(RuntimeError):
    """The harness gave no usable answer: missing, logged out, failed or too slow."""


class Reply(BaseModel):
    """What a driver reads from one headless run.

    Token counts mean the same for every harness: `input_tokens` counts all input,
    including the part read from the cache, and `cached_input_tokens` counts that part.
    Vendors count differently, so each driver converts. `cost_usd` is what the harness
    reports; on a subscription it is an estimate at API prices, not a charge.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str
    model: str = ""
    session_id: str = ""
    cost_usd: float | None = Field(default=None, ge=0)
    input_tokens: int | None = Field(default=None, ge=0)
    cached_input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)


class Driver(Protocol):
    """Runs one harness headless: no conversation, read-only, context only from the prompt."""

    name: str
    executable: str

    def command(self, choice: ModelChoice, scratch: Path) -> list[str]:
        """The argv for one run. The prompt goes on stdin, never into argv."""
        ...

    def parse(self, stdout: str, scratch: Path) -> Reply:
        """Read the reply from the run's stdout and any files it wrote to `scratch`."""
        ...
