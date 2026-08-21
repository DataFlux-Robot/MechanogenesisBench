#!/usr/bin/env python3
"""Executable search baseline for canonical fixture generation."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tomllib

from mechanogenesis_bench.canonical import digest
from mechanogenesis_engine.compiler import load_world
from mechanogenesis_engine.fixture_search import FixtureGoal
from mechanogenesis_engine.gtheta import (
    GThetaRuntime,
    ReferenceResearchProposer,
    ResearchRequest,
)


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def store_object(store: Path, value: object) -> str:
    object_digest = digest(value)
    write_json(store / f"{object_digest[7:]}.json", value)
    return object_digest


def main() -> int:
    public_root = Path(os.environ["MBENCH_TASK_DIR"]) / "public"
    output = Path(os.environ["MBENCH_OUTPUT_DIR"])
    store = output / "objects"
    store.mkdir(parents=True, exist_ok=True)
    world = load_world(public_root / "mechanism_world.json")
    raw_goal = json.loads((public_root / "fixture_goal.json").read_text(encoding="utf-8"))
    benchmark_world = json.loads(
        (public_root / "world.json").read_text(encoding="utf-8")
    )
    goal = FixtureGoal.from_mapping(raw_goal)
    with (public_root.parent / "task.toml").open("rb") as handle:
        manifest = tomllib.load(handle)
    evaluator_contract = json.loads(
        (public_root / "evaluator_contract.json").read_text(encoding="utf-8")
    )
    request = ResearchRequest(
        mission=(public_root.parent / "mission.md").read_text(encoding="utf-8"),
        world=world,
        goal=goal,
        max_executions=int(manifest["budget"]["attempts"]),
    )
    research = GThetaRuntime(ReferenceResearchProposer()).run_fixture(
        request, evaluator_contract=evaluator_contract
    )
    result = research.search_result
    assert result.qualified_process_capability_id is not None
    mrs = {
        name: store_object(store, value)
        for name, value in research.mrs_objects.items()
    }
    capability = result.execution.final_state["capabilities"]["generated_fixture_metrology"]
    artifact = {
        "artifact_type": "generated_metrology_fixture",
        "program_hash": result.execution.process_hash,
        "child_world_hash": result.execution.child_world_hash,
        "assembly_id": "metrology_fixture",
        "selected_parameters": result.selected_parameters,
        "capability": capability,
        "qualified_process_capability_id": result.qualified_process_capability_id,
        "qualified_process_capability": result.execution.final_state["capabilities"][
            result.qualified_process_capability_id
        ],
        "research_strategy_hash": research.strategy.strategy_hash,
        "proposer_id": research.proposer_id,
        "search": {
            "attempted_candidates": result.attempted_candidates,
            "executable_candidates": result.executable_candidates,
            "feasible_candidates": result.feasible_candidates,
            "candidate_support_size": result.candidate_support_size,
            "robust_worst_case_error_um": result.robust_worst_case_error_um,
            "weighted_model_error_ppm_um": result.weighted_model_error_ppm_um,
            "hypothesis_errors_um": result.hypothesis_errors_um,
        },
        "total_duration_us": result.execution.total_duration_us,
        "total_energy_mj": result.execution.total_energy_mj,
    }
    construction_receipts = [
        {
            "operation_hash": receipt.operation_hash,
            "parent_world_hash": receipt.parent_world_hash,
            "child_world_hash": receipt.child_world_hash,
            "balances": [balance.to_dict() for balance in receipt.balances],
        }
        for receipt in result.execution.receipts
    ]
    consumed_mass_mg = sum(
        balance.input_q
        for receipt in result.execution.receipts
        if receipt.operation in {"machine_part", "consume_component"}
        for balance in receipt.balances
    )
    submission = {
        "schema_version": "0.1",
        "system_name": "gtheta-fixture-research-baseline",
        "system_version": "0.5.0",
        "declared_evidence_tier": "conformance",
        "resource_use": {
            "wall_time_s": 0.0,
            "monetary_cost_usd": 50.0,
            "tokens": 0,
            "energy_j": result.execution.total_energy_mj / 1000.0,
            "material_kg": consumed_mass_mg / 1_000_000.0,
            "human_intervention_s": 0.0,
            "attempts": result.attempted_candidates,
        },
        "generations": [
            {
                "index": 0,
                "parent_process_hash": benchmark_world["baseline_process_hash"],
                "child_process_hash": result.execution.process_hash,
                "parent_world_hash": result.execution.parent_world_hash,
                "child_world_hash": result.execution.child_world_hash,
                "mrs": mrs,
                "artifact": artifact,
                "artifact_hash": digest(artifact),
                "construction_receipts": construction_receipts,
                "experiment_receipts": [
                    {
                        "kind": "public_search_execution",
                        "selected_parameters": result.selected_parameters,
                        "attempted_candidates": result.attempted_candidates,
                        "executable_candidates": result.executable_candidates,
                    }
                ],
            }
        ],
    }
    write_json(Path(os.environ["MBENCH_SUBMISSION_PATH"]), submission)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
