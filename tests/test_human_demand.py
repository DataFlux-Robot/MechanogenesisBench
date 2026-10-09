from __future__ import annotations

from dataclasses import replace

import pytest

from mechanogenesis_bench.canonical import digest
from mechanogenesis_bench.human_demand import (
    DEMAND_CLOSURE_SCHEMA,
    DEMAND_FORECAST_SCHEMA,
    ENDORSED_SURPRISE_SCHEMA,
    HUMAN_OUTCOME_SCHEMA,
    AuthorizedHumanOutcome,
    EndorsedPositiveSurprise,
    HumanDemandClosureReceipt,
    HumanDemandForecast,
    categorical_brier_sum_ppm2,
)


def _hash(label: str) -> str:
    return digest({"fixture": label})


def _forecast() -> HumanDemandForecast:
    provisional = HumanDemandForecast(
        schema_version=DEMAND_FORECAST_SCHEMA,
        population_commitment_hash=_hash("population"),
        opportunity_set_hash=_hash("opportunities"),
        selected_action_hash=_hash("action"),
        outcome_probabilities_ppm=(("adopted", 600_000), ("rejected", 400_000)),
        uncertainty_ppm=100_000,
        model_hash=_hash("demand-model"),
        adapter_hash=_hash("demand-adapter"),
        frozen_sequence=2,
        source_kind="synthetic",
        forecast_hash=_hash("provisional"),
    )
    return replace(provisional, forecast_hash=digest(provisional.unsigned_dict()))


def _outcome() -> AuthorizedHumanOutcome:
    provisional = AuthorizedHumanOutcome(
        schema_version=HUMAN_OUTCOME_SCHEMA,
        population_commitment_hash=_hash("population"),
        action_hash=_hash("action"),
        product_hash=_hash("product"),
        realized_outcome="adopted",
        source_kind="authorized_prospective",
        consent_receipt_hash=_hash("consent"),
        evaluator_hash=_hash("human-evaluator"),
        evaluator_owned_by_candidate=False,
        observed_sequence=5,
        utility_lower_micro=700_000,
        utility_upper_micro=740_000,
        rights_passed=True,
        safety_passed=True,
        opt_out_available=True,
        outcome_hash=_hash("provisional"),
    )
    return replace(provisional, outcome_hash=digest(provisional.unsigned_dict()))


def _closure() -> HumanDemandClosureReceipt:
    forecast = _forecast()
    outcome = _outcome()
    provisional = HumanDemandClosureReceipt(
        schema_version=DEMAND_CLOSURE_SCHEMA,
        parent_demand_state_hash=_hash("demand-parent"),
        child_demand_state_hash=_hash("demand-child"),
        forecast=forecast,
        outcome=outcome,
        forecast_brier_sum_ppm2=categorical_brier_sum_ppm2(
            forecast.outcome_probabilities_ppm, outcome.realized_outcome
        ),
        update_training_receipt_hash=_hash("demand-update"),
        closure_hash=_hash("provisional"),
    )
    return replace(provisional, closure_hash=digest(provisional.unsigned_dict()))


def _surprise() -> EndorsedPositiveSurprise:
    provisional = EndorsedPositiveSurprise(
        schema_version=ENDORSED_SURPRISE_SCHEMA,
        demand_closure_hash=_closure().closure_hash,
        product_hash=_hash("product"),
        novel_affordance_receipt_hash=_hash("novel-affordance"),
        best_known_utility_upper_micro=500_000,
        product_utility_lower_micro=700_000,
        required_gain_micro=100_000,
        metapreference_endorsement_ppm=800_000,
        required_endorsement_ppm=700_000,
        delayed_persistence_ppm=750_000,
        required_persistence_ppm=700_000,
        disclosed_alternatives=True,
        non_coercive=True,
        independent_evaluator=True,
        receipt_hash=_hash("provisional"),
    )
    return replace(provisional, receipt_hash=digest(provisional.unsigned_dict()))


def test_real_outcome_closes_a_frozen_demand_forecast() -> None:
    closure = _closure()
    closure.validate()
    assert closure.forecast.source_kind == "synthetic"
    assert closure.outcome.source_kind == "authorized_prospective"


def test_synthetic_persona_cannot_certify_human_outcome() -> None:
    with pytest.raises(ValueError, match="not an authorized human outcome"):
        replace(_outcome(), source_kind="synthetic").validate()


def test_candidate_owned_human_evaluator_is_rejected() -> None:
    with pytest.raises(ValueError, match="candidate-owned"):
        replace(_outcome(), evaluator_owned_by_candidate=True).validate()


def test_demand_forecast_must_precede_observation_and_bind_action() -> None:
    closure = _closure()
    early = replace(closure.outcome, observed_sequence=1)
    early = replace(early, outcome_hash=digest(early.unsigned_dict()))
    with pytest.raises(ValueError, match="before the forecast froze"):
        replace(closure, outcome=early).validate()
    wrong = replace(closure.outcome, action_hash=_hash("other-action"))
    wrong = replace(wrong, outcome_hash=digest(wrong.unsigned_dict()))
    with pytest.raises(ValueError, match="differs from the frozen"):
        replace(closure, outcome=wrong).validate()


def test_positive_surprise_requires_gain_endorsement_and_persistence() -> None:
    surprise = _surprise()
    surprise.validate()
    with pytest.raises(ValueError, match="best known utility"):
        replace(surprise, product_utility_lower_micro=550_000).validate()
    with pytest.raises(ValueError, match="metapreference"):
        replace(surprise, metapreference_endorsement_ppm=600_000).validate()
    with pytest.raises(ValueError, match="delayed"):
        replace(surprise, delayed_persistence_ppm=600_000).validate()


def test_surprise_cannot_be_declared_without_anti_manipulation_controls() -> None:
    with pytest.raises(ValueError, match="anti-manipulation"):
        replace(_surprise(), non_coercive=False).validate()
