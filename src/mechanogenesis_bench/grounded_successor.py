"""Grounded joint successor contract for weight-internalized recursive claims.

The older :mod:`coupled_successor` contract proves continuity of three hashes.
That is useful for conformance, but a changed demand-state hash is not evidence
that the model became better calibrated.  This module raises the claim level:

* the demand edge contains the actual frozen forecast and authorized outcome;
* the same checkpoint identity denotes the demand model and the trainable model;
* held-out demand calibration is replayed by a verifier-owned runtime;
* the exact sealed winning checkpoint is the replayed demand-update child; and
* the exact next forecast is inherited by the following generation.

Physical truth is still owned by PIPE certificates and their registered
metrology reports.  Human truth is still owned by authorized outcome adapters.
The code checks finite bindings; it does not manufacture either kind of truth.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Protocol, Sequence

from .canonical import digest
from .coupled_successor import SealedFullUpdatePosterior
from .human_demand import (
    EndorsedPositiveSurprise,
    HumanDemandClosureReceipt,
    HumanDemandForecast,
)
from .recursive_closure import (
    PIPECertificate,
    PIPEStatus,
    PIPEVerificationReport,
    verify_prsi_chain,
)


DEMAND_BELIEF_UPDATE_SCHEMA = "grounded-demand-belief-update/v1"
GROUNDED_JOINT_GENERATION_SCHEMA = "grounded-joint-successor/v1"


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


class FixedDemandBeliefRuntime(Protocol):
    """Verifier-owned deterministic refinement boundary.

    Implementations may replay a real trainer or verify signed trainer and
    evaluator receipts.  They must not be supplied by the candidate model.
    """

    trainer_hash: str
    evaluator_hash: str

    def training_input_hash(self, closure_hashes: Sequence[str]) -> str: ...

    def replay_update(
        self, parent_checkpoint_hash: str, training_input_hash: str
    ) -> tuple[str, str]:
        """Return ``(child_checkpoint_hash, trainer_receipt_hash)``."""

    def holdout_brier(
        self, checkpoint_hash: str, holdout_commitment_hash: str
    ) -> tuple[int, str]:
        """Return ``(brier_sum, evaluator_receipt_hash)``."""


@dataclass(frozen=True)
class GroundedDemandBeliefUpdate:
    """A weight-internalized demand-belief update with replayable improvement."""

    schema_version: str
    parent_checkpoint_hash: str
    successor_checkpoint_hash: str
    calibration_closure_hashes: tuple[str, ...]
    training_input_hash: str
    trainer_receipt_hash: str
    trainer_implementation_hash: str
    evaluator_implementation_hash: str
    holdout_commitment_hash: str
    holdout_brier_before: int
    holdout_brier_after: int
    holdout_before_receipt_hash: str
    holdout_after_receipt_hash: str
    full_parameter_execution: bool
    allowed_inference_history: tuple[str, ...]
    receipt_hash: str

    def unsigned_dict(self) -> dict[str, object]:
        value = asdict(self)
        value.pop("receipt_hash")
        return value

    def validate(self) -> None:
        if self.schema_version != DEMAND_BELIEF_UPDATE_SCHEMA:
            raise ValueError("unsupported grounded demand-belief update schema")
        for field in (
            "parent_checkpoint_hash",
            "successor_checkpoint_hash",
            "training_input_hash",
            "trainer_receipt_hash",
            "trainer_implementation_hash",
            "evaluator_implementation_hash",
            "holdout_commitment_hash",
            "holdout_before_receipt_hash",
            "holdout_after_receipt_hash",
            "receipt_hash",
        ):
            _require_digest(getattr(self, field), field)
        if not self.calibration_closure_hashes:
            raise ValueError("demand update requires authorized calibration closures")
        for closure_hash in self.calibration_closure_hashes:
            _require_digest(closure_hash, "calibration_closure_hash")
        if len(set(self.calibration_closure_hashes)) != len(
            self.calibration_closure_hashes
        ):
            raise ValueError("demand calibration closures must be distinct")
        if self.parent_checkpoint_hash == self.successor_checkpoint_hash:
            raise ValueError("demand belief update did not change checkpoint identity")
        if self.full_parameter_execution is not True:
            raise ValueError("demand belief must be internalized by full-parameter execution")
        if self.allowed_inference_history:
            raise ValueError("demand improvement must be available from weights only")
        _require_nat(self.holdout_brier_before, "holdout_brier_before")
        _require_nat(self.holdout_brier_after, "holdout_brier_after")
        if self.holdout_brier_after >= self.holdout_brier_before:
            raise ValueError("held-out authorized-demand calibration did not improve")
        if self.receipt_hash != digest(self.unsigned_dict()):
            raise ValueError("grounded demand-belief update receipt hash mismatch")


def validate_demand_belief_update_against_runtime(
    update: GroundedDemandBeliefUpdate,
    runtime: FixedDemandBeliefRuntime,
) -> None:
    """Replay all empirical numbers and identities under the fixed runtime."""

    update.validate()
    _require_digest(runtime.trainer_hash, "runtime.trainer_hash")
    _require_digest(runtime.evaluator_hash, "runtime.evaluator_hash")
    if update.trainer_implementation_hash != runtime.trainer_hash:
        raise ValueError("demand trainer is not the verifier-owned runtime")
    if update.evaluator_implementation_hash != runtime.evaluator_hash:
        raise ValueError("demand evaluator is not the verifier-owned runtime")
    expected_input = runtime.training_input_hash(update.calibration_closure_hashes)
    _require_digest(expected_input, "runtime.training_input_hash")
    if update.training_input_hash != expected_input:
        raise ValueError("demand update did not consume the exact closure set")
    child_hash, trainer_receipt_hash = runtime.replay_update(
        update.parent_checkpoint_hash, expected_input
    )
    if child_hash != update.successor_checkpoint_hash:
        raise ValueError("demand successor checkpoint does not replay")
    if trainer_receipt_hash != update.trainer_receipt_hash:
        raise ValueError("demand trainer receipt does not replay")
    before, before_receipt = runtime.holdout_brier(
        update.parent_checkpoint_hash, update.holdout_commitment_hash
    )
    after, after_receipt = runtime.holdout_brier(
        update.successor_checkpoint_hash, update.holdout_commitment_hash
    )
    if (before, after) != (
        update.holdout_brier_before,
        update.holdout_brier_after,
    ):
        raise ValueError("held-out demand calibration scores do not replay")
    if (before_receipt, after_receipt) != (
        update.holdout_before_receipt_hash,
        update.holdout_after_receipt_hash,
    ):
        raise ValueError("held-out demand evaluator receipts do not replay")


def joint_evidence_commitment(
    *,
    demand_closure_hash: str,
    product_hash: str,
    physical_execution_hash: str,
    realized_operator_hash: str,
) -> str:
    """Commit the evidence view from which update programmes are proposed."""

    for field, value in (
        ("demand_closure_hash", demand_closure_hash),
        ("product_hash", product_hash),
        ("physical_execution_hash", physical_execution_hash),
        ("realized_operator_hash", realized_operator_hash),
    ):
        _require_digest(value, field)
    return digest(
        {
            "schema_version": "grounded-joint-evidence/v1",
            "demand_closure_hash": demand_closure_hash,
            "product_hash": product_hash,
            "physical_execution_hash": physical_execution_hash,
            "realized_operator_hash": realized_operator_hash,
        }
    )


@dataclass(frozen=True)
class GroundedJointSuccessorGeneration:
    """One generation whose demand, weight and physical edges share identities."""

    schema_version: str
    generation_index: int
    parent_checkpoint_hash: str
    successor_checkpoint_hash: str
    demand_closure: HumanDemandClosureReceipt
    demand_belief_update: GroundedDemandBeliefUpdate
    successor_demand_forecast: HumanDemandForecast
    update_posterior: SealedFullUpdatePosterior
    input_operator_hash: str
    output_operator_hash: str
    product_hash: str
    physical_execution_hash: str
    next_mrs_hash: str
    endorsed_positive_surprise: EndorsedPositiveSurprise | None
    witness_hash: str

    def unsigned_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "generation_index": self.generation_index,
            "parent_checkpoint_hash": self.parent_checkpoint_hash,
            "successor_checkpoint_hash": self.successor_checkpoint_hash,
            "demand_closure": asdict(self.demand_closure),
            "demand_belief_update": asdict(self.demand_belief_update),
            "successor_demand_forecast": asdict(self.successor_demand_forecast),
            "update_posterior": asdict(self.update_posterior),
            "input_operator_hash": self.input_operator_hash,
            "output_operator_hash": self.output_operator_hash,
            "product_hash": self.product_hash,
            "physical_execution_hash": self.physical_execution_hash,
            "next_mrs_hash": self.next_mrs_hash,
            "endorsed_positive_surprise": (
                asdict(self.endorsed_positive_surprise)
                if self.endorsed_positive_surprise is not None
                else None
            ),
        }

    def validate(self, demand_runtime: FixedDemandBeliefRuntime) -> None:
        if self.schema_version != GROUNDED_JOINT_GENERATION_SCHEMA:
            raise ValueError("unsupported grounded joint successor schema")
        _require_nat(self.generation_index, "generation_index")
        for field in (
            "parent_checkpoint_hash",
            "successor_checkpoint_hash",
            "input_operator_hash",
            "output_operator_hash",
            "product_hash",
            "physical_execution_hash",
            "next_mrs_hash",
            "witness_hash",
        ):
            _require_digest(getattr(self, field), field)
        self.demand_closure.validate()
        validate_demand_belief_update_against_runtime(
            self.demand_belief_update, demand_runtime
        )
        self.successor_demand_forecast.validate()
        self.update_posterior.validate()

        closure = self.demand_closure
        demand_update = self.demand_belief_update
        posterior = self.update_posterior
        winner = posterior.candidates[posterior.winner_index]
        if closure.parent_demand_state_hash != self.parent_checkpoint_hash:
            raise ValueError("parent demand belief is not the parent G-theta weights")
        if closure.child_demand_state_hash != self.successor_checkpoint_hash:
            raise ValueError("child demand belief is not the successor G-theta weights")
        if closure.forecast.model_hash != self.parent_checkpoint_hash:
            raise ValueError("frozen demand forecast was not emitted by parent G-theta")
        if closure.outcome.product_hash != self.product_hash:
            raise ValueError("authorized human outcome concerns a different product")
        if closure.update_training_receipt_hash != demand_update.trainer_receipt_hash:
            raise ValueError("demand closure and weight update use different training")
        if closure.closure_hash not in demand_update.calibration_closure_hashes:
            raise ValueError("adopted demand update omits this generation's closure")
        if demand_update.parent_checkpoint_hash != self.parent_checkpoint_hash:
            raise ValueError("demand update and generation bind different parents")
        if demand_update.successor_checkpoint_hash != self.successor_checkpoint_hash:
            raise ValueError("demand update and generation bind different successors")
        if posterior.parent_checkpoint_hash != self.parent_checkpoint_hash:
            raise ValueError("sealed posterior and generation bind different parents")
        if posterior.successor_checkpoint_hash != self.successor_checkpoint_hash:
            raise ValueError("sealed winner is not the generation successor")
        if winner.training_receipt_hash != demand_update.trainer_receipt_hash:
            raise ValueError("demand improvement was trained outside the sealed winner")
        expected_evidence = joint_evidence_commitment(
            demand_closure_hash=closure.closure_hash,
            product_hash=self.product_hash,
            physical_execution_hash=self.physical_execution_hash,
            realized_operator_hash=self.output_operator_hash,
        )
        if posterior.evidence_hash != expected_evidence:
            raise ValueError("update candidates did not consume the joint evidence")
        if self.successor_demand_forecast.model_hash != self.successor_checkpoint_hash:
            raise ValueError("next demand forecast was not emitted by successor weights")
        if (
            self.successor_demand_forecast.frozen_sequence
            <= closure.outcome.observed_sequence
        ):
            raise ValueError("successor demand forecast predates its training outcome")
        if self.input_operator_hash == self.output_operator_hash:
            raise ValueError("generation did not realize a distinct physical operator")
        if self.endorsed_positive_surprise is not None:
            surprise = self.endorsed_positive_surprise
            surprise.validate()
            if surprise.demand_closure_hash != closure.closure_hash:
                raise ValueError("endorsed surprise is not bound to demand closure")
            if surprise.product_hash != self.product_hash:
                raise ValueError("endorsed surprise concerns a different product")
        if self.witness_hash != digest(self.unsigned_dict()):
            raise ValueError("grounded joint successor witness hash mismatch")


@dataclass(frozen=True)
class GroundedJointChainReport:
    valid: bool
    depth: int
    label: str | None
    demand_calibration_improved: bool
    exact_weight_identity: bool
    physical_successor_closed: bool
    endorsed_surprise_count: int
    reasons: tuple[str, ...]


def verify_grounded_joint_successor_chain(
    generations: Sequence[GroundedJointSuccessorGeneration],
    demand_runtimes: Sequence[FixedDemandBeliefRuntime],
    pipe_certificates: Sequence[PIPECertificate],
    pipe_reports: Sequence[PIPEVerificationReport],
) -> GroundedJointChainReport:
    """Verify a two-or-more-generation joint successor chain, fail closed."""

    reasons: list[str] = []
    if len(generations) < 2:
        reasons.append("grounded joint claim requires at least two generations")
    if len(demand_runtimes) != len(generations):
        reasons.append("every generation requires a fixed demand runtime")
    if len(pipe_certificates) != len(generations):
        reasons.append("every generation requires one PIPE certificate")
    if len(pipe_reports) != len(generations):
        reasons.append("every generation requires one PIPE report")

    for index, generation in enumerate(generations):
        if generation.generation_index != index:
            reasons.append("generation indices must be contiguous from zero")
        if index < len(demand_runtimes):
            try:
                generation.validate(demand_runtimes[index])
            except ValueError as error:
                reasons.append(f"generation {index}: {error}")

    for index, (earlier, later) in enumerate(zip(generations, generations[1:])):
        if earlier.successor_checkpoint_hash != later.parent_checkpoint_hash:
            reasons.append(f"generation {index} successor weights are not inherited")
        if earlier.output_operator_hash != later.input_operator_hash:
            reasons.append(f"generation {index} physical operator is not inherited")
        if (
            earlier.successor_demand_forecast.forecast_hash
            != later.demand_closure.forecast.forecast_hash
        ):
            reasons.append(f"generation {index} successor demand forecast is not used")

    for index, report in enumerate(pipe_reports):
        if report.status is not PIPEStatus.ACCEPTED:
            reasons.append(f"generation {index} physical edge is not accepted PIPE")

    physical_chain = None
    if len(pipe_certificates) == len(generations):
        for index, (generation, certificate) in enumerate(
            zip(generations, pipe_certificates)
        ):
            if certificate.treatment_hash != generation.input_operator_hash:
                reasons.append(f"generation {index} PIPE treatment identity mismatch")
            if certificate.realized_operator_hash != generation.output_operator_hash:
                reasons.append(f"generation {index} PIPE output identity mismatch")
            if certificate.witness_hash != generation.physical_execution_hash:
                reasons.append(f"generation {index} PIPE execution identity mismatch")
        physical_chain = verify_prsi_chain(tuple(pipe_certificates))
        reasons.extend(physical_chain.reasons)

    demand_improved = bool(generations) and all(
        generation.demand_belief_update.holdout_brier_after
        < generation.demand_belief_update.holdout_brier_before
        for generation in generations
    )
    exact_weights = bool(generations) and all(
        generation.successor_checkpoint_hash
        == generation.update_posterior.candidates[
            generation.update_posterior.winner_index
        ].final_checkpoint_hash
        == generation.demand_belief_update.successor_checkpoint_hash
        for generation in generations
    )
    physical_closed = bool(
        physical_chain is not None
        and physical_chain.valid
        and len(pipe_reports) == len(generations)
        and all(report.status is PIPEStatus.ACCEPTED for report in pipe_reports)
    )
    if not demand_improved:
        reasons.append("held-out demand calibration did not improve on every edge")
    if not exact_weights:
        reasons.append("demand and sealed weight successor identities diverge")
    if not physical_closed:
        reasons.append("physical successor-production chain is not closed")

    return GroundedJointChainReport(
        valid=not reasons,
        depth=len(generations),
        label=(f"grounded-joint-prsi-{len(generations)}" if not reasons else None),
        demand_calibration_improved=demand_improved,
        exact_weight_identity=exact_weights,
        physical_successor_closed=physical_closed,
        endorsed_surprise_count=sum(
            generation.endorsed_positive_surprise is not None
            for generation in generations
        ),
        reasons=tuple(reasons),
    )


__all__ = [
    "DEMAND_BELIEF_UPDATE_SCHEMA",
    "GROUNDED_JOINT_GENERATION_SCHEMA",
    "FixedDemandBeliefRuntime",
    "GroundedDemandBeliefUpdate",
    "GroundedJointChainReport",
    "GroundedJointSuccessorGeneration",
    "joint_evidence_commitment",
    "validate_demand_belief_update_against_runtime",
    "verify_grounded_joint_successor_chain",
]
