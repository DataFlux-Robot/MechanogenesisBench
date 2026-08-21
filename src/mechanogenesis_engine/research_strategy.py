from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping

from mechanogenesis_bench.canonical import digest

from .errors import IRValidationError


STRATEGY_SCHEMA_VERSION = "0.1"
PARAMETER_SEMANTICS = (
    "pin_spacing_um",
    "bore_clearance_um",
    "reference_y_um",
)
OBJECTIVE_FIELDS = (
    "robust_worst_case_error_um",
    "weighted_model_error_ppm_um",
    "base_volume_um3",
    "duration_us",
)
_IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,63}$")


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise IRValidationError(f"{field} must be an object")
    return value


def _keys(raw: Mapping[str, Any], expected: set[str], field: str) -> None:
    if set(raw) != expected:
        raise IRValidationError(
            f"{field} fields mismatch; missing={sorted(expected-set(raw))}, "
            f"extra={sorted(set(raw)-expected)}"
        )


def _text(value: Any, field: str, *, limit: int = 2_000) -> str:
    if not isinstance(value, str) or not value.strip():
        raise IRValidationError(f"{field} must be non-empty text")
    if len(value) > limit:
        raise IRValidationError(f"{field} exceeds {limit} characters")
    return value


def _identifier(value: Any, field: str) -> str:
    text = _text(value, field, limit=64)
    if _IDENTIFIER.fullmatch(text) is None:
        raise IRValidationError(f"{field} must be a bounded identifier")
    return text


def _nat(value: Any, field: str, *, positive: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise IRValidationError(f"{field} must be an integer")
    minimum = 1 if positive else 0
    if value < minimum:
        qualifier = "positive" if positive else "nonnegative"
        raise IRValidationError(f"{field} must be {qualifier}")
    return value


def _bounded_positive_list(value: Any, field: str) -> tuple[int, ...]:
    if not isinstance(value, list) or not value:
        raise IRValidationError(f"{field} must be a non-empty list")
    if len(value) > 64:
        raise IRValidationError(f"{field} exceeds 64 candidates")
    result = tuple(
        _nat(item, f"{field}[{index}]", positive=True)
        for index, item in enumerate(value)
    )
    if len(set(result)) != len(result):
        raise IRValidationError(f"{field} must not contain duplicates")
    return result


@dataclass(frozen=True)
class ParameterDomain:
    symbol: str
    semantic: str
    candidates_um: tuple[int, ...]

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any], field: str) -> "ParameterDomain":
        _keys(raw, {"symbol", "semantic", "candidates_um"}, field)
        semantic = _text(raw["semantic"], f"{field}.semantic", limit=64)
        if semantic not in PARAMETER_SEMANTICS:
            raise IRValidationError(
                f"{field}.semantic is outside the trusted fixture fragment"
            )
        return cls(
            symbol=_identifier(raw["symbol"], f"{field}.symbol"),
            semantic=semantic,
            candidates_um=_bounded_positive_list(
                raw["candidates_um"], f"{field}.candidates_um"
            ),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "semantic": self.semantic,
            "candidates_um": list(self.candidates_um),
        }


