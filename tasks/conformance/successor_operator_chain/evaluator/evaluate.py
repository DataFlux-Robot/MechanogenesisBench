#!/usr/bin/env python3
"""Trusted evaluator for the two-generation physical successor task."""

from __future__ import annotations

import argparse
from math import ceil
import json
import os
from pathlib import Path

from mechanogenesis_bench.successor_operator import execute_successor_operator_chain
from mechanogenesis_engine.compiler import load_world
from mechanogenesis_engine.fixture_search import FixtureGoal, search_fixture
from mechanogenesis_engine.gtheta import ResearchRequest, StaticStrategyProposer
from mechanogenesis_engine.interpreter import initial_state
from mechanogenesis_engine.research_strategy import FixtureResearchStrategy
from mechanogenesis_engine.sovereign import find_sovereign_checker, verify_with_lean


def load_object(submission_path: Path, generation: dict[str, object], name: str) -> object:
    object_digest = generation["mrs"][name]
    return json.loads(
        (submission_path.parent / "objects" / f"{object_digest[7:]}.json").read_text(
            encoding="utf-8"
        )
    )


def object_path(submission_path: Path, generation: dict[str, object], name: str) -> Path:
    object_digest = generation["mrs"][name]
    return submission_path.parent / "objects" / f"{object_digest[7:]}.json"


def core_receipts(execution) -> list[dict[str, object]]:
    return [
        {
            "operation_hash": receipt.operation_hash,
            "parent_world_hash": receipt.parent_world_hash,
            "child_world_hash": receipt.child_world_hash,
            "balances": [balance.to_dict() for balance in receipt.balances],
        }
        for receipt in execution.receipts
    ]


