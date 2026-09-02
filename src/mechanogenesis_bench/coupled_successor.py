"""Finite contract for human-demand-guided coupled successor production.

The contract binds three different closures without treating any one of them
as a substitute for the others:

* demand closure: a forecast is frozen, an independently evaluated outcome is
  observed, and the demand state changes;
* weight closure: every frozen update programme is fully executed, the sealed
  posterior is opened only afterwards, and the exact winning checkpoint is
  adopted;
* physical closure: the exact operator produced by one certified PIPE edge is
  the treatment actually used by the next edge.

This module checks finite identities and ordering.  It does not turn a claimed
human outcome into a real observation, or a claimed physical receipt into a
PIPE.  Those facts remain owned by registered demand and physical evaluators.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Sequence

from .canonical import digest
from .recursive_closure import (
    PIPECertificate,
    PIPEStatus,
    PIPEVerificationReport,
    verify_prsi_chain,
)


UPDATE_POSTERIOR_SCHEMA = "sealed-full-update-posterior/v1"
COUPLED_GENERATION_SCHEMA = "human-demand-coupled-successor/v1"


def _require_digest(value: object, field: str) -> str:
    if not (
        isinstance(value, str)
        and value.startswith("sha256:")
        and len(value) == 71
        and all(character in "0123456789abcdef" for character in value[7:])
    ):
        raise ValueError(f"{field} must be a canonical sha256 digest")
    return value


def _require_nonnegative_int(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field} must be a nonnegative integer")
    return value


@dataclass(frozen=True)
class FullUpdateCandidate:
    """One complete candidate successor produced from the frozen parent.

    ``full_parameter_execution`` is an evaluator finding, not a model-authored
    success flag.  A benchmark adapter must derive it from the registered
    trainer receipt before constructing this object.
    """

    update_program_hash: str
    training_receipt_hash: str
    final_checkpoint_hash: str
    sealed_probe_receipt_hash: str
    sealed_probe_score: int
    full_parameter_execution: bool

    def validate(self) -> None:
        for field in (
            "update_program_hash",
            "training_receipt_hash",
            "final_checkpoint_hash",
            "sealed_probe_receipt_hash",
        ):
            _require_digest(getattr(self, field), field)
        _require_nonnegative_int(self.sealed_probe_score, "sealed_probe_score")
        if self.full_parameter_execution is not True:
            raise ValueError("every frozen update candidate must be fully executed")


def update_candidate_commitment(
    parent_checkpoint_hash: str,
    evidence_hash: str,
    candidates: Sequence[FullUpdateCandidate],
) -> str:
    _require_digest(parent_checkpoint_hash, "parent_checkpoint_hash")
    _require_digest(evidence_hash, "evidence_hash")
    return digest(
        {
            "schema_version": "full-update-candidate-set/v1",
            "parent_checkpoint_hash": parent_checkpoint_hash,
            "evidence_hash": evidence_hash,
            "ordered_update_program_hashes": [
                candidate.update_program_hash for candidate in candidates
            ],
        }
    )


@dataclass(frozen=True)
class SealedFullUpdatePosterior:
    """SEAL posterior over fully materialized candidate checkpoints."""

    schema_version: str
    parent_checkpoint_hash: str
    evidence_hash: str
    candidate_set_commitment_hash: str
    candidates: tuple[FullUpdateCandidate, ...]
    proposal_frozen_sequence: int
    seal_opened_sequence: int
    winner_index: int
    successor_checkpoint_hash: str
    allowed_inference_history: tuple[str, ...]

    def validate(self) -> None:
        if self.schema_version != UPDATE_POSTERIOR_SCHEMA:
            raise ValueError("unsupported sealed update posterior schema")
        _require_digest(self.parent_checkpoint_hash, "parent_checkpoint_hash")
        _require_digest(self.evidence_hash, "evidence_hash")
        _require_digest(
            self.candidate_set_commitment_hash,
            "candidate_set_commitment_hash",
        )
        _require_digest(self.successor_checkpoint_hash, "successor_checkpoint_hash")
        if len(self.candidates) < 2:
            raise ValueError("sealed posterior requires at least two update candidates")
        for candidate in self.candidates:
            candidate.validate()
        if len({item.update_program_hash for item in self.candidates}) != len(
            self.candidates
        ):
            raise ValueError("frozen update programmes must be distinct")
        if len({item.training_receipt_hash for item in self.candidates}) != len(
            self.candidates
        ):
            raise ValueError("candidate training receipts must be distinct")
        if len({item.final_checkpoint_hash for item in self.candidates}) != len(
            self.candidates
        ):
            raise ValueError("candidate checkpoints must be distinct")
        expected_commitment = update_candidate_commitment(
            self.parent_checkpoint_hash,
            self.evidence_hash,
            self.candidates,
        )
        if self.candidate_set_commitment_hash != expected_commitment:
            raise ValueError("candidate set changed after its commitment")
        _require_nonnegative_int(
            self.proposal_frozen_sequence, "proposal_frozen_sequence"
        )
        _require_nonnegative_int(self.seal_opened_sequence, "seal_opened_sequence")
        if self.proposal_frozen_sequence >= self.seal_opened_sequence:
            raise ValueError("sealed outcomes opened before candidate set freeze")
        _require_nonnegative_int(self.winner_index, "winner_index")
        if self.winner_index >= len(self.candidates):
            raise ValueError("winner_index is outside the frozen candidate set")
        expected_winner = max(
            range(len(self.candidates)),
            key=lambda index: (self.candidates[index].sealed_probe_score, -index),
        )
        if self.winner_index != expected_winner:
            raise ValueError("posterior winner disagrees with sealed probe ordering")
        winner = self.candidates[self.winner_index]
        if self.successor_checkpoint_hash != winner.final_checkpoint_hash:
            raise ValueError(
                "successor is not the byte-identical winning candidate checkpoint"
            )
        if self.successor_checkpoint_hash == self.parent_checkpoint_hash:
            raise ValueError("winning update produced no checkpoint identity change")
        if self.allowed_inference_history:
            raise ValueError(
                "successor probe must not rely on winner history outside its weights"
            )


@dataclass(frozen=True)
class CoupledSuccessorGeneration:
    """One generation joining demand, weights, product and physical capital."""

    schema_version: str
    generation_index: int
    demand_parent_state_hash: str
    demand_child_state_hash: str
    frozen_demand_forecast_hash: str
    authorized_human_outcome_hash: str
    demand_calibration_receipt_hash: str
    endorsed_guidance_receipt_hash: str | None
    parent_checkpoint_hash: str
    update_posterior: SealedFullUpdatePosterior
    successor_checkpoint_hash: str
    input_operator_hash: str
    output_operator_hash: str
    product_hash: str
    physical_execution_hash: str
    next_mrs_hash: str
    witness_hash: str

    def unsigned_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "generation_index": self.generation_index,
            "demand_parent_state_hash": self.demand_parent_state_hash,
            "demand_child_state_hash": self.demand_child_state_hash,
            "frozen_demand_forecast_hash": self.frozen_demand_forecast_hash,
            "authorized_human_outcome_hash": self.authorized_human_outcome_hash,
            "demand_calibration_receipt_hash": (
                self.demand_calibration_receipt_hash
            ),
            "endorsed_guidance_receipt_hash": (
                self.endorsed_guidance_receipt_hash
            ),
            "parent_checkpoint_hash": self.parent_checkpoint_hash,
            "update_posterior": asdict(self.update_posterior),
            "successor_checkpoint_hash": self.successor_checkpoint_hash,
            "input_operator_hash": self.input_operator_hash,
            "output_operator_hash": self.output_operator_hash,
            "product_hash": self.product_hash,
            "physical_execution_hash": self.physical_execution_hash,
            "next_mrs_hash": self.next_mrs_hash,
        }

    def validate(self) -> None:
        if self.schema_version != COUPLED_GENERATION_SCHEMA:
            raise ValueError("unsupported coupled successor generation schema")
        _require_nonnegative_int(self.generation_index, "generation_index")
        for field in (
            "demand_parent_state_hash",
            "demand_child_state_hash",
            "frozen_demand_forecast_hash",
            "authorized_human_outcome_hash",
            "demand_calibration_receipt_hash",
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
        if self.endorsed_guidance_receipt_hash is not None:
            _require_digest(
                self.endorsed_guidance_receipt_hash,
                "endorsed_guidance_receipt_hash",
            )
        if self.demand_parent_state_hash == self.demand_child_state_hash:
            raise ValueError("real outcome did not update the demand state")
        if self.input_operator_hash == self.output_operator_hash:
            raise ValueError("generation did not produce a distinct successor operator")
        self.update_posterior.validate()
        if self.parent_checkpoint_hash != self.update_posterior.parent_checkpoint_hash:
            raise ValueError("generation and update posterior bind different parents")
        if (
            self.successor_checkpoint_hash
            != self.update_posterior.successor_checkpoint_hash
        ):
            raise ValueError("generation and update posterior bind different successors")
        if self.witness_hash != digest(self.unsigned_dict()):
            raise ValueError("coupled generation witness hash mismatch")


@dataclass(frozen=True)
class CoupledSuccessorChainReport:
    valid: bool
    depth: int
    label: str | None
    demand_closed: bool
    weight_closed: bool
    physical_closed: bool
    endorsed_guidance_count: int
    reasons: tuple[str, ...]


def verify_coupled_successor_chain(
    generations: Sequence[CoupledSuccessorGeneration],
    pipe_certificates: Sequence[PIPECertificate],
    pipe_reports: Sequence[PIPEVerificationReport],
) -> CoupledSuccessorChainReport:
    """Verify a finite chain only when all three closures are present."""

    reasons: list[str] = []
    if len(generations) < 2:
        reasons.append("coupled successor claim requires at least two generations")
    if len(pipe_certificates) != len(generations):
        reasons.append("every generation requires one PIPE certificate")
    if len(pipe_reports) != len(generations):
        reasons.append("every generation requires one PIPE verification report")

    for expected_index, generation in enumerate(generations):
        try:
            generation.validate()
        except ValueError as error:
            reasons.append(f"generation {expected_index}: {error}")
        if generation.generation_index != expected_index:
            reasons.append("generation indices must be contiguous from zero")

    for index, (earlier, later) in enumerate(zip(generations, generations[1:])):
        if earlier.successor_checkpoint_hash != later.parent_checkpoint_hash:
            reasons.append(
                f"generation {index} successor weights are not generation "
                f"{index + 1} parent weights"
            )
        if earlier.output_operator_hash != later.input_operator_hash:
            reasons.append(
                f"generation {index} output operator is not generation "
                f"{index + 1} actual input operator"
            )
        if earlier.demand_child_state_hash != later.demand_parent_state_hash:
            reasons.append(
                f"generation {index} demand update is not inherited by generation "
                f"{index + 1}"
            )

    for index, report in enumerate(pipe_reports):
        if report.status is not PIPEStatus.ACCEPTED:
            reasons.append(f"generation {index} physical edge is not accepted PIPE")

    if len(pipe_certificates) == len(generations):
        for index, (generation, certificate) in enumerate(
            zip(generations, pipe_certificates)
        ):
            if certificate.treatment_hash != generation.input_operator_hash:
                reasons.append(
                    f"generation {index} PIPE treatment is not its actual input operator"
                )
            if certificate.realized_operator_hash != generation.output_operator_hash:
                reasons.append(
                    f"generation {index} PIPE output is not its realized operator"
                )
            if certificate.witness_hash != generation.physical_execution_hash:
                reasons.append(
                    f"generation {index} PIPE witness is not its physical execution"
                )
        physical_chain = verify_prsi_chain(tuple(pipe_certificates))
        reasons.extend(physical_chain.reasons)
    else:
        physical_chain = None

    demand_closed = bool(generations) and all(
        generation.demand_parent_state_hash != generation.demand_child_state_hash
        for generation in generations
    )
    weight_closed = bool(generations) and all(
        generation.parent_checkpoint_hash != generation.successor_checkpoint_hash
        for generation in generations
    )
    physical_closed = bool(
        physical_chain is not None
        and physical_chain.valid
        and len(pipe_reports) == len(generations)
        and all(report.status is PIPEStatus.ACCEPTED for report in pipe_reports)
    )
    if not demand_closed:
        reasons.append("demand state is not closed across every generation")
    if not weight_closed:
        reasons.append("weight successor is not closed across every generation")
    if not physical_closed:
        reasons.append("physical successor-production chain is not closed")

    return CoupledSuccessorChainReport(
        valid=not reasons,
        depth=len(generations),
        label=(
            f"human-demand-coupled-prsi-{len(generations)}"
            if not reasons
            else None
        ),
        demand_closed=demand_closed,
        weight_closed=weight_closed,
        physical_closed=physical_closed,
        endorsed_guidance_count=sum(
            generation.endorsed_guidance_receipt_hash is not None
            for generation in generations
        ),
        reasons=tuple(reasons),
    )


__all__ = [
    "COUPLED_GENERATION_SCHEMA",
    "UPDATE_POSTERIOR_SCHEMA",
    "CoupledSuccessorChainReport",
    "CoupledSuccessorGeneration",
    "FullUpdateCandidate",
    "SealedFullUpdatePosterior",
    "update_candidate_commitment",
    "verify_coupled_successor_chain",
]