@dataclass(frozen=True)
class TaskLanguage:
    language_id: str
    semantic_target: str
    topology: str
    parameters: tuple[ParameterDomain, ...]

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any], field: str) -> "TaskLanguage":
        _keys(
            raw,
            {"language_id", "semantic_target", "topology", "parameters"},
            field,
        )
        if raw["semantic_target"] != "canonical_fixture_ir_v0_3":
            raise IRValidationError(
                f"{field}.semantic_target is outside the trusted compiler"
            )
        if raw["topology"] != "two_locator_one_reference":
            raise IRValidationError(f"{field}.topology is outside the trusted compiler")
        parameters_raw = raw["parameters"]
        if not isinstance(parameters_raw, list) or len(parameters_raw) != 3:
            raise IRValidationError(f"{field}.parameters must contain three domains")
        parameters = tuple(
            ParameterDomain.from_mapping(
                _mapping(item, f"{field}.parameters[{index}]"),
                f"{field}.parameters[{index}]",
            )
            for index, item in enumerate(parameters_raw)
        )
        if {item.semantic for item in parameters} != set(PARAMETER_SEMANTICS):
            raise IRValidationError(
                f"{field}.parameters must define each trusted semantic exactly once"
            )
        if len({item.symbol for item in parameters}) != len(parameters):
            raise IRValidationError(f"{field}.parameters contains duplicate symbols")
        return cls(
            language_id=_identifier(raw["language_id"], f"{field}.language_id"),
            semantic_target="canonical_fixture_ir_v0_3",
            topology="two_locator_one_reference",
            parameters=parameters,
        )

    def domain(self, semantic: str) -> tuple[int, ...]:
        for parameter in self.parameters:
            if parameter.semantic == semantic:
                return parameter.candidates_um
        raise IRValidationError(f"task language has no parameter semantic {semantic!r}")

    def to_dict(self) -> dict[str, object]:
        return {
            "language_id": self.language_id,
            "semantic_target": self.semantic_target,
            "topology": self.topology,
            "parameters": [parameter.to_dict() for parameter in self.parameters],
        }


@dataclass(frozen=True)
class WorldHypothesis:
    hypothesis_id: str
    workpiece_span_um: int
    extra_disturbance_um: int
    prior_weight_ppm: int

    @classmethod
    def from_mapping(
        cls, raw: Mapping[str, Any], field: str
    ) -> "WorldHypothesis":
        _keys(
            raw,
            {
                "hypothesis_id",
                "workpiece_span_um",
                "extra_disturbance_um",
                "prior_weight_ppm",
            },
            field,
        )
        span = _nat(raw["workpiece_span_um"], f"{field}.workpiece_span_um", positive=True)
        disturbance = _nat(
            raw["extra_disturbance_um"], f"{field}.extra_disturbance_um"
        )
        if span > 10_000_000 or disturbance > 1_000_000:
            raise IRValidationError(f"{field} exceeds trusted fixed-point bounds")
        return cls(
            hypothesis_id=_identifier(
                raw["hypothesis_id"], f"{field}.hypothesis_id"
            ),
            workpiece_span_um=span,
            extra_disturbance_um=disturbance,
            prior_weight_ppm=_nat(
                raw["prior_weight_ppm"], f"{field}.prior_weight_ppm", positive=True
            ),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "workpiece_span_um": self.workpiece_span_um,
            "extra_disturbance_um": self.extra_disturbance_um,
            "prior_weight_ppm": self.prior_weight_ppm,
        }


@dataclass(frozen=True)
class SearchPolicy:
    mode: str
    base_order: str
    objective_order: tuple[str, ...]
    max_executions: int

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any], field: str) -> "SearchPolicy":
        _keys(raw, {"mode", "base_order", "objective_order", "max_executions"}, field)
        mode = _text(raw["mode"], f"{field}.mode", limit=64)
        if mode not in {"exhaustive_lexicographic", "ordered_first_feasible"}:
            raise IRValidationError(f"{field}.mode is unsupported")
        base_order = _text(raw["base_order"], f"{field}.base_order", limit=64)
        if base_order not in {"smallest_first", "largest_first"}:
            raise IRValidationError(f"{field}.base_order is unsupported")
        objectives = raw["objective_order"]
        if (
            not isinstance(objectives, list)
            or len(objectives) != len(OBJECTIVE_FIELDS)
            or not all(isinstance(item, str) for item in objectives)
            or set(objectives) != set(OBJECTIVE_FIELDS)
        ):
            raise IRValidationError(
                f"{field}.objective_order must be a permutation of "
                f"{list(OBJECTIVE_FIELDS)!r}"
            )
        maximum = _nat(raw["max_executions"], f"{field}.max_executions", positive=True)
        if maximum > 100_000:
            raise IRValidationError(f"{field}.max_executions exceeds trusted limit")
        return cls(
            mode=mode,
            base_order=base_order,
            objective_order=tuple(objectives),
            max_executions=maximum,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "base_order": self.base_order,
            "objective_order": list(self.objective_order),
            "max_executions": self.max_executions,
        }


