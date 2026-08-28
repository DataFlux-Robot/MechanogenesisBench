from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from itertools import combinations
from typing import Mapping, Sequence

from .canonical import digest


GENERALIZATION_AXES = (
    "world",
    "intervention",
    "embodiment",
    "error_state",
    "mechanism",
)


def _require_identifier(value: str, field: str) -> None:
    if not value or not value.replace("_", "").replace("-", "").isalnum():
        raise ValueError(f"{field} must be a bounded identifier")


@dataclass(frozen=True)
class FactorizedCase:
    """One evaluator-owned point in the physical task universe.

    ``target_signature`` is not required to be a class name.  It can identify a
    canonical program, a pairwise preference, or a certified behavioral
    equivalence class.  The benchmark only uses equality when constructing
    shortcut counterexamples.
    """

    case_id: str
    split: str
    factors: Mapping[str, str]
    target_signature: str
    execution_cost: int = 1

    def __post_init__(self) -> None:
        _require_identifier(self.case_id, "case_id")
        _require_identifier(self.split, "split")
        if not self.target_signature:
            raise ValueError("target_signature must be non-empty")
        if self.execution_cost <= 0:
            raise ValueError("execution_cost must be positive")
        if set(self.factors) != set(GENERALIZATION_AXES):
            raise ValueError(
                "factors must contain exactly the registered generalization axes"
            )
        for axis, value in self.factors.items():
            _require_identifier(axis, "factor axis")
            _require_identifier(value, f"factor value for {axis}")

    @property
    def factor_tuple(self) -> tuple[str, ...]:
        return tuple(self.factors[axis] for axis in GENERALIZATION_AXES)

    def projection(self, axes: Sequence[str]) -> tuple[str, ...]:
        if not axes or any(axis not in GENERALIZATION_AXES for axis in axes):
            raise ValueError("projection axes must be a non-empty registered subset")
        if len(axes) != len(set(axes)):
            raise ValueError("projection axes must be unique")
        return tuple(self.factors[axis] for axis in axes)

    def to_dict(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "split": self.split,
            "factors": dict(self.factors),
            "target_signature": self.target_signature,
            "execution_cost": self.execution_cost,
        }

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> "FactorizedCase":
        expected = {
            "case_id",
            "split",
            "factors",
            "target_signature",
            "execution_cost",
        }
        if set(raw) != expected or not isinstance(raw["factors"], Mapping):
            raise ValueError("factorized case schema mismatch")
        return cls(
            case_id=str(raw["case_id"]),
            split=str(raw["split"]),
            factors={str(key): str(value) for key, value in raw["factors"].items()},
            target_signature=str(raw["target_signature"]),
            execution_cost=int(raw["execution_cost"]),
        )


Projection = tuple[str, ...]


def registered_shortcut_projections(max_order: int = 2) -> tuple[Projection, ...]:
    """Return low-order factor projections that the benchmark must refute.

    A projection represents the entire class of deterministic selectors that
    can inspect only those axes.  A same-projection/opposite-target witness
    refutes every selector in that class, rather than one hand-written rule.
    """

    if not 1 <= max_order < len(GENERALIZATION_AXES):
        raise ValueError("max_order must be between 1 and axis_count - 1")
    return tuple(
        projection
        for order in range(1, max_order + 1)
        for projection in combinations(GENERALIZATION_AXES, order)
    )


def _collision_witness(
    cases: Sequence[FactorizedCase], projection: Projection
) -> tuple[str, str] | None:
    seen: dict[tuple[str, ...], FactorizedCase] = {}
    for case in sorted(cases, key=lambda item: item.case_id):
        key = case.projection(projection)
        previous = seen.get(key)
        if previous is not None and previous.target_signature != case.target_signature:
            return previous.case_id, case.case_id
        seen[key] = case
    return None


def shortcut_witnesses(
    cases: Sequence[FactorizedCase],
    projections: Sequence[Projection],
) -> dict[Projection, tuple[str, str]]:
    witnesses: dict[Projection, tuple[str, str]] = {}
    for projection in projections:
        witness = _collision_witness(cases, projection)
        if witness is not None:
            witnesses[tuple(projection)] = witness
    return witnesses


def residual_shortcuts(
    cases: Sequence[FactorizedCase],
    projections: Sequence[Projection],
) -> tuple[Projection, ...]:
    destroyed = shortcut_witnesses(cases, projections)
    return tuple(projection for projection in projections if projection not in destroyed)


def marginal_values(cases: Sequence[FactorizedCase]) -> dict[str, set[str]]:
    return {
        axis: {case.factors[axis] for case in cases}
        for axis in GENERALIZATION_AXES
    }


