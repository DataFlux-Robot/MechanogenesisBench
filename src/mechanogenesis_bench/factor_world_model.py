from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping, Sequence

from .canonical import digest
from .generalization import (
    AcquisitionCandidate,
    CandidateTargetBelief,
    FactorizedCase,
    GENERALIZATION_AXES,
)


def _ppm_distribution(log_scores: Mapping[str, float]) -> dict[str, int]:
    maximum = max(log_scores.values())
    weights = {label: math.exp(value - maximum) for label, value in log_scores.items()}
    total = sum(weights.values())
    raw = {label: weight * 1_000_000 / total for label, weight in weights.items()}
    ppm = {label: int(value) for label, value in raw.items()}
    remainder = 1_000_000 - sum(ppm.values())
    order = sorted(raw, key=lambda label: (-(raw[label] - ppm[label]), label))
    for label in order[:remainder]:
        ppm[label] += 1
    return ppm


@dataclass(frozen=True)
class FactorizedTargetWorldModel:
    """A deterministic target-hidden baseline, not the final Gθ world model."""

    labels: tuple[str, ...]
    label_counts: Mapping[str, int]
    value_counts: Mapping[tuple[str, str, str], int]
    axis_domains: Mapping[str, tuple[str, ...]]
    evidence_case_ids: tuple[str, ...]
    smoothing_micros: int = 1_000_000

    def __post_init__(self) -> None:
        if not self.labels or self.smoothing_micros <= 0:
            raise ValueError("factor world model requires labels and positive smoothing")

    @property
    def model_hash(self) -> str:
        return digest(
            {
                "model": "factorized_naive_bayes_v0_1",
                "labels": list(self.labels),
                "label_counts": dict(self.label_counts),
                "value_counts": {
                    "::".join(key): value
                    for key, value in sorted(self.value_counts.items())
                },
                "axis_domains": {
                    axis: list(values) for axis, values in self.axis_domains.items()
                },
                "evidence_case_ids": list(self.evidence_case_ids),
                "smoothing_micros": self.smoothing_micros,
            }
        )

    def predict(self, candidate: AcquisitionCandidate) -> CandidateTargetBelief:
        alpha = self.smoothing_micros / 1_000_000
        sample_count = sum(self.label_counts.values())
        log_scores: dict[str, float] = {}
        for label in self.labels:
            label_count = self.label_counts[label]
            score = math.log(label_count + alpha) - math.log(
                sample_count + alpha * len(self.labels)
            )
            for axis in GENERALIZATION_AXES:
                domain_size = max(1, len(self.axis_domains[axis]))
                count = self.value_counts.get(
                    (label, axis, candidate.factors[axis]), 0
                )
                score += math.log(count + alpha) - math.log(
                    label_count + alpha * domain_size
                )
            log_scores[label] = score
        return CandidateTargetBelief(
            candidate=candidate,
            target_probability_ppm=_ppm_distribution(log_scores),
            model_hash=self.model_hash,
        )


def fit_factorized_target_world_model(
    evidence: Sequence[FactorizedCase],
    public_candidates: Sequence[AcquisitionCandidate],
) -> FactorizedTargetWorldModel:
    if not evidence:
        raise ValueError("world model needs revealed evidence")
    labels = tuple(sorted({case.target_signature for case in evidence}))
    label_counts = {
        label: sum(case.target_signature == label for case in evidence)
        for label in labels
    }
    value_counts: dict[tuple[str, str, str], int] = {}
    for case in evidence:
        for axis in GENERALIZATION_AXES:
            key = (case.target_signature, axis, case.factors[axis])
            value_counts[key] = value_counts.get(key, 0) + 1
    axis_domains = {
        axis: tuple(
            sorted(
                {
                    *(case.factors[axis] for case in evidence),
                    *(candidate.factors[axis] for candidate in public_candidates),
                }
            )
        )
        for axis in GENERALIZATION_AXES
    }
    return FactorizedTargetWorldModel(
        labels=labels,
        label_counts=label_counts,
        value_counts=value_counts,
        axis_domains=axis_domains,
        evidence_case_ids=tuple(sorted(case.case_id for case in evidence)),
    )
