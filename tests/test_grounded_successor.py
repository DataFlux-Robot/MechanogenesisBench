from __future__ import annotations

from dataclasses import replace

import pytest

from mechanogenesis_bench.canonical import digest
from mechanogenesis_bench.coupled_successor import (
    UPDATE_POSTERIOR_SCHEMA,
    FullUpdateCandidate,
    SealedFullUpdatePosterior,
    update_candidate_commitment,
)
from mechanogenesis_bench.grounded_successor import (
    DEMAND_BELIEF_UPDATE_SCHEMA,
    GROUNDED_JOINT_GENERATION_SCHEMA,
    GroundedDemandBeliefUpdate,
    GroundedJointSuccessorGeneration,
    joint_evidence_commitment,
    verify_grounded_joint_successor_chain,
)
from mechanogenesis_bench.human_demand import (
    DEMAND_CLOSURE_SCHEMA,
    DEMAND_FORECAST_SCHEMA,
    HUMAN_OUTCOME_SCHEMA,
    AuthorizedHumanOutcome,
    HumanDemandClosureReceipt,
    HumanDemandForecast,
    categorical_brier_sum_ppm2,
)
from mechanogenesis_bench.recursive_closure import (
    PIPECertificate,
    PIPEStatus,
    PIPEVerificationReport,
)


def _hash(label: str) -> str:
    return digest({"fixture": label})


def _forecast(model: str, label: str, sequence: int) -> HumanDemandForecast:
    provisional = HumanDemandForecast(
        schema_version=DEMAND_FORECAST_SCHEMA,
        population_commitment_hash=_hash("population"),
        opportunity_set_hash=_hash(f"{label}-opportunity"),
        selected_action_hash=_hash(f"{label}-action"),
        outcome_probabilities_ppm=(("adopted", 600_000), ("rejected", 400_000)),
        uncertainty_ppm=100_000,
        model_hash=model,
        adapter_hash=_hash("registered-demand-adapter"),
        frozen_sequence=sequence,
        source_kind="authorized_historical",
        forecast_hash=_hash("provisional"),
    )
    return replace(provisional, forecast_hash=digest(provisional.unsigned_dict()))


def _outcome(
    forecast: HumanDemandForecast, product: str, sequence: int
) -> AuthorizedHumanOutcome:
    provisional = AuthorizedHumanOutcome(
        schema_version=HUMAN_OUTCOME_SCHEMA,
        population_commitment_hash=forecast.population_commitment_hash,
        action_hash=forecast.selected_action_hash,
        product_hash=product,
        realized_outcome="adopted",
        source_kind="authorized_prospective",
        consent_receipt_hash=_hash("consent"),
        evaluator_hash=_hash("independent-human-evaluator"),
        evaluator_owned_by_candidate=False,
        observed_sequence=sequence,
        utility_lower_micro=700_000,
        utility_upper_micro=740_000,
        rights_passed=True,
        safety_passed=True,
        opt_out_available=True,
        outcome_hash=_hash("provisional"),
    )
    return replace(provisional, outcome_hash=digest(provisional.unsigned_dict()))


class _DemandRuntime:
    trainer_hash = _hash("registered-joint-trainer")
    evaluator_hash = _hash("registered-holdout-evaluator")

    def __init__(self, parent: str, child: str, trainer_receipt: str):
        self.parent = parent
        self.child = child
        self.trainer_receipt = trainer_receipt

    def training_input_hash(self, closure_hashes):
        return digest({"ordered_demand_closures": list(closure_hashes)})

    def replay_update(self, parent, training_input):
        assert parent == self.parent
        return self.child, self.trainer_receipt

    def holdout_brier(self, checkpoint, holdout):
        assert holdout == _hash("sealed-human-holdout")
        if checkpoint == self.parent:
            return 40, _hash(f"{self.parent}-before")
        assert checkpoint == self.child
        return 20, _hash(f"{self.child}-after")