def case_error(fixture: dict[str, object], span_um: int, *, input_error_um: int = 0) -> int:
    return (
        input_error_um
        + int(fixture["radial_clearance_um"])
        + int(fixture["reference_clearance_um"])
        + ceil(
            2
            * int(fixture["radial_clearance_um"])
            * span_um
            / int(fixture["locator_spacing_um"])
        )
        + int(fixture["manufacturing_repeatability_um"])
        + 20
        + 30
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--submission", type=Path, required=True)
    parser.add_argument("--task-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    submission = json.loads(args.submission.read_text(encoding="utf-8"))
    submitted_generations = submission.get("generations", [])
    spec = json.loads((args.task_dir / "private/spec.json").read_text(encoding="utf-8"))
    world = load_world(args.task_dir / "public/mechanism_world.json")
    goals = tuple(
        FixtureGoal.from_mapping(
            json.loads(
                (args.task_dir / f"public/fixture_goal_g{index}.json").read_text(
                    encoding="utf-8"
                )
            )
        )
        for index in range(2)
    )
    valid = len(submitted_generations) == 2
    chain = None
    strategies = []
    try:
        for generation in submitted_generations:
            language = load_object(args.submission, generation, "language")
            strategies.append(
                FixtureResearchStrategy.from_mapping(language["research_strategy"])
            )
        chain = execute_successor_operator_chain(
            world,
            goals,
            strategies,
            evaluator_contract=json.loads(
                (args.task_dir / "public/evaluator_contract.json").read_text(
                    encoding="utf-8"
                )
            ),
            max_executions=500,
        )
        checker = find_sovereign_checker(args.task_dir.parents[2])
        if checker is None:
            raise RuntimeError("Lean sovereign checker is unavailable")
        previous_program_hash = json.loads(
            (args.task_dir / "public/world.json").read_text(encoding="utf-8")
        )["baseline_process_hash"]
        for submitted, edge in zip(submitted_generations, chain.generations, strict=True):
            result = edge.run.search_result
            verify_with_lean(
                object_path(args.submission, submitted, "compiler_certificate"), checker
            )
            fixture = result.execution.final_state["capabilities"][
                result.fixture_capability_id
            ]
            output_operator = result.execution.final_state["capabilities"][
                result.qualified_process_capability_id
            ]
            expected_artifact = {
                "artifact_type": "successor_metrology_operator",
                "generation": edge.index,
                "selected_parameters": result.selected_parameters,
                "fixture_capability_id": result.fixture_capability_id,
                "fixture_capability": fixture,
                "input_operator_id": edge.input_operator_id,
                "input_operator_hash": edge.input_operator_hash,
                "output_operator_id": edge.output_operator_id,
                "output_operator_hash": edge.output_operator_hash,
                "output_operator": output_operator,
                "used_input_operator": edge.used_input_operator,
                "product_absolute_frame_error_um": edge.product_absolute_frame_error_um,
                "program_hash": edge.program_hash,
                "child_world_hash": edge.child_world_hash,
                "research_strategy_hash": edge.run.strategy.strategy_hash,
            }
            valid = valid and submitted["artifact"] == expected_artifact
            valid = valid and submitted["parent_process_hash"] == previous_program_hash
            valid = valid and submitted["child_process_hash"] == edge.program_hash
            valid = valid and submitted["parent_world_hash"] == edge.parent_world_hash
            valid = valid and submitted["child_world_hash"] == edge.child_world_hash
            valid = valid and submitted["construction_receipts"] == core_receipts(
                result.execution
            )
            valid = valid and submitted["experiment_receipts"] == [edge.to_receipt()]
            previous_program_hash = edge.program_hash
    except Exception:
        valid = False

    decisions = []
    if valid and chain is not None:
        first, second = chain.generations
        fixtures = [
            edge.run.search_result.execution.final_state["capabilities"][
                edge.run.search_result.fixture_capability_id
            ]
            for edge in chain.generations
        ]
        first_errors = [
            case_error(fixtures[0], span)
            for span in spec["generation_0_held_out_spans_um"]
        ]
        second_errors = [
            case_error(
                fixtures[1],
                span,
                input_error_um=second.input_position_error_um,
            )
            for span in spec["generation_1_held_out_spans_um"]
        ]
        no_inheritance = search_fixture(
            world,
            goals[1],
            parent_state=initial_state(world),
            namespace="counterfactual",
            strategy=strategies[1],
        )
        no_fixture = no_inheritance.execution.final_state["capabilities"][
            no_inheritance.fixture_capability_id
        ]
        counterfactual_errors = [
            case_error(no_fixture, span, input_error_um=800)
            for span in spec["generation_1_held_out_spans_um"]
        ]
        first_robustness = sum(
            value <= spec["generation_0_max_relative_error_um"]
            for value in first_errors
        ) / len(first_errors)
        second_robustness = sum(
            value <= spec["generation_1_max_absolute_frame_error_um"]
            for value in second_errors
        ) / len(second_errors)
        inheritance_advantage = max(counterfactual_errors) - max(second_errors)
        accepted = [
            first.output_position_error_um < first.input_position_error_um
            and first_robustness >= 0.8,
            second.output_position_error_um < second.input_position_error_um
            and second.used_input_operator
            and second_robustness >= 0.8
            and inheritance_advantage >= spec["minimum_inheritance_advantage_um"],
        ]
        before_after = [
            (-float(first.input_position_error_um), -float(first.output_position_error_um)),
            (-float(max(counterfactual_errors)), -float(max(second_errors))),
        ]
        robustness = [first_robustness, second_robustness]
        for index, edge in enumerate(chain.generations):
            consumed_mass = sum(
                balance.input_q
                for receipt in edge.run.search_result.execution.receipts
                if receipt.operation in {"machine_part", "consume_component"}
                for balance in receipt.balances
            )
            gain = before_after[index][1] - before_after[index][0]
            net_value = (
                gain
                * int(spec["reuse_count"])
                * int(spec["value_per_um_improvement_milliusd"])
                - consumed_mass * int(spec["material_cost_milliusd_per_mg"])
            )
            decisions.append(
                {
                    "index": index,
                    "artifact_hash": submitted_generations[index]["artifact_hash"],
                    "accepted": accepted[index] and net_value > 0,
                    "before_upper": before_after[index][0],
                    "after_lower": before_after[index][1],
                    "margin": float(spec["minimum_operator_improvement_um"]),
                    "net_value": float(net_value),
                    "robustness_pass_rate": robustness[index],
                    "evidence_tier": "conformance",
                    "rrc_time_rate_delta": 0.0,
                    "rrc_budget_rate_delta": 0.0,
                }
            )
    else:
        for index, generation in enumerate(submitted_generations[:2]):
            decisions.append(
                {
                    "index": index,
                    "artifact_hash": generation["artifact_hash"],
                    "accepted": False,
                    "before_upper": 0.0,
                    "after_lower": 0.0,
                    "margin": 1.0,
                    "net_value": -1.0,
                    "robustness_pass_rate": 0.0,
                    "evidence_tier": "conformance",
                    "rrc_time_rate_delta": 0.0,
                    "rrc_budget_rate_delta": 0.0,
                }
            )

    args.output.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "task_id": "conformance.successor_operator_chain",
                "task_package_digest": os.environ["MBENCH_TASK_PACKAGE_DIGEST"],
                "evaluator_digest": os.environ["MBENCH_EVALUATOR_BUNDLE_DIGEST"],
                "decisions": decisions,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