def unseen_interactions(
    train: Sequence[FactorizedCase],
    sealed: Sequence[FactorizedCase],
    *,
    order: int = 2,
) -> set[tuple[Projection, tuple[str, ...]]]:
    if not 2 <= order <= len(GENERALIZATION_AXES):
        raise ValueError("interaction order must be between 2 and axis count")
    projections = tuple(combinations(GENERALIZATION_AXES, order))
    train_cells = {
        (projection, case.projection(projection))
        for projection in projections
        for case in train
    }
    return {
        (projection, case.projection(projection))
        for projection in projections
        for case in sealed
        if (projection, case.projection(projection)) not in train_cells
    }


@dataclass(frozen=True)
class EngineeringEvidenceReceipt:
    """HWE-style engineering gates without pretending they are equivalent.

    The first three counts cover canonical parsing, Lean checking and reference
    replay for every evaluated case.  Independent backends and physical trials
    are separate evidence, so simulation-only runs cannot silently receive a
    physical label.
    """

    evaluated_cases: int
    canonical_parse_passes: int
    lean_kernel_passes: int
    reference_replay_passes: int
    independent_backend_passes: int
    physical_trial_passes: int
    independent_numeric_seeds: int

    def __post_init__(self) -> None:
        values = tuple(self.__dict__.values())
        if any(value < 0 for value in values):
            raise ValueError("engineering evidence counts must be nonnegative")
        for count in (
            self.canonical_parse_passes,
            self.lean_kernel_passes,
            self.reference_replay_passes,
            self.independent_backend_passes,
            self.physical_trial_passes,
        ):
            if count > self.evaluated_cases:
                raise ValueError("engineering pass count exceeds evaluated cases")

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> "EngineeringEvidenceReceipt":
        expected = set(cls.__dataclass_fields__)
        if set(raw) != expected:
            raise ValueError("engineering evidence receipt schema mismatch")
        return cls(**{field: int(raw[field]) for field in expected})

    def violations(self, *, require_physical: bool) -> tuple[str, ...]:
        checks = {
            "no_evaluated_cases": self.evaluated_cases > 0,
            "canonical_parse_incomplete": (
                self.canonical_parse_passes == self.evaluated_cases
            ),
            "lean_kernel_incomplete": self.lean_kernel_passes == self.evaluated_cases,
            "reference_replay_incomplete": (
                self.reference_replay_passes == self.evaluated_cases
            ),
            "independent_backend_incomplete": (
                self.independent_backend_passes == self.evaluated_cases
            ),
            "numeric_seed_replication_missing": self.independent_numeric_seeds >= 3,
            "physical_trial_missing": (
                not require_physical or self.physical_trial_passes > 0
            ),
        }
        return tuple(name for name, passed in checks.items() if not passed)


@dataclass(frozen=True)
class GeneralizationGate:
    minimum_sealed_accuracy_ppm: int = 900_000
    minimum_worst_group_accuracy_ppm: int = 750_000
    require_physical: bool = True

    def __post_init__(self) -> None:
        for value in (
            self.minimum_sealed_accuracy_ppm,
            self.minimum_worst_group_accuracy_ppm,
        ):
            if not 0 <= value <= 1_000_000:
                raise ValueError("accuracy thresholds must be in parts per million")


@dataclass(frozen=True)
class GeneralizationReport:
    eligible: bool
    violations: tuple[str, ...]
    train_case_count: int
    sealed_case_count: int
    sealed_correct: int
    sealed_accuracy_ppm: int
    worst_mechanism_accuracy_ppm: int
    marginal_value_overlap_complete: bool
    exact_factor_tuple_overlap_count: int
    unseen_pairwise_interaction_count: int
    registered_shortcut_count: int
    destroyed_shortcut_count: int
    residual_shortcuts: tuple[Projection, ...]
    shortcut_witnesses: Mapping[Projection, tuple[str, str]]
    engineering_violations: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "eligible": self.eligible,
            "violations": list(self.violations),
            "train_case_count": self.train_case_count,
            "sealed_case_count": self.sealed_case_count,
            "sealed_correct": self.sealed_correct,
            "sealed_accuracy_ppm": self.sealed_accuracy_ppm,
            "worst_mechanism_accuracy_ppm": self.worst_mechanism_accuracy_ppm,
            "marginal_value_overlap_complete": self.marginal_value_overlap_complete,
            "exact_factor_tuple_overlap_count": self.exact_factor_tuple_overlap_count,
            "unseen_pairwise_interaction_count": self.unseen_pairwise_interaction_count,
            "registered_shortcut_count": self.registered_shortcut_count,
            "destroyed_shortcut_count": self.destroyed_shortcut_count,
            "residual_shortcuts": [list(item) for item in self.residual_shortcuts],
            "shortcut_witnesses": {
                "+".join(key): list(value)
                for key, value in sorted(self.shortcut_witnesses.items())
            },
            "engineering_violations": list(self.engineering_violations),
        }


