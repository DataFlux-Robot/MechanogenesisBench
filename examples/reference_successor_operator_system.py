#!/usr/bin/env python3
"""Deterministic reference system for the two-generation successor task."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tomllib

from mechanogenesis_bench.canonical import digest
from mechanogenesis_bench.successor_operator import execute_successor_operator_chain
from mechanogenesis_engine.compiler import load_world
from mechanogenesis_engine.fixture_search import FixtureGoal
from mechanogenesis_engine.gtheta import ReferenceResearchProposer, ResearchRequest


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def store_object(store: Path, value: object) -> str:
    object_digest = digest(value)
    write_json(store / f"{object_digest[7:]}.json", value)
    return object_digest


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


def main() -> int:
    task_root = Path(os.environ["MBENCH_TASK_DIR"])
    public = task_root / "public"
    output = Path(os.environ["MBENCH_OUTPUT_DIR"])
    store = output / "objects"
    store.mkdir(parents=True, exist_ok=True)
    with (task_root / "task.toml").open("rb") as stream:
        manifest = tomllib.load(stream)

    world = load_world(public / "mechanism_world.json")
    world_contract = json.loads((public / "world.json").read_text(encoding="utf-8"))
    evaluator_contract = json.loads(
        (public / "evaluator_contract.json").read_text(encoding="utf-8")
    )
    briefs = json.loads((public / "demand_briefs.json").read_text(encoding="utf-8"))[
        "briefs"
    ]
    goals = tuple(
        FixtureGoal.from_mapping(
            json.loads(
                (public / f"fixture_goal_g{index}.json").read_text(encoding="utf-8")
            )
        )
        for index in range(2)
    )
    proposer = ReferenceResearchProposer()
    strategies = tuple(
        proposer.propose(
            ResearchRequest(
                mission=json.dumps(briefs[index], sort_keys=True),
                world=world,
                goal=goals[index],
                max_executions=int(manifest["budget"]["attempts"]) // 2,
            )
        )
        for index in range(2)
    )
    chain = execute_successor_operator_chain(
        world,
        goals,
        strategies,
        missions=tuple(json.dumps(item, sort_keys=True) for item in briefs),
        evaluator_contract=evaluator_contract,
        max_executions=int(manifest["budget"]["attempts"]) // 2,
    )

    generations: list[dict[str, object]] = []
    total_attempts = 0
    total_energy_mj = 0
    total_mass_mg = 0
    parent_process_hash = world_contract["baseline_process_hash"]
    for edge in chain.generations:
        result = edge.run.search_result
        mrs = {
            name: store_object(store, value)
            for name, value in edge.run.mrs_objects.items()
        }
        fixture = result.execution.final_state["capabilities"][
            result.fixture_capability_id
        ]
        output_operator = result.execution.final_state["capabilities"][
            result.qualified_process_capability_id
        ]
        artifact = {
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
        generations.append(
            {
                "index": edge.index,
                "parent_process_hash": parent_process_hash,
                "child_process_hash": edge.program_hash,
                "parent_world_hash": edge.parent_world_hash,
                "child_world_hash": edge.child_world_hash,
                "mrs": mrs,
                "artifact": artifact,
                "artifact_hash": digest(artifact),
                "construction_receipts": core_receipts(result.execution),
                "experiment_receipts": [edge.to_receipt()],
            }
        )
        parent_process_hash = edge.program_hash
        total_attempts += result.attempted_candidates
        total_energy_mj += result.execution.total_energy_mj
        total_mass_mg += sum(
            balance.input_q
            for receipt in result.execution.receipts
            if receipt.operation in {"machine_part", "consume_component"}
            for balance in receipt.balances
        )

    write_json(
        Path(os.environ["MBENCH_SUBMISSION_PATH"]),
        {
            "schema_version": "0.1",
            "system_name": "reference-successor-operator",
            "system_version": "0.1.0",
            "declared_evidence_tier": "conformance",
            "resource_use": {
                "wall_time_s": 0.0,
                "monetary_cost_usd": 0.0,
                "tokens": 0,
                "energy_j": total_energy_mj / 1000.0,
                "material_kg": total_mass_mg / 1_000_000.0,
                "human_intervention_s": 0.0,
                "attempts": total_attempts,
            },
            "generations": generations,
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
