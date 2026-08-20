from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from typing import Any, Mapping

from .errors import SchemaError


class Track(str, Enum):
    FIXED_ENGINE = "fixed_engine"
    OPEN_SYSTEM = "open_system"
    RECURSIVE_LEARNER = "recursive_learner"


class GuidanceLevel(str, Enum):
    G1 = "G1"
    G2 = "G2"
    G3 = "G3"
    G4 = "G4"
    G5 = "G5"


class EvidenceTier(str, Enum):
    CONFORMANCE = "conformance"
    SIMULATION = "simulation"
    CROSS_VALIDATED = "cross_validated_simulation"
    HARDWARE_IN_LOOP = "hardware_in_loop"
    HARDWARE = "hardware"
    RECURSIVE_PHYSICAL = "recursive_physical"

    @property
    def rank(self) -> int:
        return list(EvidenceTier).index(self)


def require_mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise SchemaError(f"{field} must be an object")
    return value


def require_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SchemaError(f"{field} must be non-empty text")
    return value


def require_number(value: Any, field: str, *, nonnegative: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SchemaError(f"{field} must be numeric")
    numeric = float(value)
    if not math.isfinite(numeric):
        raise SchemaError(f"{field} must be finite")
    if nonnegative and numeric < 0:
        raise SchemaError(f"{field} must be nonnegative")
    return numeric


@dataclass(frozen=True)
class ResourceVector:
    wall_time_s: float
    monetary_cost_usd: float
    tokens: int
    energy_j: float
    material_kg: float
    human_intervention_s: float
    attempts: int

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any], field: str) -> "ResourceVector":
        values = {
            "wall_time_s": require_number(raw.get("wall_time_s"), f"{field}.wall_time_s", nonnegative=True),
            "monetary_cost_usd": require_number(raw.get("monetary_cost_usd"), f"{field}.monetary_cost_usd", nonnegative=True),
            "tokens": raw.get("tokens"),
            "energy_j": require_number(raw.get("energy_j"), f"{field}.energy_j", nonnegative=True),
            "material_kg": require_number(raw.get("material_kg"), f"{field}.material_kg", nonnegative=True),
            "human_intervention_s": require_number(raw.get("human_intervention_s"), f"{field}.human_intervention_s", nonnegative=True),
            "attempts": raw.get("attempts"),
        }
        for name in ("tokens", "attempts"):
            value = values[name]
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise SchemaError(f"{field}.{name} must be a nonnegative integer")
        return cls(**values)

    def within(self, limit: "ResourceVector") -> bool:
        return all(
            getattr(self, field) <= getattr(limit, field)
            for field in self.__dataclass_fields__
        )


@dataclass(frozen=True)
class TaskManifest:
    schema_version: str
    task_id: str
    title: str
    track: Track
    evidence_ceiling: EvidenceTier
    guidance_levels: tuple[GuidanceLevel, ...]
    generations: int
    min_promotions: int
    min_robustness_pass_rate: float
    evaluator_command: tuple[str, ...]
    budget: ResourceVector

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "TaskManifest":
        schema_version = require_text(raw.get("schema_version"), "schema_version")
        if schema_version != "0.1":
            raise SchemaError(f"unsupported task schema version {schema_version!r}")
        task_id = require_text(raw.get("task_id"), "task_id")
        if any(character not in "abcdefghijklmnopqrstuvwxyz0123456789._-" for character in task_id):
            raise SchemaError("task_id contains unsupported characters")
        try:
            track = Track(require_text(raw.get("track"), "track"))
            ceiling = EvidenceTier(require_text(raw.get("evidence_ceiling"), "evidence_ceiling"))
        except ValueError as error:
            raise SchemaError(str(error)) from error
        raw_levels = raw.get("guidance_levels")
        if not isinstance(raw_levels, list) or not raw_levels:
            raise SchemaError("guidance_levels must be a non-empty list")
        try:
            levels = tuple(GuidanceLevel(item) for item in raw_levels)
        except ValueError as error:
            raise SchemaError(str(error)) from error
        if len(levels) != len(set(levels)):
            raise SchemaError("guidance_levels must be unique")
        generations = raw.get("generations")
        min_promotions = raw.get("min_promotions")
        if isinstance(generations, bool) or not isinstance(generations, int) or generations < 1:
            raise SchemaError("generations must be a positive integer")
        if isinstance(min_promotions, bool) or not isinstance(min_promotions, int):
            raise SchemaError("min_promotions must be an integer")
        if not 0 <= min_promotions <= generations:
            raise SchemaError("min_promotions must lie in [0, generations]")
        min_robustness = require_number(
            raw.get("min_robustness_pass_rate"),
            "min_robustness_pass_rate",
            nonnegative=True,
        )
        if min_robustness > 1:
            raise SchemaError("min_robustness_pass_rate must be <= 1")
        evaluator = require_mapping(raw.get("evaluator"), "evaluator")
        command = evaluator.get("command")
        if not isinstance(command, list) or not command:
            raise SchemaError("evaluator.command must be a non-empty list")
        evaluator_command = tuple(require_text(item, "evaluator.command item") for item in command)
        budget = ResourceVector.from_mapping(require_mapping(raw.get("budget"), "budget"), "budget")
        return cls(
            schema_version=schema_version,
            task_id=task_id,
            title=require_text(raw.get("title"), "title"),
            track=track,
            evidence_ceiling=ceiling,
            guidance_levels=levels,
            generations=generations,
            min_promotions=min_promotions,
            min_robustness_pass_rate=min_robustness,
            evaluator_command=evaluator_command,
            budget=budget,
        )
