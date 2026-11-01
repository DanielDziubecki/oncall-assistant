"""Base class for every model that crosses a boundary (LLM, proxy, event log)."""

from pydantic import BaseModel, ConfigDict


class Schema(BaseModel):
    """Immutable and closed: unknown fields are rejected, so a model can't smuggle in extra keys."""

    model_config = ConfigDict(extra="forbid", frozen=True)
