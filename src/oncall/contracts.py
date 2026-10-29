"""JSON Schemas of the agent's contracts, committed under `schemas/` so changes show up in review.

Regenerate with `make schemas`; a unit test fails when the committed files are stale.
"""

import json
import sys
from pathlib import Path
from typing import Any

from oncall.agent.diagnosis import Diagnosis
from oncall.agent.hypotheses import Hypothesis
from oncall.capabilities.registry import CAPABILITIES

DEFAULT_DIR = Path(__file__).resolve().parents[2] / "schemas"


def json_schemas() -> dict[str, dict[str, Any]]:
    """Map a relative file path to its JSON Schema."""
    schemas: dict[str, dict[str, Any]] = {
        "diagnosis.json": Diagnosis.model_json_schema(),
        "hypothesis.json": Hypothesis.model_json_schema(),
    }
    for name, spec in CAPABILITIES.items():
        schemas[f"capabilities/{name}.input.json"] = spec.input.model_json_schema()
        schemas[f"capabilities/{name}.output.json"] = spec.output.model_json_schema()
    return schemas


def render(schema: dict[str, Any]) -> str:
    return json.dumps(schema, indent=2, sort_keys=True) + "\n"


def write(directory: Path) -> None:
    for relative, schema in json_schemas().items():
        path = directory / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render(schema))


if __name__ == "__main__":
    write(Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DIR)
