from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .errors import IRValidationError
from .ir import MechanismProgram, WorldSpec, program_to_dict


def _load_json(path: str | Path, name: str) -> dict[str, Any]:
    source = Path(path)
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise IRValidationError(f"cannot load {name} {source}: {error}") from error
    if not isinstance(value, dict):
        raise IRValidationError(f"{name} root must be an object")
    return value


def load_world(path: str | Path) -> WorldSpec:
    return WorldSpec.from_mapping(_load_json(path, "world"))


def load_program(path: str | Path) -> MechanismProgram:
    return MechanismProgram.from_mapping(_load_json(path, "program"))


def load_state(path: str | Path) -> dict[str, object]:
    return dict(_load_json(path, "state"))


def write_program(path: str | Path, program: MechanismProgram) -> None:
    Path(path).write_text(
        json.dumps(program_to_dict(program), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_state(path: str | Path, state: dict[str, object]) -> None:
    Path(path).write_text(
        json.dumps(state, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
