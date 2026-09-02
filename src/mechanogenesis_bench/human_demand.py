"""Exact benchmark-side records for sensing and closing human demand.

Synthetic personas may produce forecasts, counterfactuals and candidate briefs.
They cannot produce an ``AuthorizedHumanOutcome``.  Real-outcome adapters own
that boundary and must bind consent, evaluator identity, timing and utility
intervals before a demand state can be updated.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from .canonical import digest


DEMAND_FORECAST_SCHEMA = "human-demand-forecast/v1"
HUMAN_OUTCOME_SCHEMA = "authorized-human-outcome/v1"
DEMAND_CLOSURE_SCHEMA = "human-demand-closure/v1"
ENDORSED_SURPRISE_SCHEMA = "endorsed-positive-surprise/v1"
AUTHORIZED_SOURCES = {"authorized_historical", "authorized_prospective"}
PPM = 1_000_000


def _require_digest(value: object, field: str) -> str:
    if not (
        isinstance(value, str)
        and value.startswith("sha256:")
        and len(value) == 71
        and all(character in "0123456789abcdef" for character in value[7:])
    ):
        raise ValueError(f"{field} must be a canonical sha256 digest")
    return value


def _require_nat(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field} must be a nonnegative integer")
    return value


def _require_ppm(value: object, field: str) -> int:
    result = _require_nat(value, field)
    if result > PPM:
        raise ValueError(f"{field} exceeds 1,000,000 ppm")
    return result


@dataclass(frozen=True)
class HumanDemandForecast:
    schema_version: str
    population_commitment_hash: str
    opportunity_set_hash: str
    selected_action_hash: str
    outcome_probabilities_ppm: tuple[tuple[str, int], ...]
    uncertainty_ppm: int
    model_hash: str
    adapter_hash: str
    frozen_sequence: int
    source_kind: str
    forecast_hash: str

    def unsigned_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "population_commitment_hash": self.population_commitment_hash,
            "opportunity_set_hash": self.opportunity_set_hash,
            "selected_action_hash": self.selected_action_hash,
            "outcome_probabilities_ppm": [
                list(row) for row in self.outcome_probabilities_ppm
            ],
            "uncertainty_ppm": self.uncertainty_ppm,
            "model_hash": self.model_hash,
            "adapter_hash": self.adapter_hash,
            "frozen_sequence": self.frozen_sequence,
            "source_kind": self.source_kind,
        }

    def validate(self) -> None:
        if self.schema_version != DEMAND_FORECAST_SCHEMA:
            raise ValueError("unsupported human-demand forecast schema")
        for field in (
            "population_commitment_hash",
            "opportunity_set_hash",
            "selected_action_hash",
            "model_hash",
            "adapter_hash",
            "forecast_hash",
        ):
            _require_digest(getattr(self, field), field)
        if self.source_kind not in {"synthetic", *AUTHORIZED_SOURCES}:
            raise ValueError("unsupported demand forecast source")
        if not self.outcome_probabilities_ppm:
            raise ValueError("forecast requires a nonempty outcome distribution")
        labels = [label for label, _ in self.outcome_probabilities_ppm]
        if any(not label for label in labels) or len(labels) != len(set(labels)):
            raise ValueError("forecast outcome labels must be nonempty and unique")
        for _, probability in self.outcome_probabilities_ppm:
            _require_ppm(probability, "outcome probability")
        if sum(value for _, value in self.outcome_probabilities_ppm) != PPM:
            raise ValueError("forecast outcome probabilities must sum to 1,000,000 ppm")
        _require_ppm(self.uncertainty_ppm, "uncertainty_ppm")
        _require_nat(self.frozen_sequence, "frozen_sequence")
        if self.forecast_hash != digest(self.unsigned_dict()):
            raise ValueError("human-demand forecast hash mismatch")


@dataclass(frozen=True)
class AuthorizedHumanOutcome:
    schema_version: str
    population_commitment_hash: str
    action_hash: str
    product_hash: str
    realized_outcome: str
    source_kind: str
    consent_receipt_hash: str
    evaluator_hash: str
    evaluator_owned_by_candidate: bool
    observed_sequence: int
    utility_lower_micro: int
    utility_upper_micro: int
    rights_passed: bool
    safety_passed: bool
    opt_out_available: bool
    outcome_hash: str

    def unsigned_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "population_commitment_hash": self.population_commitment_hash,
            "action_hash": self.action_hash,
            "product_hash": self.product_hash,
            "realized_outcome": self.realized_outcome,
            "source_kind": self.source_kind,
            "consent_receipt_hash": self.consent_receipt_hash,
            "evaluator_hash": self.evaluator_hash,
            "evaluator_owned_by_candidate": self.evaluator_owned_by_candidate,
            "observed_sequence": self.observed_sequence,
            "utility_lower_micro": self.utility_lower_micro,
            "utility_upper_micro": self.utility_upper_micro,
            "rights_passed": self.rights_passed,
            "safety_passed": self.safety_passed,
            "opt_out_available": self.opt_out_available,
        }

    def validate(self) -> None:
        if self.schema_version != HUMAN_OUTCOME_SCHEMA:
            raise ValueError("unsupported authorized human outcome schema")
        for field in (
            "population_commitment_hash",
            "action_hash",
            "product_hash",
            "consent_receipt_hash",
            "evaluator_hash",
            "outcome_hash",
        ):
            _require_digest(getattr(self, field), field)
        if not self.realized_outcome:
            raise ValueError("realized_outcome must be nonempty")
        if self.source_kind not in AUTHORIZED_SOURCES:
            raise ValueError("synthetic persona output is not an authorized human outcome")
        if self.evaluator_owned_by_candidate:
            raise ValueError("candidate-owned evaluator cannot certify human utility")
        _require_nat(self.observed_sequence, "observed_sequence")
        if isinstance(self.utility_lower_micro, bool) or not isinstance(
            self.utility_lower_micro, int
        ):
            raise ValueError("utility_lower_micro must be an integer")
        if isinstance(self.utility_upper_micro, bool) or not isinstance(
            self.utility_upper_micro, int
        ):
            raise ValueError("utility_upper_micro must be an integer")
        if self.utility_lower_micro > self.utility_upper_micro:
            raise ValueError("human utility interval is reversed")
        if not all((self.rights_passed, self.safety_passed, self.opt_out_available)):
            raise ValueError("authorized human outcome violates a noncompensable guard")
        if self.outcome_hash != digest(self.unsigned_dict()):
            raise ValueError("authorized human outcome hash mismatch")


def categorical_brier_sum_ppm2(
    probabilities: tuple[tuple[str, int], ...], realized_outcome: str
) -> int:
    labels = {label for label, _ in probabilities}
    if realized_outcome not in labels:
        raise ValueError("realized outcome was absent from the frozen forecast")
    return sum(
        (probability - (PPM if label == realized_outcome else 0)) ** 2
        for label, probability in probabilities
    )


@dataclass(frozen=True)
class HumanDemandClosureReceipt:
    schema_version: str
    parent_demand_state_hash: str
    child_demand_state_hash: str
    forecast: HumanDemandForecast
    outcome: AuthorizedHumanOutcome
    forecast_brier_sum_ppm2: int
    update_training_receipt_hash: str
    closure_hash: str

    def unsigned_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "parent_demand_state_hash": self.parent_demand_state_hash,
            "child_demand_state_hash": self.child_demand_state_hash,
            "forecast": asdict(self.forecast),
            "outcome": asdict(self.outcome),
            "forecast_brier_sum_ppm2": self.forecast_brier_sum_ppm2,
            "update_training_receipt_hash": self.update_training_receipt_hash,
        }

    def validate(self) -> None:
        if self.schema_version != DEMAND_CLOSURE_SCHEMA:
            raise ValueError("unsupported human-demand closure schema")
        for field in (
            "parent_demand_state_hash",
            "child_demand_state_hash",
            "update_training_receipt_hash",
            "closure_hash",
        ):
            _require_digest(getattr(self, field), field)
        self.forecast.validate()
        self.outcome.validate()
        if self.parent_demand_state_hash == self.child_demand_state_hash:
            raise ValueError("human outcome did not update the demand state")
        if (
            self.forecast.population_commitment_hash
            != self.outcome.population_commitment_hash
        ):
            raise ValueError("forecast and outcome concern different populations")
        if self.forecast.selected_action_hash != self.outcome.action_hash:
            raise ValueError("observed action differs from the frozen demand action")
        if self.forecast.frozen_sequence >= self.outcome.observed_sequence:
            raise ValueError("human outcome was observed before the forecast froze")
        expected_brier = categorical_brier_sum_ppm2(
            self.forecast.outcome_probabilities_ppm,
            self.outcome.realized_outcome,
        )
        if self.forecast_brier_sum_ppm2 != expected_brier:
            raise ValueError("demand calibration is not derived from frozen forecast")
        if self.closure_hash != digest(self.unsigned_dict()):
            raise ValueError("human-demand closure hash mismatch")


@dataclass(frozen=True)
class EndorsedPositiveSurprise:
    """A novel affordance whose utility gain is endorsed after reflection."""

    schema_version: str
    demand_closure_hash: str
    product_hash: str
    novel_affordance_receipt_hash: str
    best_known_utility_upper_micro: int
    product_utility_lower_micro: int
    required_gain_micro: int
    metapreference_endorsement_ppm: int
    required_endorsement_ppm: int
    delayed_persistence_ppm: int
    required_persistence_ppm: int
    disclosed_alternatives: bool
    non_coercive: bool
    independent_evaluator: bool
    receipt_hash: str

    def unsigned_dict(self) -> dict[str, object]:
        return asdict(self) | {"receipt_hash": None}

    def validate(self) -> None:
        if self.schema_version != ENDORSED_SURPRISE_SCHEMA:
            raise ValueError("unsupported endorsed-surprise schema")
        for field in (
            "demand_closure_hash",
            "product_hash",
            "novel_affordance_receipt_hash",
            "receipt_hash",
        ):
            _require_digest(getattr(self, field), field)
        if isinstance(self.required_gain_micro, bool) or not isinstance(
            self.required_gain_micro, int
        ) or self.required_gain_micro <= 0:
            raise ValueError("positive surprise requires a strict utility gain")
        for field in (
            "metapreference_endorsement_ppm",
            "required_endorsement_ppm",
            "delayed_persistence_ppm",
            "required_persistence_ppm",
        ):
            _require_ppm(getattr(self, field), field)
        if (
            self.product_utility_lower_micro
            < self.best_known_utility_upper_micro + self.required_gain_micro
        ):
            raise ValueError("novel product does not beat the best known utility bound")
        if self.metapreference_endorsement_ppm < self.required_endorsement_ppm:
            raise ValueError("preference change lacks human metapreference endorsement")
        if self.delayed_persistence_ppm < self.required_persistence_ppm:
            raise ValueError("positive surprise did not persist at delayed observation")
        if not all(
            (self.disclosed_alternatives, self.non_coercive, self.independent_evaluator)
        ):
            raise ValueError("positive surprise lacks anti-manipulation safeguards")
        expected = digest(self.unsigned_dict())
        if self.receipt_hash != expected:
            raise ValueError("endorsed-surprise receipt hash mismatch")


__all__ = [
    "AUTHORIZED_SOURCES",
    "DEMAND_CLOSURE_SCHEMA",
    "DEMAND_FORECAST_SCHEMA",
    "ENDORSED_SURPRISE_SCHEMA",
    "HUMAN_OUTCOME_SCHEMA",
    "AuthorizedHumanOutcome",
    "EndorsedPositiveSurprise",
    "HumanDemandClosureReceipt",
    "HumanDemandForecast",
    "categorical_brier_sum_ppm2",
]