def evaluate_generalization(
    train: Sequence[FactorizedCase],
    sealed: Sequence[FactorizedCase],
    predictions: Mapping[str, str],
    engineering: EngineeringEvidenceReceipt,
    *,
    projections: Sequence[Projection] | None = None,
    gate: GeneralizationGate | None = None,
) -> GeneralizationReport:
    if not train or not sealed:
        raise ValueError("generalization evaluation needs non-empty train and sealed sets")
    if len({case.case_id for case in (*train, *sealed)}) != len(train) + len(sealed):
        raise ValueError("case identifiers must be globally unique")
    selected_projections = tuple(projections or registered_shortcut_projections())
    selected_gate = gate or GeneralizationGate()
    train_values = marginal_values(train)
    sealed_values = marginal_values(sealed)
    marginal_complete = all(
        sealed_values[axis] <= train_values[axis] for axis in GENERALIZATION_AXES
    )
    train_tuples = {case.factor_tuple for case in train}
    sealed_tuples = {case.factor_tuple for case in sealed}
    tuple_overlap = len(train_tuples & sealed_tuples)
    unseen_pairs = unseen_interactions(train, sealed, order=2)
    witnesses = shortcut_witnesses(train, selected_projections)
    residual = tuple(
        projection for projection in selected_projections if projection not in witnesses
    )
    missing_predictions = [case.case_id for case in sealed if case.case_id not in predictions]
    sealed_correct = sum(
        predictions.get(case.case_id) == case.target_signature for case in sealed
    )
    sealed_accuracy_ppm = sealed_correct * 1_000_000 // len(sealed)
    per_mechanism: dict[str, list[bool]] = {}
    for case in sealed:
        per_mechanism.setdefault(case.factors["mechanism"], []).append(
            predictions.get(case.case_id) == case.target_signature
        )
    worst_group_ppm = min(
        sum(values) * 1_000_000 // len(values) for values in per_mechanism.values()
    )
    engineering_violations = engineering.violations(
        require_physical=selected_gate.require_physical
    )
    checks = {
        "missing_sealed_predictions": not missing_predictions,
        "sealed_split_reuses_exact_factor_tuple": tuple_overlap == 0,
        "sealed_factor_value_not_seen_in_train": marginal_complete,
        "sealed_has_no_novel_pairwise_interaction": bool(unseen_pairs),
        "registered_shortcuts_survive_training": not residual,
        "sealed_accuracy_below_threshold": (
            sealed_accuracy_ppm >= selected_gate.minimum_sealed_accuracy_ppm
        ),
        "worst_mechanism_accuracy_below_threshold": (
            worst_group_ppm >= selected_gate.minimum_worst_group_accuracy_ppm
        ),
        "engineering_case_count_mismatch": (
            engineering.evaluated_cases == len(sealed)
        ),
        "engineering_evidence_incomplete": not engineering_violations,
    }
    violations = tuple(name for name, passed in checks.items() if not passed)
    return GeneralizationReport(
        eligible=not violations,
        violations=violations,
        train_case_count=len(train),
        sealed_case_count=len(sealed),
        sealed_correct=sealed_correct,
        sealed_accuracy_ppm=sealed_accuracy_ppm,
        worst_mechanism_accuracy_ppm=worst_group_ppm,
        marginal_value_overlap_complete=marginal_complete,
        exact_factor_tuple_overlap_count=tuple_overlap,
        unseen_pairwise_interaction_count=len(unseen_pairs),
        registered_shortcut_count=len(selected_projections),
        destroyed_shortcut_count=len(witnesses),
        residual_shortcuts=residual,
        shortcut_witnesses=witnesses,
        engineering_violations=engineering_violations,
    )


