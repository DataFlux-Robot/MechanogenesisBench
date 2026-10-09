from __future__ import annotations

from dataclasses import replace

import pytest

from mechanogenesis_bench.canonical import digest
from mechanogenesis_bench.coupled_successor import (
    COUPLED_GENERATION_SCHEMA,
    UPDATE_POSTERIOR_SCHEMA,
    CoupledSuccessorGeneration,
    FullUpdateCandidate,
    SealedFullUpdatePosterior,
    update_candidate_commitment,
    verify_coupled_successor_chain,
)
from mechanogenesis_bench.recursive_closure import (
    PIPECertificate,
    PIPEStatus,
    PIPEVerificationReport,
)


def _hash(label: str) -> str:
    return digest({"fixture": label})


def _posterior(parent: str, successor: str, label: str) -> SealedFullUpdatePosterior:
    candidates = (
        FullUpdateCandidate(
            update_program_hash=_hash(f"{label}-u0"),
            training_receipt_hash=_hash(f"{label}-train0"),
            final_checkpoint_hash=successor,
            sealed_probe_receipt_hash=_hash(f"{label}-probe0"),
            sealed_probe_score=20,
            full_parameter_execution=True,
        ),
        FullUpdateCandidate(
            update_program_hash=_hash(f"{label}-u1"),
            training_receipt_hash=_hash(f"{label}-train1"),
            final_checkpoint_hash=_hash(f"{label}-loser"),
            sealed_probe_receipt_hash=_hash(f"{label}-probe1"),
            sealed_probe_score=10,
            full_parameter_execution=True,
        ),
    )
    evidence = _hash(f"{label}-evidence")
    return SealedFullUpdatePosterior(
        schema_version=UPDATE_POSTERIOR_SCHEMA,
        parent_checkpoint_hash=parent,
        evidence_hash=evidence,
        candidate_set_commitment_hash=update_candidate_commitment(
            parent, evidence, candidates
        ),
        candidates=candidates,
        proposal_frozen_sequence=1,
        seal_opened_sequence=2,
        winner_index=0,
        successor_checkpoint_hash=successor,
        allowed_inference_history=(),
    )


def _generation(
    index: int,
    *,
    parent: str,
    successor: str,
    demand_parent: str,
    demand_child: str,
    input_operator: str,
    output_operator: str,
) -> CoupledSuccessorGeneration:
    provisional = CoupledSuccessorGeneration(
        schema_version=COUPLED_GENERATION_SCHEMA,
        generation_index=index,
        demand_parent_state_hash=demand_parent,
        demand_child_state_hash=demand_child,
        frozen_demand_forecast_hash=_hash(f"g{index}-forecast"),
        authorized_human_outcome_hash=_hash(f"g{index}-human"),
        demand_calibration_receipt_hash=_hash(f"g{index}-calibration"),
        endorsed_guidance_receipt_hash=_hash(f"g{index}-guidance"),
        parent_checkpoint_hash=parent,
        update_posterior=_posterior(parent, successor, f"g{index}"),
        successor_checkpoint_hash=successor,
        input_operator_hash=input_operator,
        output_operator_hash=output_operator,
        product_hash=_hash(f"g{index}-product"),
        physical_execution_hash=_hash(f"g{index}-physical"),
        next_mrs_hash=_hash(f"g{index}-next-mrs"),
        witness_hash=_hash("provisional"),
    )
    return replace(provisional, witness_hash=digest(provisional.unsigned_dict()))


def _accepted_pipe_report() -> PIPEVerificationReport:
    return PIPEVerificationReport(
        status=PIPEStatus.ACCEPTED,
        reasons=(),
        post_transition_effect=2.0,
        ancestor_net_lift=1.0,
    )


def _valid_chain():
    model0, model1, model2 = _hash("m0"), _hash("m1"), _hash("m2")
    demand0, demand1, demand2 = _hash("d0"), _hash("d1"), _hash("d2")
    operator0, operator1, operator2 = _hash("o0"), _hash("o1"), _hash("o2")
    generations = (
        _generation(
            0,
            parent=model0,
            successor=model1,
            demand_parent=demand0,
            demand_child=demand1,
            input_operator=operator0,
            output_operator=operator1,
        ),
        _generation(
            1,
            parent=model1,
            successor=model2,
            demand_parent=demand1,
            demand_child=demand2,
            input_operator=operator1,
            output_operator=operator2,
        ),
    )
    certificates = tuple(
        PIPECertificate(
            treatment_hash=generation.input_operator_hash,
            realized_operator_hash=generation.output_operator_hash,
            witness_hash=generation.physical_execution_hash,
        )
        for generation in generations
    )
    reports = (_accepted_pipe_report(), _accepted_pipe_report())
    return generations, certificates, reports


def test_two_generation_chain_closes_demand_weights_and_physical_operator() -> None:
    generations, certificates, reports = _valid_chain()
    result = verify_coupled_successor_chain(generations, certificates, reports)
    assert result.valid
    assert result.label == "human-demand-coupled-prsi-2"
    assert result.demand_closed
    assert result.weight_closed
    assert result.physical_closed
    assert result.endorsed_guidance_count == 2


def test_every_update_candidate_must_be_fully_executed() -> None:
    posterior = _posterior(_hash("parent"), _hash("successor"), "incomplete")
    broken_candidate = replace(
        posterior.candidates[1], full_parameter_execution=False
    )
    broken = replace(
        posterior,
        candidates=(posterior.candidates[0], broken_candidate),
    )
    with pytest.raises(ValueError, match="every frozen update candidate"):
        broken.validate()


def test_post_selection_credit_child_cannot_replace_winning_checkpoint() -> None:
    posterior = _posterior(_hash("parent"), _hash("winner"), "credit-child")
    broken = replace(
        posterior,
        successor_checkpoint_hash=_hash("separately-trained-credit-child"),
    )
    with pytest.raises(ValueError, match="byte-identical winning"):
        broken.validate()


def test_successor_probe_must_be_weight_only() -> None:
    posterior = _posterior(_hash("parent"), _hash("successor"), "history")
    with pytest.raises(ValueError, match="outside its weights"):
        replace(posterior, allowed_inference_history=(_hash("winner-log"),)).validate()


def test_coupled_chain_rejects_broken_operator_and_demand_inheritance() -> None:
    generations, certificates, reports = _valid_chain()
    broken_second = replace(
        generations[1],
        input_operator_hash=_hash("procured-substitute"),
        demand_parent_state_hash=_hash("reset-demand-state"),
    )
    broken_second = replace(
        broken_second, witness_hash=digest(broken_second.unsigned_dict())
    )
    result = verify_coupled_successor_chain(
        (generations[0], broken_second), certificates, reports
    )
    assert not result.valid
    assert any("actual input operator" in reason for reason in result.reasons)
    assert any("demand update is not inherited" in reason for reason in result.reasons)


def test_structural_chain_cannot_replace_an_accepted_pipe() -> None:
    generations, certificates, reports = _valid_chain()
    rejected = replace(
        reports[1], status=PIPEStatus.NON_IDENTIFIABLE,
        reasons=("trusted physical validation missing",),
    )
    result = verify_coupled_successor_chain(
        generations, certificates, (reports[0], rejected)
    )
    assert not result.valid
    assert not result.physical_closed
    assert any("not accepted PIPE" in reason for reason in result.reasons)