@dataclass(frozen=True)
class ExperimentPolicy:
    intervention_rule: str
    required_hypotheses: int

    @classmethod
    def from_mapping(
        cls, raw: Mapping[str, Any], field: str
    ) -> "ExperimentPolicy":
        _keys(raw, {"intervention_rule", "required_hypotheses"}, field)
        rule = _text(raw["intervention_rule"], f"{field}.intervention_rule", limit=64)
        if rule != "robust_model_sweep":
            raise IRValidationError(f"{field}.intervention_rule is unsupported")
        return cls(
            intervention_rule=rule,
            required_hypotheses=_nat(
                raw["required_hypotheses"],
                f"{field}.required_hypotheses",
                positive=True,
            ),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "intervention_rule": self.intervention_rule,
            "required_hypotheses": self.required_hypotheses,
        }


@dataclass(frozen=True)
class FixtureResearchStrategy:
    schema_version: str
    strategy_id: str
    research_hypothesis: str
    language: TaskLanguage
    world_hypotheses: tuple[WorldHypothesis, ...]
    search: SearchPolicy
    experiment: ExperimentPolicy

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "FixtureResearchStrategy":
        _keys(
            raw,
            {
                "schema_version",
                "strategy_id",
                "research_hypothesis",
                "language",
                "world_hypotheses",
                "search",
                "experiment",
            },
            "research_strategy",
        )
        if raw["schema_version"] != STRATEGY_SCHEMA_VERSION:
            raise IRValidationError("unsupported research strategy schema version")
        hypotheses_raw = raw["world_hypotheses"]
        if not isinstance(hypotheses_raw, list) or not 1 <= len(hypotheses_raw) <= 32:
            raise IRValidationError(
                "research_strategy.world_hypotheses must contain 1..32 models"
            )
        hypotheses = tuple(
            WorldHypothesis.from_mapping(
                _mapping(item, f"world_hypotheses[{index}]"),
                f"world_hypotheses[{index}]",
            )
            for index, item in enumerate(hypotheses_raw)
        )
        if len({item.hypothesis_id for item in hypotheses}) != len(hypotheses):
            raise IRValidationError("world_hypotheses contains duplicate ids")
        if sum(item.prior_weight_ppm for item in hypotheses) != 1_000_000:
            raise IRValidationError("world hypothesis weights must sum to 1,000,000 ppm")
        experiment = ExperimentPolicy.from_mapping(
            _mapping(raw["experiment"], "research_strategy.experiment"),
            "research_strategy.experiment",
        )
        if experiment.required_hypotheses > len(hypotheses):
            raise IRValidationError(
                "experiment requires more hypotheses than the strategy supplies"
            )
        return cls(
            schema_version=STRATEGY_SCHEMA_VERSION,
            strategy_id=_identifier(raw["strategy_id"], "research_strategy.strategy_id"),
            research_hypothesis=_text(
                raw["research_hypothesis"], "research_strategy.research_hypothesis"
            ),
            language=TaskLanguage.from_mapping(
                _mapping(raw["language"], "research_strategy.language"),
                "research_strategy.language",
            ),
            world_hypotheses=hypotheses,
            search=SearchPolicy.from_mapping(
                _mapping(raw["search"], "research_strategy.search"),
                "research_strategy.search",
            ),
            experiment=experiment,
        )

    @property
    def strategy_hash(self) -> str:
        return digest(self.to_dict())

    def validate_goal_domains(self, goal: Any) -> None:
        allowed = {
            "pin_spacing_um": set(goal.pin_spacing_candidates_um),
            "bore_clearance_um": set(goal.bore_clearance_candidates_um),
            "reference_y_um": set(goal.reference_y_candidates_um),
        }
        for semantic, allowed_values in allowed.items():
            proposed = set(self.language.domain(semantic))
            if not proposed <= allowed_values:
                raise IRValidationError(
                    f"strategy proposes {semantic} outside public intervention access"
                )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "strategy_id": self.strategy_id,
            "research_hypothesis": self.research_hypothesis,
            "language": self.language.to_dict(),
            "world_hypotheses": [item.to_dict() for item in self.world_hypotheses],
            "search": self.search.to_dict(),
            "experiment": self.experiment.to_dict(),
        }
