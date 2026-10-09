from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping, Sequence

from .canonical import digest
from .generalization import (
    AcquisitionCandidate,
    FactorizedCase,
    GENERALIZATION_AXES,
    GroundedSeparatingChoice,
    Projection,
    registered_shortcut_projections,
    residual_shortcuts,
)


FeatureVector = Mapping[str, float]


def destruction_features(
    evidence: Sequence[FactorizedCase],
    candidates: Sequence[AcquisitionCandidate],
    choice: GroundedSeparatingChoice,
    *,
    projections: Sequence[Projection] | None = None,
) -> dict[str, float]:
    """Public, target-hidden features for decision-statistic prediction."""

    selected = tuple(projections or registered_shortcut_projections(max_order=2))
    residual = residual_shortcuts(evidence, selected)
    candidate_index = {candidate.case_id: candidate for candidate in candidates}
    batch = [candidate_index[case_id] for case_id in choice.case_ids]
    features: dict[str, float] = {
        "state.residual_count": float(len(residual)),
        "state.evidence_count": float(len(evidence)),
        "action.batch_size": float(len(batch)),
        "action.structural_count": float(len(choice.structurally_tested_shortcuts)),
        "action.complement_distance_sum": float(choice.complement_distance_sum),
        "action.minimum_complement_distance": float(
            choice.minimum_complement_distance
        ),
        "action.new_factor_values": float(choice.new_factor_values),
        "action.new_pairwise_cells": float(choice.new_pairwise_cells),
        "action.execution_cost_billions": choice.execution_cost / 1_000_000_000,
    }
    features["interaction.structural_x_distance"] = (
        features["action.structural_count"]
        * features["action.complement_distance_sum"]
    )
    features["interaction.residual_x_structural"] = (
        features["state.residual_count"]
        * features["action.structural_count"]
    )
    features["interaction.batch_x_distance"] = (
        features["action.batch_size"]
        * features["action.complement_distance_sum"]
    )
    tested = set(choice.structurally_tested_shortcuts)
    for projection in selected:
        token = "+".join(projection)
        features[f"residual.{token}"] = float(projection in residual)
        features[f"tested.{token}"] = float(projection in tested)
        if projection in residual:
            features[f"interaction.residual_tested.{token}"] = float(
                projection in tested
            )
    for axis in GENERALIZATION_AXES:
        values = [candidate.factors[axis] for candidate in batch]
        features[f"batch_diversity.{axis}"] = float(len(set(values)))
        for value in values:
            key = f"batch_factor.{axis}={value}"
            features[key] = features.get(key, 0.0) + 1.0 / len(batch)
    label_counts: dict[str, int] = {}
    for case in evidence:
        label_counts[case.target_signature] = label_counts.get(case.target_signature, 0) + 1
    for label, count in label_counts.items():
        features[f"evidence_label.{label}"] = count / len(evidence)
    anchor_count = 0
    for projection in tested:
        evidence_values = {case.projection(projection) for case in evidence}
        anchor_count += sum(
            candidate.projection(projection) in evidence_values for candidate in batch
        )
    features["action.anchor_count"] = float(anchor_count)
    return features


@dataclass(frozen=True)
class DestructionTrainingExample:
    state_id: str
    action_id: str
    features: FeatureVector
    destroyed_shortcut_count: int

    def __post_init__(self) -> None:
        if not self.state_id or not self.action_id:
            raise ValueError("destruction example identifiers must be non-empty")
        if self.destroyed_shortcut_count < 0:
            raise ValueError("destroyed shortcut count must be nonnegative")
        if not self.features or any(not math.isfinite(value) for value in self.features.values()):
            raise ValueError("destruction example features must be finite and non-empty")