def _generation(
    index: int,
    *,
    parent: str,
    successor: str,
    forecast: HumanDemandForecast,
    successor_forecast: HumanDemandForecast,
    input_operator: str,
    output_operator: str,
) -> tuple[GroundedJointSuccessorGeneration, _DemandRuntime]:
    product = _hash(f"g{index}-product")
    physical = _hash(f"g{index}-physical")
    trainer_receipt = _hash(f"g{index}-joint-training")
    outcome = _outcome(forecast, product, forecast.frozen_sequence + 3)
    provisional_closure = HumanDemandClosureReceipt(
        schema_version=DEMAND_CLOSURE_SCHEMA,
        parent_demand_state_hash=parent,
        child_demand_state_hash=successor,
        forecast=forecast,
        outcome=outcome,
        forecast_brier_sum_ppm2=categorical_brier_sum_ppm2(
            forecast.outcome_probabilities_ppm, outcome.realized_outcome
        ),
        update_training_receipt_hash=trainer_receipt,
        closure_hash=_hash("provisional"),
    )
    closure = replace(
        provisional_closure,
        closure_hash=digest(provisional_closure.unsigned_dict()),
    )
    evidence = joint_evidence_commitment(
        demand_closure_hash=closure.closure_hash,
        product_hash=product,
        physical_execution_hash=physical,
        realized_operator_hash=output_operator,
    )
    candidates = (
        FullUpdateCandidate(
            update_program_hash=_hash(f"g{index}-u0"),
            training_receipt_hash=trainer_receipt,
            final_checkpoint_hash=successor,
            sealed_probe_receipt_hash=_hash(f"g{index}-probe0"),
            sealed_probe_score=20,
            full_parameter_execution=True,
        ),
        FullUpdateCandidate(
            update_program_hash=_hash(f"g{index}-u1"),
            training_receipt_hash=_hash(f"g{index}-loser-training"),
            final_checkpoint_hash=_hash(f"g{index}-loser-checkpoint"),
            sealed_probe_receipt_hash=_hash(f"g{index}-probe1"),
            sealed_probe_score=10,
            full_parameter_execution=True,
        ),
    )
    posterior = SealedFullUpdatePosterior(
        schema_version=UPDATE_POSTERIOR_SCHEMA,
        parent_checkpoint_hash=parent,
        evidence_hash=evidence,
        candidate_set_commitment_hash=update_candidate_commitment(
            parent, evidence, candidates
        ),
        candidates=candidates,
        proposal_frozen_sequence=outcome.observed_sequence + 1,
        seal_opened_sequence=outcome.observed_sequence + 2,
        winner_index=0,
        successor_checkpoint_hash=successor,
        allowed_inference_history=(),
    )
    runtime = _DemandRuntime(parent, successor, trainer_receipt)
    provisional_update = GroundedDemandBeliefUpdate(
        schema_version=DEMAND_BELIEF_UPDATE_SCHEMA,
        parent_checkpoint_hash=parent,
        successor_checkpoint_hash=successor,
        calibration_closure_hashes=(closure.closure_hash,),
        training_input_hash=runtime.training_input_hash((closure.closure_hash,)),
        trainer_receipt_hash=trainer_receipt,
        trainer_implementation_hash=runtime.trainer_hash,
        evaluator_implementation_hash=runtime.evaluator_hash,
        holdout_commitment_hash=_hash("sealed-human-holdout"),
        holdout_brier_before=40,
        holdout_brier_after=20,
        holdout_before_receipt_hash=_hash(f"{parent}-before"),
        holdout_after_receipt_hash=_hash(f"{successor}-after"),
        full_parameter_execution=True,
        allowed_inference_history=(),
        receipt_hash=_hash("provisional"),
    )
    demand_update = replace(
        provisional_update,
        receipt_hash=digest(provisional_update.unsigned_dict()),
    )
    provisional = GroundedJointSuccessorGeneration(
        schema_version=GROUNDED_JOINT_GENERATION_SCHEMA,
        generation_index=index,
        parent_checkpoint_hash=parent,
        successor_checkpoint_hash=successor,
        demand_closure=closure,
        demand_belief_update=demand_update,
        successor_demand_forecast=successor_forecast,
        update_posterior=posterior,
        input_operator_hash=input_operator,
        output_operator_hash=output_operator,
        product_hash=product,
        physical_execution_hash=physical,
        next_mrs_hash=_hash(f"g{index}-next-mrs"),
        endorsed_positive_surprise=None,
        witness_hash=_hash("provisional"),
    )
    return (
        replace(provisional, witness_hash=digest(provisional.unsigned_dict())),
        runtime,
    )


def _valid_chain():
    m0, m1, m2 = _hash("m0"), _hash("m1"), _hash("m2")
    o0, o1, o2 = _hash("o0"), _hash("o1"), _hash("o2")
    f0 = _forecast(m0, "g0", 2)
    f1 = _forecast(m1, "g1", 8)
    f2 = _forecast(m2, "g2", 14)
    g0, r0 = _generation(
        0,
        parent=m0,
        successor=m1,
        forecast=f0,
        successor_forecast=f1,
        input_operator=o0,
        output_operator=o1,
    )
    g1, r1 = _generation(
        1,
        parent=m1,
        successor=m2,
        forecast=f1,
        successor_forecast=f2,
        input_operator=o1,
        output_operator=o2,
    )
    generations = (g0, g1)
    certificates = tuple(
        PIPECertificate(
            treatment_hash=g.input_operator_hash,
            realized_operator_hash=g.output_operator_hash,
            witness_hash=g.physical_execution_hash,
        )
        for g in generations
    )
    reports = tuple(
        PIPEVerificationReport(
            status=PIPEStatus.ACCEPTED,
            reasons=(),
            post_transition_effect=2.0,
            ancestor_net_lift=1.0,
        )
        for _ in generations
    )
    return generations, (r0, r1), certificates, reports