def lean_generalization_certificate(
    train: Sequence[FactorizedCase],
    sealed: Sequence[FactorizedCase],
    predictions: Mapping[str, str],
    report: GeneralizationReport,
    engineering: EngineeringEvidenceReceipt,
    *,
    gate: GeneralizationGate | None = None,
) -> dict[str, int | bool]:
    """Lower an evaluator report into the Lean sovereign certificate ABI."""

    selected_gate = gate or GeneralizationGate()
    train_values = marginal_values(train)
    sealed_values = marginal_values(sealed)
    group_rows: dict[str, list[bool]] = {}
    for case in sealed:
        group_rows.setdefault(case.factors["mechanism"], []).append(
            predictions.get(case.case_id) == case.target_signature
        )
    factor_value_count = sum(len(values) for values in sealed_values.values())
    factor_overlap_count = sum(
        len(sealed_values[axis] & train_values[axis]) for axis in GENERALIZATION_AXES
    )
    worst_group = min(
        group_rows.values(), key=lambda rows: (sum(rows) / len(rows), len(rows))
    )
    worst_group_count = len(worst_group)
    worst_group_correct = sum(worst_group)

    def split_id(cases: Sequence[FactorizedCase]) -> int:
        value = digest(sorted(case.case_id for case in cases))
        return int(value.split(":", 1)[1][:16], 16)

    return {
        "trainSplitId": split_id(train),
        "sealedSplitId": split_id(sealed),
        "exactFactorTupleOverlapCount": report.exact_factor_tuple_overlap_count,
        "registeredAxisCount": len(GENERALIZATION_AXES),
        "sealedFactorValueCount": factor_value_count,
        "factorValuesSeenInTrainCount": factor_overlap_count,
        "unseenInteractionCount": report.unseen_pairwise_interaction_count,
        "registeredShortcutCount": report.registered_shortcut_count,
        "destroyedShortcutCount": report.destroyed_shortcut_count,
        "sealedCaseCount": report.sealed_case_count,
        "predictionCount": sum(case.case_id in predictions for case in sealed),
        "sealedCorrectCount": report.sealed_correct,
        "worstGroupCaseCount": worst_group_count,
        "worstGroupCorrectCount": worst_group_correct,
        "minimumAccuracyPPM": selected_gate.minimum_sealed_accuracy_ppm,
        "minimumWorstGroupAccuracyPPM": (
            selected_gate.minimum_worst_group_accuracy_ppm
        ),
        "canonicalPassCount": engineering.canonical_parse_passes,
        "leanPassCount": engineering.lean_kernel_passes,
        "replayPassCount": engineering.reference_replay_passes,
        "independentBackendPassCount": engineering.independent_backend_passes,
        "independentNumericSeedCount": engineering.independent_numeric_seeds,
        "physicalRequired": selected_gate.require_physical,
        "physicalPassCount": engineering.physical_trial_passes,
        "sealedReadBeforeFreeze": False,
        "recursiveClaim": False,
        "generatorUpdateCount": 0,
        "parentFutureEstimate": 0,
        "placeboFutureEstimate": 0,
        "actualFutureEstimate": 0,
        "simultaneousError": 0,
        "fullUpdateCost": 0,
    }


@dataclass(frozen=True)
class CounterexampleChoice:
    case_ids: tuple[str, ...]
    newly_destroyed: tuple[Projection, ...]
    new_factor_values: int
    new_pairwise_cells: int
    execution_cost: int

    @property
    def utility_numerator(self) -> int:
        # Shortcut destruction is lexicographically dominant; diversity breaks
        # ties.  Integer arithmetic keeps selection deterministic.
        return (
            len(self.newly_destroyed) * 1_000_000
            + self.new_pairwise_cells * 1_000
            + self.new_factor_values
        )


def _new_coverage_counts(
    evidence: Sequence[FactorizedCase], additions: Sequence[FactorizedCase]
) -> tuple[int, int]:
    old_values = marginal_values(evidence) if evidence else {
        axis: set() for axis in GENERALIZATION_AXES
    }
    new_factor_values = sum(
        len({case.factors[axis] for case in additions} - old_values[axis])
        for axis in GENERALIZATION_AXES
    )
    projections = tuple(combinations(GENERALIZATION_AXES, 2))
    old_cells = {
        (projection, case.projection(projection))
        for projection in projections
        for case in evidence
    }
    added_cells = {
        (projection, case.projection(projection))
        for projection in projections
        for case in additions
    }
    return new_factor_values, len(added_cells - old_cells)


def select_counterexample_batch(
    evidence: Sequence[FactorizedCase],
    pool: Sequence[FactorizedCase],
    *,
    projections: Sequence[Projection] | None = None,
) -> CounterexampleChoice | None:
    """Choose a high-yield batch from an already executed labeled archive.

    This function reads candidate targets and is therefore an oracle curriculum
    selector/upper bound, not a deployable next-physical-experiment policy.
    Candidate batches contain one or two archived cases.  Online acquisition
    must use ``select_disagreement_experiment`` and reveal targets only after
    execution.
    """

    if len({case.case_id for case in (*evidence, *pool)}) != len(evidence) + len(pool):
        raise ValueError("evidence and acquisition pool must be content-disjoint")
    selected = tuple(projections or registered_shortcut_projections())
    before = set(shortcut_witnesses(evidence, selected))
    candidates = [(case,) for case in pool]
    candidates.extend(combinations(pool, 2))
    choices: list[CounterexampleChoice] = []
    for additions in candidates:
        after = set(shortcut_witnesses([*evidence, *additions], selected))
        newly_destroyed = tuple(
            projection for projection in selected if projection in after - before
        )
        if not newly_destroyed:
            continue
        new_values, new_cells = _new_coverage_counts(evidence, additions)
        choices.append(
            CounterexampleChoice(
                case_ids=tuple(sorted(case.case_id for case in additions)),
                newly_destroyed=newly_destroyed,
                new_factor_values=new_values,
                new_pairwise_cells=new_cells,
                execution_cost=sum(case.execution_cost for case in additions),
            )
        )
    if not choices:
        return None
    return min(
        choices,
        key=lambda choice: (
            -choice.utility_numerator / choice.execution_cost,
            choice.execution_cost,
            choice.case_ids,
        ),
    )


