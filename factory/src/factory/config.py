"""Which model each harness uses for each size of job.

Jobs ask for a size, not a model: `small` for fast helper work, `large` for hard work.
`factory/models.toml` maps each size to a model per harness, so switching models never
touches a job's definition.
"""

import tomllib
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, TypeAdapter

DEFAULT_MODELS_FILE = Path(__file__).resolve().parents[2] / "models.toml"


class Size(StrEnum):
    SMALL = "small"
    LARGE = "large"


class ModelChoice(BaseModel):
    """A model and an effort level for one harness. Empty means the harness's own default."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    model: str = ""
    effort: str = ""


class HarnessModels(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    small: ModelChoice = ModelChoice()
    large: ModelChoice = ModelChoice()

    def for_size(self, size: Size) -> ModelChoice:
        return self.small if size is Size.SMALL else self.large


_MODELS_FILE = TypeAdapter(dict[str, HarnessModels])


def load_models(path: Path = DEFAULT_MODELS_FILE) -> dict[str, HarnessModels]:
    """Read the models file: one table per harness and size, such as `[claude.small]`."""
    return _MODELS_FILE.validate_python(tomllib.loads(path.read_text()))
