from __future__ import annotations

import json
from pathlib import Path

from mechanogenesis_bench.successor_operator import execute_successor_operator_chain
from mechanogenesis_engine.fixture_search import FixtureGoal, search_fixture
from mechanogenesis_engine.gtheta import ReferenceResearchProposer, ResearchRequest
from mechanogenesis_engine.interpreter import initial_state
from mechanogenesis_engine.ir import WorldSpec


ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "tasks/conformance/generated_metrology_fixture/public"


def _world() -> WorldSpec:
    raw = json.loads((PUBLIC / "mechanism_world.json").read_text(encoding="utf-8"))
    for item in raw["inventory"]:
        item["quantity"] *= 2
    return WorldSpec.from_mapping(raw)


def _goals() -> tuple[FixtureGoal, FixtureGoal]:
    first = json.loads((PUBLIC / "fixture_goal.json").read_text(encoding="utf-8"))
    second = dict(first)
    second.update(
        {
            "max_worst_case_error_um": 120,
            "pin_spacing_candidates_um": [70_000, 80_000, 90_000],
            "bore_clearance_candidates_um": [5, 10, 15],
        }
    )
    return FixtureGoal.from_mapping(first), FixtureGoal.from_mapping(second)


def _strategies(world: WorldSpec, goals: tuple[FixtureGoal, FixtureGoal]):
    proposer = ReferenceResearchProposer()
    return tuple(
        proposer.propose(
            ResearchRequest(
                mission=f"generation {index}",
                world=world,
                goal=goal,
                max_executions=500,
            )
        )
        for index, goal in enumerate(goals)
    )


def test_previous_operator_is_actually_used_to_make_its_successor() -> None:
    world = _world()
    goals = _goals()
    chain = execute_successor_operator_chain(world, goals, _strategies(world, goals))

    first, second = chain.generations
    assert first.input_position_error_um == 800
    assert first.output_position_error_um == 140
    assert second.input_operator_id == first.output_operator_id
    assert second.input_operator_hash == first.output_operator_hash
    assert second.used_input_operator
    assert second.output_position_error_um == 87
    assert second.product_absolute_frame_error_um == 217
    assert chain.strict_operator_improvements == 2


def test_inherited_operator_beats_procured_baseline_on_successor_product() -> None:
    world = _world()
    goals = _goals()
    strategies = _strategies(world, goals)
    chain = execute_successor_operator_chain(world, goals, strategies)

    no_inheritance = search_fixture(
        world,
        goals[1],
        parent_state=initial_state(world),
        namespace="counterfactual",
        strategy=strategies[1],
    )
    counterfactual_fixture = no_inheritance.execution.final_state["capabilities"][
        no_inheritance.fixture_capability_id
    ]
    assert counterfactual_fixture["absolute_frame_error_um"] == 877
    assert chain.final_product_absolute_frame_error_um == 217
    assert (
        counterfactual_fixture["absolute_frame_error_um"]
        - chain.final_product_absolute_frame_error_um
        == 660
    )


def test_chain_receipt_binds_operator_and_world_identity() -> None:
    world = _world()
    goals = _goals()
    chain = execute_successor_operator_chain(world, goals, _strategies(world, goals))
    first, second = chain.generations

    first_receipt = first.to_receipt()
    second_receipt = second.to_receipt()
    assert first_receipt["output_operator_hash"] == second_receipt["input_operator_hash"]
    assert first_receipt["child_world_hash"] == second_receipt["parent_world_hash"]
    assert second_receipt["used_input_operator"] is True