def build_shortcut_destruction_curriculum(
    initial_evidence: Sequence[FactorizedCase],
    acquisition_pool: Sequence[FactorizedCase],
    *,
    projections: Sequence[Projection] | None = None,
    max_rounds: int = 100,
) -> tuple[tuple[FactorizedCase, ...], tuple[CounterexampleChoice, ...]]:
    """Build a finite counterexample-guided curriculum from a labeled archive.

    Termination is fail-closed: the function returns with residual shortcuts if
    the available intervention/task pool cannot distinguish them.  It never
    fabricates a proof of generalization from marginal coverage alone.
    """

    if max_rounds <= 0:
        raise ValueError("max_rounds must be positive")
    selected = tuple(projections or registered_shortcut_projections())
    evidence = list(initial_evidence)
    remaining_pool = list(acquisition_pool)
    trace: list[CounterexampleChoice] = []
    for _ in range(max_rounds):
        if not residual_shortcuts(evidence, selected):
            break
        choice = select_counterexample_batch(
            evidence, remaining_pool, projections=selected
        )
        if choice is None:
            break
        chosen = {case_id for case_id in choice.case_ids}
        evidence.extend(case for case in remaining_pool if case.case_id in chosen)
        remaining_pool = [case for case in remaining_pool if case.case_id not in chosen]
        trace.append(choice)
    return tuple(evidence), tuple(trace)


@dataclass(frozen=True)
class AcquisitionCandidate:
    """A candidate experiment before evaluator outcome reveal."""

    case_id: str
    factors: Mapping[str, str]
    execution_cost: int

    def __post_init__(self) -> None:
        _require_identifier(self.case_id, "case_id")
        if set(self.factors) != set(GENERALIZATION_AXES):
            raise ValueError("acquisition candidate has incomplete factor axes")
        if self.execution_cost <= 0:
            raise ValueError("acquisition execution cost must be positive")

    def projection(self, axes: Sequence[str]) -> tuple[str, ...]:
        return tuple(self.factors[axis] for axis in axes)

    @classmethod
    def from_hidden_case(cls, case: FactorizedCase) -> "AcquisitionCandidate":
        return cls(case.case_id, dict(case.factors), case.execution_cost)


@dataclass(frozen=True)
class CandidateTargetBelief:
    """Frozen world-model prediction; probabilities use exact ppm integers."""

    candidate: AcquisitionCandidate
    target_probability_ppm: Mapping[str, int]
    model_hash: str

    def __post_init__(self) -> None:
        if not self.model_hash.startswith("sha256:"):
            raise ValueError("candidate belief requires a content-bound model hash")
        if not self.target_probability_ppm:
            raise ValueError("candidate belief requires at least one target")
        if any(value < 0 for value in self.target_probability_ppm.values()):
            raise ValueError("target probabilities must be nonnegative")
        if sum(self.target_probability_ppm.values()) != 1_000_000:
            raise ValueError("target probabilities must sum to one million ppm")


@dataclass(frozen=True)
class PlannedAcquisitionChoice:
    case_ids: tuple[str, ...]
    expected_destroyed_shortcuts_ppm: int
    new_factor_values: int
    new_pairwise_cells: int
    execution_cost: int
    model_hashes: tuple[str, ...]


@dataclass(frozen=True)
class CalibratedCandidateTargetBelief:
    belief: CandidateTargetBelief
    simultaneous_probability_error_ppm: int
    calibration_receipt_hash: str

    def __post_init__(self) -> None:
        if not 0 <= self.simultaneous_probability_error_ppm <= 1_000_000:
            raise ValueError("calibration error must be a ppm probability bound")
        if not self.calibration_receipt_hash.startswith("sha256:"):
            raise ValueError("calibrated belief requires a receipt hash")


@dataclass(frozen=True)
class CertifiedPlannedAcquisitionChoice:
    case_ids: tuple[str, ...]
    expected_destroyed_shortcuts_ppm: int
    simultaneous_forecast_error_ppm: int
    lower_destroyed_shortcuts_ppm: int
    execution_cost: int
    model_hashes: tuple[str, ...]
    calibration_receipt_hashes: tuple[str, ...]


