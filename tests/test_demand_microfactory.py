from __future__ import annotations

import json
from pathlib import Path

import pytest

from mechanogenesis_bench.canonical import digest
from mechanogenesis_bench.demand_microfactory import (
    MicrofactoryPlan,
    OperatorBundle,
    evaluate_demand_outcome,
    execute_plan,
    product_metrics,
    reference_plan,
)
from mechanogenesis_bench.errors import SchemaError


ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "tasks/simulation/demand_driven_microfactory"


def _inputs():
    public = TASK / "public"
    world = json.loads((public / "world.json").read_text())
    observations = json.loads(
        (public / "demand_observations.json").read_text()
    )["generations"]
    operator = OperatorBundle.from_mapping(world["initial_operator_bundle"])
    return world, observations, operator


def test_plan_requires_exact_available_operator_hash() -> None:
    world, observations, operator = _inputs()
    plan = reference_plan(
        generation=0,
        input_operator=operator,
        observations=observations[0]["comparisons"],
    )
    raw = plan.to_dict()
    raw["input_operator_bundle_hash"] = "sha256:" + "f" * 64
    wrong = MicrofactoryPlan.from_mapping(raw)
    with pytest.raises(SchemaError, match="exact available operator"):
        execute_plan(
            wrong,
            operator,
            parent_world_hash=world["baseline_world_hash"],
            capital_budget_milliusd=65_000_000,
        )


def test_three_operator_inheritance_changes_successor_physical_quality() -> None:
    world, observations, operator = _inputs()
    first = reference_plan(
        generation=0,
        input_operator=operator,
        observations=observations[0]["comparisons"],
    )
    first_execution = execute_plan(
        first,
        operator,
        parent_world_hash=world["baseline_world_hash"],
        capital_budget_milliusd=65_000_000,
    )
    second = reference_plan(
        generation=1,
        input_operator=first_execution.output_operator,
        observations=observations[1]["comparisons"],
    )
    inherited = product_metrics(second.product, first_execution.output_operator)
    procured_counterfactual = product_metrics(second.product, operator)
    assert inherited["physical_quality_ppm"] > procured_counterfactual[
        "physical_quality_ppm"
    ]
    assert first_execution.output_operator.parent_bundle_hash == operator.bundle_hash


def test_synthetic_delight_cannot_become_human_endorsement() -> None:
    world, observations, operator = _inputs()
    plan = reference_plan(
        generation=0,
        input_operator=operator,
        observations=observations[0]["comparisons"],
    )
    execution = execute_plan(
        plan,
        operator,
        parent_world_hash=world["baseline_world_hash"],
        capital_budget_milliusd=65_000_000,
    )
    outcome = evaluate_demand_outcome(
        plan,
        execution.metrics,
        {
            "accessibility": 150000,
            "cargo": 360000,
            "range": 230000,
            "repairability": 200000,
            "weather": 60000,
        },
        latent_novel_affordance="self_leveling_cargo",
    )
    assert outcome["synthetic_positive_surprise_proxy"]
    assert outcome["human_endorsed_positive_surprise"] is False
    assert digest(outcome).startswith("sha256:")