def destruction_examples_from_compiled_assets(
    assets: object,
) -> tuple[DestructionTrainingExample, ...]:
    """Load only validator-approved, state-grouped calibration supervision."""

    manifest = getattr(assets, "manifest", None)
    calibration = getattr(assets, "calibration", None)
    source_trace_hash = getattr(assets, "source_trace_hash", None)
    if (
        not isinstance(manifest, Mapping)
        or manifest.get("target_hiding_verified") is not True
        or not isinstance(source_trace_hash, str)
        or not source_trace_hash.startswith("sha256:")
        or not isinstance(calibration, tuple)
    ):
        raise ValueError("ranker requires verified compiled trajectory assets")
    examples: list[DestructionTrainingExample] = []
    for state in calibration:
        if not isinstance(state, Mapping) or not isinstance(state.get("actions"), list):
            raise ValueError("calibration state is malformed")
        state_id = str(state.get("state_id") or "")
        candidate_set_hash = str(state.get("candidate_set_hash") or "")
        if not state_id or not candidate_set_hash.startswith("sha256:"):
            raise ValueError("calibration state lineage is missing")
        for action in state["actions"]:
            if not isinstance(action, Mapping):
                raise ValueError("calibration action is malformed")
            raw_features = action.get("public_features")
            realized_micros = action.get("realized_destruction_micros")
            if not isinstance(raw_features, Mapping) or not isinstance(realized_micros, int):
                raise ValueError("calibration action lacks features or outcome")
            if realized_micros < 0 or realized_micros % 1_000_000 != 0:
                raise ValueError("destruction outcome must be an exact nonnegative count")
            features = {
                str(name): float(value)
                for name, value in raw_features.items()
                if isinstance(value, (int, float)) and not isinstance(value, bool)
            }
            if len(features) != len(raw_features):
                raise ValueError("ranker features must all be numeric")
            examples.append(
                DestructionTrainingExample(
                    state_id=f"{state_id}@{candidate_set_hash}",
                    action_id=str(action.get("action_id") or ""),
                    features=features,
                    destroyed_shortcut_count=realized_micros // 1_000_000,
                )
            )
    if not examples:
        raise ValueError("compiled trajectory assets contain no calibration outcomes")
    return tuple(examples)


def _solve_linear_system(matrix: list[list[float]], vector: list[float]) -> list[float]:
    size = len(vector)
    augmented = [matrix[row][:] + [vector[row]] for row in range(size)]
    for column in range(size):
        pivot = max(range(column, size), key=lambda row: abs(augmented[row][column]))
        if abs(augmented[pivot][column]) < 1e-12:
            raise ValueError("ridge system is numerically singular")
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        divisor = augmented[column][column]
        augmented[column] = [value / divisor for value in augmented[column]]
        for row in range(size):
            if row == column:
                continue
            multiplier = augmented[row][column]
            if multiplier == 0:
                continue
            augmented[row] = [
                current - multiplier * pivot_value
                for current, pivot_value in zip(
                    augmented[row], augmented[column], strict=True
                )
            ]
    return [augmented[row][-1] for row in range(size)]


@dataclass(frozen=True)
class RidgeDestructionRanker:
    feature_names: tuple[str, ...]
    feature_means: tuple[float, ...]
    feature_scales: tuple[float, ...]
    weights: tuple[float, ...]
    ridge_penalty: float
    fit_example_hash: str

    @property
    def model_hash(self) -> str:
        return digest(
            {
                "model": "ridge_destruction_ranker_v0_1",
                "feature_names": self.feature_names,
                "feature_means": self.feature_means,
                "feature_scales": self.feature_scales,
                "weights": self.weights,
                "ridge_penalty": self.ridge_penalty,
                "fit_example_hash": self.fit_example_hash,
            }
        )

    def predict_micros(self, features: FeatureVector) -> int:
        normalized = [1.0]
        normalized.extend(
            (features.get(name, 0.0) - center) / scale
            for name, center, scale in zip(
                self.feature_names,
                self.feature_means,
                self.feature_scales,
                strict=True,
            )
        )
        prediction = sum(
            weight * value for weight, value in zip(self.weights, normalized, strict=True)
        )
        maximum = int(features.get("state.residual_count", 0.0) * 1_000_000)
        return min(maximum, max(0, round(prediction * 1_000_000)))


def fit_ridge_destruction_ranker(
    examples: Sequence[DestructionTrainingExample],
    *,
    ridge_penalty: float = 1.0,
) -> RidgeDestructionRanker:
    if not examples or ridge_penalty <= 0:
        raise ValueError("ranker fit needs examples and positive ridge penalty")
    feature_names = tuple(sorted({name for item in examples for name in item.features}))
    columns = [
        [item.features.get(name, 0.0) for item in examples] for name in feature_names
    ]
    means = tuple(sum(column) / len(column) for column in columns)
    scales = tuple(
        max(
            1e-9,
            math.sqrt(
                sum((value - center) ** 2 for value in column) / len(column)
            ),
        )
        for column, center in zip(columns, means, strict=True)
    )
    design: list[list[float]] = []
    targets: list[float] = []
    for item in examples:
        row = [1.0]
        row.extend(
            (item.features.get(name, 0.0) - center) / scale
            for name, center, scale in zip(feature_names, means, scales, strict=True)
        )
        design.append(row)
        targets.append(float(item.destroyed_shortcut_count))
    dimension = len(feature_names) + 1
    gram = [[0.0 for _ in range(dimension)] for _ in range(dimension)]
    right = [0.0 for _ in range(dimension)]
    for row, target in zip(design, targets, strict=True):
        for left_index, left_value in enumerate(row):
            right[left_index] += left_value * target
            for right_index, right_value in enumerate(row):
                gram[left_index][right_index] += left_value * right_value
    for index in range(1, dimension):
        gram[index][index] += ridge_penalty
    weights = tuple(_solve_linear_system(gram, right))
    example_hash = digest(
        [
            {
                "state_id": item.state_id,
                "action_id": item.action_id,
                "features": dict(item.features),
                "destroyed_shortcut_count": item.destroyed_shortcut_count,
            }
            for item in examples
        ]
    )
    return RidgeDestructionRanker(
        feature_names=feature_names,
        feature_means=means,
        feature_scales=scales,
        weights=weights,
        ridge_penalty=ridge_penalty,
        fit_example_hash=example_hash,
    )