@dataclass(frozen=True)
class GroundedSeparatingChoice:
    """Target-hidden structural contrast used when forecasts cannot certify value.

    ``structurally_tested_shortcuts`` records projection classes for which the
    proposed batch contains a same-projection/different-complement contrast.
    It is an access opportunity, not a shortcut-destruction certificate: only
    evaluator-revealed target disagreement can remove a shortcut.
    """

    case_ids: tuple[str, ...]
    structurally_tested_shortcuts: tuple[Projection, ...]
    complement_distance_sum: int
    minimum_complement_distance: int
    new_factor_values: int
    new_pairwise_cells: int
    execution_cost: int


def _complement_distance(
    left: FactorizedCase | AcquisitionCandidate,
    right: FactorizedCase | AcquisitionCandidate,
    projection: Projection,
) -> int:
    complement = tuple(axis for axis in GENERALIZATION_AXES if axis not in projection)
    return sum(left.factors[axis] != right.factors[axis] for axis in complement)


def _structurally_tested_projections(
    evidence: Sequence[FactorizedCase],
    batch: Sequence[AcquisitionCandidate],
    projections: Sequence[Projection],
    *,
    minimum_complement_distance: int,
) -> tuple[tuple[Projection, ...], int]:
    tested: list[Projection] = []
    distance_sum = 0
    for projection in projections:
        distances: list[int] = []
        for left in batch:
            for right in (*evidence, *batch):
                if left.case_id == right.case_id:
                    continue
                if left.projection(projection) != right.projection(projection):
                    continue
                distance = _complement_distance(left, right, projection)
                if distance >= minimum_complement_distance:
                    distances.append(distance)
        if distances:
            tested.append(projection)
            distance_sum += max(distances)
    return tuple(tested), distance_sum


def grounded_separating_choices(
    evidence: Sequence[FactorizedCase],
    candidates: Sequence[AcquisitionCandidate],
    *,
    projections: Sequence[Projection] | None = None,
    maximum_batch_size: int = 2,
    minimum_complement_distance: int = 1,
) -> tuple[GroundedSeparatingChoice, ...]:
    """Enumerate target-agnostic farthest contrasts for residual shortcuts.

    The selector groups candidates by a residual projection, then greedily
    chooses complement-distant members of each group.  It never reads a hidden
    candidate target or a world-model forecast.  This makes it a grounded
    separability-expansion fallback when the learned acquisition policy must
    abstain.  Structural separation does not by itself imply semantic target
    separation; execution and outcome reveal remain mandatory.
    """

    if maximum_batch_size <= 0:
        raise ValueError("maximum batch size must be positive")
    if minimum_complement_distance <= 0:
        raise ValueError("minimum complement distance must be positive")
    if len({candidate.case_id for candidate in candidates}) != len(candidates):
        raise ValueError("separating candidates must have unique case IDs")
    selected = tuple(projections or registered_shortcut_projections())
    residual = residual_shortcuts(evidence, selected)
    if not residual or not candidates:
        return ()

    candidate_batches: dict[tuple[str, ...], tuple[AcquisitionCandidate, ...]] = {}
    for projection in residual:
        grouped: dict[tuple[str, ...], list[AcquisitionCandidate]] = {}
        for candidate in candidates:
            grouped.setdefault(candidate.projection(projection), []).append(candidate)
        for projection_value, group in sorted(grouped.items()):
            anchors = [
                case
                for case in evidence
                if case.projection(projection) == projection_value
            ]
            if not anchors and len(group) < 2:
                continue
            remaining = sorted(group, key=lambda candidate: candidate.case_id)
            chosen: list[AcquisitionCandidate] = []
            while remaining and len(chosen) < maximum_batch_size:
                references: list[FactorizedCase | AcquisitionCandidate] = [
                    *anchors,
                    *chosen,
                ]

                def dispersion(candidate: AcquisitionCandidate) -> tuple[int, int, int]:
                    if references:
                        distances = [
                            _complement_distance(candidate, item, projection)
                            for item in references
                        ]
                        return (
                            min(distances),
                            max(distances),
                            -candidate.execution_cost,
                        )
                    pair_distances = [
                        _complement_distance(candidate, item, projection)
                        for item in remaining
                        if item.case_id != candidate.case_id
                    ]
                    maximum = max(pair_distances, default=0)
                    return (maximum, maximum, -candidate.execution_cost)

                next_candidate = max(remaining, key=dispersion)
                chosen.append(next_candidate)
                remaining.remove(next_candidate)
            batch = tuple(chosen)
            batch_ids = tuple(sorted(candidate.case_id for candidate in batch))
            candidate_batches[batch_ids] = batch

    choices: list[GroundedSeparatingChoice] = []
    for batch_ids, batch in candidate_batches.items():
        tested, distance_sum = _structurally_tested_projections(
            evidence,
            batch,
            residual,
            minimum_complement_distance=minimum_complement_distance,
        )
        if not tested:
            continue
        shadow_cases = [
            FactorizedCase(
                case_id=candidate.case_id,
                split="unrevealed",
                factors=candidate.factors,
                target_signature="unrevealed",
                execution_cost=candidate.execution_cost,
            )
            for candidate in batch
        ]
        new_values, new_cells = _new_coverage_counts(evidence, shadow_cases)
        choices.append(
            GroundedSeparatingChoice(
                case_ids=batch_ids,
                structurally_tested_shortcuts=tested,
                complement_distance_sum=distance_sum,
                minimum_complement_distance=minimum_complement_distance,
                new_factor_values=new_values,
                new_pairwise_cells=new_cells,
                execution_cost=sum(candidate.execution_cost for candidate in batch),
            )
        )
    if not choices:
        return ()
    return tuple(sorted(
        choices,
        key=lambda choice: (
            Fraction(-len(choice.structurally_tested_shortcuts), choice.execution_cost),
            -choice.complement_distance_sum,
            -choice.new_pairwise_cells,
            -choice.new_factor_values,
            choice.execution_cost,
            choice.case_ids,
        ),
    ))


