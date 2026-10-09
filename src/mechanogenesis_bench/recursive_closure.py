"""Fail-closed protocol for finite Physical RSI evidence.

The executable verifier checks identities, bounded outcomes, resource caps and
finite-chain linkage.  It never infers that a simulator or physical intervention
is faithful merely because a submission says so: causal promotion requires a
separate trusted ``IdentificationValidation`` supplied by the evaluator.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .models import ResourceVector


@dataclass(frozen=True)
class SuccessorIdentity:
    generator_hash: str
    runtime_hash: str
    protocol_hash: str


@dataclass(frozen=True)
class ImprovementOperatorSpec:
    spec_hash: str
    verifier_hash: str
    reset_protocol_hash: str
    horizon: int
    required_gain: float


@dataclass(frozen=True)
class ForkObservation:
    successor: SuccessorIdentity
    treatment_hash: str
    operator_spec_hash: str
    seed_schedule_hash: str
    disturbance_schedule_hash: str
    evaluator_hash: str
    treatment_enabled: bool
    post_transition_loss: float
    physical_contribution_loss: float
    sequential_operator_loss: float
    resources: ResourceVector

    @property
    def ancestor_total_loss(self) -> float:
        return self.physical_contribution_loss + self.sequential_operator_loss


@dataclass(frozen=True)
class RealizedOperator:
    operator_hash: str
    certificate_hash: str
    verifier_hash: str
    treatment_handle_hash: str


@dataclass(frozen=True)
class PIPEEvidence:
    treatment_hash: str
    operator_spec: ImprovementOperatorSpec
    with_treatment: ForkObservation
    without_treatment: ForkObservation
    realized_operator: RealizedOperator
    post_transition_margin: float
    ancestor_lift_margin: float
    resource_cap: ResourceVector


@dataclass(frozen=True)
class IdentificationValidation:
    """Trusted-evaluator findings that the protocol cannot prove by itself."""

    consistency: bool
    treatment_integrity: bool
    reset_equivalence: bool
    no_interference: bool
    operator_verifier_valid: bool
    purge_complete: bool
    substance_equivalence: bool
    effective_generator_identity: bool

    @property
    def valid(self) -> bool:
        return all(getattr(self, name) for name in self.__dataclass_fields__)


class PIPEStatus(str, Enum):
    REJECTED = "rejected"
    NON_IDENTIFIABLE = "non_identifiable"
    ACCEPTED = "pipe_1"


@dataclass(frozen=True)
class PIPEVerificationReport:
    status: PIPEStatus
    reasons: tuple[str, ...]
    post_transition_effect: float
    ancestor_net_lift: float

    @property
    def accepted(self) -> bool:
        return self.status is PIPEStatus.ACCEPTED


def _same_fork_assignment(left: ForkObservation, right: ForkObservation) -> bool:
    """Fields that must not change under the physical treatment intervention."""

    return (
        left.successor == right.successor
        and left.treatment_hash == right.treatment_hash
        and left.operator_spec_hash == right.operator_spec_hash
        and left.seed_schedule_hash == right.seed_schedule_hash
        and left.disturbance_schedule_hash == right.disturbance_schedule_hash
        and left.evaluator_hash == right.evaluator_hash
    )


def verify_pipe(
    evidence: PIPEEvidence,
    validation: IdentificationValidation | None = None,
) -> PIPEVerificationReport:
    """Check one Physical Improvement-Production Edge.

    ``PIPEStatus.ACCEPTED`` means the registered finite benchmark claim is
    supported under trusted physical validation.  It is not a proof of an
    infinite process or of behavior outside the registered operator family.
    """

    structural: list[str] = []
    plus = evidence.with_treatment
    minus = evidence.without_treatment

    if evidence.operator_spec.horizon < 2:
        structural.append("operator horizon must contain at least two instances")
    if evidence.operator_spec.required_gain <= 0:
        structural.append("operator spec must require a strict capability gain")
    if evidence.post_transition_margin <= 0:
        structural.append("post-transition margin must be positive")
    if evidence.ancestor_lift_margin <= 0:
        structural.append("ancestor-lift margin must be positive")
    if evidence.treatment_hash != plus.treatment_hash:
        structural.append("treatment identity is not bound to the treatment fork")
    if evidence.treatment_hash != minus.treatment_hash:
        structural.append("treatment identity is not bound to the control fork")
    if evidence.operator_spec.spec_hash != plus.operator_spec_hash:
        structural.append("operator spec is not bound to the treatment fork")
    if evidence.operator_spec.spec_hash != minus.operator_spec_hash:
        structural.append("operator spec is not bound to the control fork")
    if not _same_fork_assignment(plus, minus):
        structural.append(
            "physical forks do not bind identical generator/runtime/protocol assignments"
        )
    if not plus.treatment_enabled or minus.treatment_enabled:
        structural.append("fork treatment flags are not an on/off physical intervention")
    if evidence.realized_operator.verifier_hash != evidence.operator_spec.verifier_hash:
        structural.append("realized operator certificate uses a different verifier")
    if not evidence.realized_operator.treatment_handle_hash:
        structural.append("realized operator lacks a next-edge treatment handle")

    post_effect = minus.post_transition_loss - plus.post_transition_loss
    ancestor_lift = minus.ancestor_total_loss - plus.ancestor_total_loss
    if post_effect < evidence.post_transition_margin:
        structural.append("physical treatment does not meet its causal-effect margin")
    if ancestor_lift < evidence.ancestor_lift_margin:
        structural.append(
            "physical treatment does not meet common-ancestor amortized lift"
        )
    if not plus.resources.within(evidence.resource_cap):
        structural.append("treatment fork exceeds a resource or safety cap")
    if not minus.resources.within(evidence.resource_cap):
        structural.append("control fork exceeds a resource or safety cap")

    if structural:
        return PIPEVerificationReport(
            status=PIPEStatus.REJECTED,
            reasons=tuple(structural),
            post_transition_effect=post_effect,
            ancestor_net_lift=ancestor_lift,
        )

    if validation is None:
        return PIPEVerificationReport(
            status=PIPEStatus.NON_IDENTIFIABLE,
            reasons=("trusted physical identification validation is missing",),
            post_transition_effect=post_effect,
            ancestor_net_lift=ancestor_lift,
        )
    if not validation.valid:
        failed = tuple(
            f"physical identification assumption failed: {name}"
            for name in validation.__dataclass_fields__
            if not getattr(validation, name)
        )
        return PIPEVerificationReport(
            status=PIPEStatus.NON_IDENTIFIABLE,
            reasons=failed,
            post_transition_effect=post_effect,
            ancestor_net_lift=ancestor_lift,
        )

    return PIPEVerificationReport(
        status=PIPEStatus.ACCEPTED,
        reasons=(),
        post_transition_effect=post_effect,
        ancestor_net_lift=ancestor_lift,
    )


@dataclass(frozen=True)
class PIPECertificate:
    treatment_hash: str
    realized_operator_hash: str
    witness_hash: str


@dataclass(frozen=True)
class PRSIChainReport:
    valid: bool
    depth: int
    label: str | None
    reasons: tuple[str, ...]


def verify_prsi_chain(certificates: tuple[PIPECertificate, ...]) -> PRSIChainReport:
    """Verify exact finite recurrence; one edge is never labeled PRSI."""

    reasons: list[str] = []
    if len(certificates) < 2:
        reasons.append("PRSI requires at least two linked PIPE witnesses")
    if len({item.witness_hash for item in certificates}) != len(certificates):
        reasons.append("PIPE witness identities must be unique")
    for index, (earlier, later) in enumerate(zip(certificates, certificates[1:])):
        if earlier.realized_operator_hash != later.treatment_hash:
            reasons.append(
                f"edge {index} realized operator is not edge {index + 1} treatment"
            )
    return PRSIChainReport(
        valid=not reasons,
        depth=len(certificates),
        label=f"PRSI-{len(certificates)}" if not reasons else None,
        reasons=tuple(reasons),
    )