@dataclass(frozen=True)
class StateMaximumCalibrationReceipt:
    model_hash: str
    fit_split_hash: str
    calibration_split_hash: str
    calibration_state_count: int
    alpha_ppm: int
    quantile_rank: int
    simultaneous_error_micros: int
    empirical_state_coverage_ppm: int

    def __post_init__(self) -> None:
        if not all(
            value.startswith("sha256:")
            for value in (
                self.model_hash,
                self.fit_split_hash,
                self.calibration_split_hash,
            )
        ):
            raise ValueError("calibration receipt hashes are invalid")
        if self.calibration_state_count <= 0:
            raise ValueError("calibration receipt needs states")
        if not 0 < self.alpha_ppm < 1_000_000:
            raise ValueError("calibration alpha must be in (0, 1000000)")

    @property
    def receipt_hash(self) -> str:
        return digest(self.__dict__)


def calibrate_state_maximum_error(
    model: RidgeDestructionRanker,
    examples: Sequence[DestructionTrainingExample],
    *,
    alpha_ppm: int,
    fit_split_hash: str,
) -> StateMaximumCalibrationReceipt:
    if not examples or not 0 < alpha_ppm < 1_000_000:
        raise ValueError("calibration examples and alpha are required")
    by_state: dict[str, list[DestructionTrainingExample]] = {}
    for item in examples:
        by_state.setdefault(item.state_id, []).append(item)
    state_errors = sorted(
        max(
            abs(
                model.predict_micros(item.features)
                - item.destroyed_shortcut_count * 1_000_000
            )
            for item in state_examples
        )
        for state_examples in by_state.values()
    )
    state_count = len(state_errors)
    numerator = (state_count + 1) * (1_000_000 - alpha_ppm)
    rank = (numerator + 1_000_000 - 1) // 1_000_000
    if rank > state_count:
        error = max(state_errors) + 15_000_000
    else:
        error = state_errors[max(0, rank - 1)]
    coverage = sum(value <= error for value in state_errors) * 1_000_000 // state_count
    calibration_hash = digest(
        [
            {
                "state_id": item.state_id,
                "action_id": item.action_id,
                "features": dict(item.features),
                "destroyed_shortcut_count": item.destroyed_shortcut_count,
            }
            for item in examples
        ]
    )
    return StateMaximumCalibrationReceipt(
        model_hash=model.model_hash,
        fit_split_hash=fit_split_hash,
        calibration_split_hash=calibration_hash,
        calibration_state_count=state_count,
        alpha_ppm=alpha_ppm,
        quantile_rank=rank,
        simultaneous_error_micros=error,
        empirical_state_coverage_ppm=coverage,
    )


@dataclass(frozen=True)
class RankedDestructionChoice:
    choice: GroundedSeparatingChoice
    predicted_destruction_micros: int
    simultaneous_error_micros: int
    lower_destruction_micros: int
    model_hash: str
    calibration_receipt_hash: str


def select_calibrated_destruction_choice(
    model: RidgeDestructionRanker,
    calibration: StateMaximumCalibrationReceipt,
    evidence: Sequence[FactorizedCase],
    candidates: Sequence[AcquisitionCandidate],
    choices: Sequence[GroundedSeparatingChoice],
    *,
    projections: Sequence[Projection] | None = None,
) -> RankedDestructionChoice | None:
    if calibration.model_hash != model.model_hash:
        raise ValueError("calibration receipt does not bind the supplied model")
    ranked: list[RankedDestructionChoice] = []
    for choice in choices:
        features = destruction_features(
            evidence, candidates, choice, projections=projections
        )
        predicted = model.predict_micros(features)
        lower = max(0, predicted - calibration.simultaneous_error_micros)
        if lower == 0:
            continue
        ranked.append(
            RankedDestructionChoice(
                choice=choice,
                predicted_destruction_micros=predicted,
                simultaneous_error_micros=calibration.simultaneous_error_micros,
                lower_destruction_micros=lower,
                model_hash=model.model_hash,
                calibration_receipt_hash=calibration.receipt_hash,
            )
        )
    if not ranked:
        return None
    return min(
        ranked,
        key=lambda item: (
            -item.lower_destruction_micros / item.choice.execution_cost,
            item.choice.execution_cost,
            item.choice.case_ids,
        ),
    )