def select_grounded_separating_experiment(
    evidence: Sequence[FactorizedCase],
    candidates: Sequence[AcquisitionCandidate],
    *,
    projections: Sequence[Projection] | None = None,
    maximum_batch_size: int = 2,
    minimum_complement_distance: int = 1,
) -> GroundedSeparatingChoice | None:
    """Return the best deterministic structural contrast, or abstain."""

    choices = grounded_separating_choices(
        evidence,
        candidates,
        projections=projections,
        maximum_batch_size=maximum_batch_size,
        minimum_complement_distance=minimum_complement_distance,
    )
    return choices[0] if choices else None


def _different_target_probability_ppm(
    left: Mapping[str, int], right: Mapping[str, int]
) -> int:
    labels = set(left) | set(right)
    same_numerator = sum(left.get(label, 0) * right.get(label, 0) for label in labels)
    return 1_000_000 - same_numerator // 1_000_000


def _expected_projection_destruction_ppm(
    evidence: Sequence[FactorizedCase],
    beliefs: Sequence[CandidateTargetBelief],
    projection: Projection,
) -> int:
    known: dict[tuple[str, ...], str] = {}
    for case in evidence:
        key = case.projection(projection)
        previous = known.get(key)
        if previous is not None and previous != case.target_signature:
            return 1_000_000
        known[key] = case.target_signature
    by_key: dict[tuple[str, ...], list[CandidateTargetBelief]] = {}
    for belief in beliefs:
        key = belief.candidate.projection(projection)
        by_key.setdefault(key, []).append(belief)
    best = 0
    for key, group in by_key.items():
        known_target = known.get(key)
        if known_target is not None:
            same_probability = 1_000_000
            for belief in group:
                same_probability = (
                    same_probability
                    * belief.target_probability_ppm.get(known_target, 0)
                    // 1_000_000
                )
            best = max(best, 1_000_000 - same_probability)
        elif len(group) == 2:
            best = max(
                best,
                _different_target_probability_ppm(
                    group[0].target_probability_ppm,
                    group[1].target_probability_ppm,
                ),
            )
    return best


def select_disagreement_experiment(
    evidence: Sequence[FactorizedCase],
    candidate_beliefs: Sequence[CandidateTargetBelief],
    *,
    projections: Sequence[Projection] | None = None,
) -> PlannedAcquisitionChoice | None:
    """Plan the next experiment without reading any candidate true target.

    A frozen world model supplies calibrated target distributions.  Selection
    maximizes expected registered-shortcut destruction per full execution cost;
    only evaluator-revealed outcomes can subsequently update the version space.
    """

    if len({belief.candidate.case_id for belief in candidate_beliefs}) != len(
        candidate_beliefs
    ):
        raise ValueError("candidate beliefs must have unique case IDs")
    selected = tuple(projections or registered_shortcut_projections())
    residual = residual_shortcuts(evidence, selected)
    batches: list[tuple[CandidateTargetBelief, ...]] = [
        (belief,) for belief in candidate_beliefs
    ]
    batches.extend(combinations(candidate_beliefs, 2))
    choices: list[PlannedAcquisitionChoice] = []
    for batch in batches:
        expected = sum(
            _expected_projection_destruction_ppm(evidence, batch, projection)
            for projection in residual
        )
        if expected <= 0:
            continue
        shadow_cases = [
            FactorizedCase(
                case_id=belief.candidate.case_id,
                split="unrevealed",
                factors=belief.candidate.factors,
                target_signature="unrevealed",
                execution_cost=belief.candidate.execution_cost,
            )
            for belief in batch
        ]
        new_values, new_cells = _new_coverage_counts(evidence, shadow_cases)
        choices.append(
            PlannedAcquisitionChoice(
                case_ids=tuple(sorted(case.case_id for case in shadow_cases)),
                expected_destroyed_shortcuts_ppm=expected,
                new_factor_values=new_values,
                new_pairwise_cells=new_cells,
                execution_cost=sum(case.execution_cost for case in shadow_cases),
                model_hashes=tuple(sorted(belief.model_hash for belief in batch)),
            )
        )
    if not choices:
        return None
    return min(
        choices,
        key=lambda choice: (
            -choice.expected_destroyed_shortcuts_ppm / choice.execution_cost,
            -choice.new_pairwise_cells,
            -choice.new_factor_values,
            choice.execution_cost,
            choice.case_ids,
        ),
    )