def test_two_generation_joint_chain_replays_demand_weights_and_operator() -> None:
    result = verify_grounded_joint_successor_chain(*_valid_chain())
    assert result.valid
    assert result.label == "grounded-joint-prsi-2"
    assert result.demand_calibration_improved
    assert result.exact_weight_identity
    assert result.physical_successor_closed


def test_hash_change_cannot_impersonate_demand_calibration_improvement() -> None:
    generations, runtimes, certificates, reports = _valid_chain()
    broken_update = replace(
        generations[0].demand_belief_update,
        holdout_brier_after=50,
    )
    broken = replace(generations[0], demand_belief_update=broken_update)
    result = verify_grounded_joint_successor_chain(
        (broken, generations[1]), runtimes, certificates, reports
    )
    assert not result.valid
    assert any("calibration did not improve" in reason for reason in result.reasons)


def test_external_forecast_cannot_be_claimed_as_weight_internalization() -> None:
    generations, runtimes, certificates, reports = _valid_chain()
    original = generations[0]
    wrong_forecast = replace(
        original.demand_closure.forecast,
        model_hash=_hash("glm-5.3-flash"),
    )
    wrong_forecast = replace(
        wrong_forecast, forecast_hash=digest(wrong_forecast.unsigned_dict())
    )
    wrong_closure = replace(original.demand_closure, forecast=wrong_forecast)
    wrong_closure = replace(
        wrong_closure, closure_hash=digest(wrong_closure.unsigned_dict())
    )
    wrong_update = replace(
        original.demand_belief_update,
        calibration_closure_hashes=(wrong_closure.closure_hash,),
        training_input_hash=runtimes[0].training_input_hash(
            (wrong_closure.closure_hash,)
        ),
    )
    wrong_update = replace(
        wrong_update, receipt_hash=digest(wrong_update.unsigned_dict())
    )
    wrong_evidence = joint_evidence_commitment(
        demand_closure_hash=wrong_closure.closure_hash,
        product_hash=original.product_hash,
        physical_execution_hash=original.physical_execution_hash,
        realized_operator_hash=original.output_operator_hash,
    )
    wrong_posterior = replace(original.update_posterior, evidence_hash=wrong_evidence)
    wrong_posterior = replace(
        wrong_posterior,
        candidate_set_commitment_hash=update_candidate_commitment(
            wrong_posterior.parent_checkpoint_hash,
            wrong_evidence,
            wrong_posterior.candidates,
        ),
    )
    broken = replace(
        original,
        demand_closure=wrong_closure,
        demand_belief_update=wrong_update,
        update_posterior=wrong_posterior,
    )
    result = verify_grounded_joint_successor_chain(
        (broken, generations[1]), runtimes, certificates, reports
    )
    assert not result.valid
    assert any("not emitted by parent G-theta" in reason for reason in result.reasons)


def test_synthetic_outcome_cannot_close_the_joint_claim() -> None:
    generations, runtimes, certificates, reports = _valid_chain()
    synthetic = replace(generations[0].demand_closure.outcome, source_kind="synthetic")
    broken_closure = replace(generations[0].demand_closure, outcome=synthetic)
    broken = replace(generations[0], demand_closure=broken_closure)
    result = verify_grounded_joint_successor_chain(
        (broken, generations[1]), runtimes, certificates, reports
    )
    assert not result.valid
    assert any("not an authorized human outcome" in reason for reason in result.reasons)


def test_post_selection_credit_child_cannot_be_the_joint_successor() -> None:
    generations, runtimes, certificates, reports = _valid_chain()
    outside = replace(
        generations[0].demand_belief_update,
        successor_checkpoint_hash=_hash("post-selection-credit-child"),
    )
    outside = replace(outside, receipt_hash=digest(outside.unsigned_dict()))
    broken = replace(generations[0], demand_belief_update=outside)
    result = verify_grounded_joint_successor_chain(
        (broken, generations[1]), runtimes, certificates, reports
    )
    assert not result.valid
    assert any("does not replay" in reason for reason in result.reasons)


def test_successor_forecast_must_be_used_by_the_next_generation() -> None:
    generations, runtimes, certificates, reports = _valid_chain()
    alternate = _forecast(generations[1].parent_checkpoint_hash, "alternate", 8)
    broken_second = replace(
        generations[1],
        demand_closure=replace(generations[1].demand_closure, forecast=alternate),
    )
    result = verify_grounded_joint_successor_chain(
        (generations[0], broken_second), runtimes, certificates, reports
    )
    assert not result.valid
    assert any("successor demand forecast is not used" in reason for reason in result.reasons)