def select_certified_disagreement_experiment(
    evidence: Sequence[FactorizedCase],
    calibrated_beliefs: Sequence[CalibratedCandidateTargetBelief],
    *,
    projections: Sequence[Projection] | None = None,
) -> CertifiedPlannedAcquisitionChoice | None:
    """Select by a simultaneous lower confidence bound, or abstain.

    The probability-error aggregation is deliberately conservative: each
    residual projection pays the sum of candidate probability errors.  A more
    powerful model may supply a tighter joint receipt, but may not silently set
    the error to zero.
    """

    selected = tuple(projections or registered_shortcut_projections())
    residual = residual_shortcuts(evidence, selected)
    batches: list[tuple[CalibratedCandidateTargetBelief, ...]] = [
        (item,) for item in calibrated_beliefs
    ]
    batches.extend(combinations(calibrated_beliefs, 2))
    choices: list[CertifiedPlannedAcquisitionChoice] = []
    for batch in batches:
        beliefs = tuple(item.belief for item in batch)
        expected = sum(
            _expected_projection_destruction_ppm(evidence, beliefs, projection)
            for projection in residual
        )
        per_projection_error = min(
            1_000_000,
            sum(item.simultaneous_probability_error_ppm for item in batch),
        )
        total_error = len(residual) * per_projection_error
        lower = max(0, expected - total_error)
        if lower == 0:
            continue
        choices.append(
            CertifiedPlannedAcquisitionChoice(
                case_ids=tuple(
                    sorted(item.belief.candidate.case_id for item in batch)
                ),
                expected_destroyed_shortcuts_ppm=expected,
                simultaneous_forecast_error_ppm=total_error,
                lower_destroyed_shortcuts_ppm=lower,
                execution_cost=sum(
                    item.belief.candidate.execution_cost for item in batch
                ),
                model_hashes=tuple(
                    sorted(item.belief.model_hash for item in batch)
                ),
                calibration_receipt_hashes=tuple(
                    sorted(item.calibration_receipt_hash for item in batch)
                ),
            )
        )
    if not choices:
        return None
    return min(
        choices,
        key=lambda choice: (
            -choice.lower_destroyed_shortcuts_ppm / choice.execution_cost,
            choice.execution_cost,
            choice.case_ids,
        ),
    )


@dataclass(frozen=True)
class TrainingObjectiveTerms:
    """Metrics for optimization; none of them is a promotion certificate."""

    task_nll: float
    counterfactual_ranking_loss: float
    intervention_prediction_loss: float
    nuisance_consistency_loss: float
    recursive_credit_loss: float
    description_length_bits: float
    residual_shortcut_fraction: float

    def __post_init__(self) -> None:
        if any(value < 0 for value in self.__dict__.values()):
            raise ValueError("training objective terms must be nonnegative")


@dataclass(frozen=True)
class TrainingObjectiveWeights:
    counterfactual: float = 1.0
    intervention: float = 1.0
    consistency: float = 0.5
    recursive_credit: float = 1.0
    description_length: float = 1e-6
    shortcut_survival: float = 4.0

    def __post_init__(self) -> None:
        if any(value < 0 for value in self.__dict__.values()):
            raise ValueError("training objective weights must be nonnegative")


def lean_guided_training_objective(
    terms: TrainingObjectiveTerms,
    weights: TrainingObjectiveWeights | None = None,
) -> float:
    """Surrogate derived from the formal failure modes.

    MDL pressure is intentionally weak until counterexamples have destroyed
    registered shortcuts: a short shortcut can otherwise beat a longer causal
    rule.  Promotion remains an independent sealed/evidence decision.
    """

    selected = weights or TrainingObjectiveWeights()
    mdl_multiplier = 1.0 if terms.residual_shortcut_fraction == 0.0 else 0.0
    return (
        terms.task_nll
        + selected.counterfactual * terms.counterfactual_ranking_loss
        + selected.intervention * terms.intervention_prediction_loss
        + selected.consistency * terms.nuisance_consistency_loss
        + selected.recursive_credit * terms.recursive_credit_loss
        + selected.description_length
        * mdl_multiplier
        * terms.description_length_bits
        + selected.shortcut_survival * terms.residual_shortcut_fraction
    )
