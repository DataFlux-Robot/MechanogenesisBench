#!/usr/bin/env python3
"""Two-generation physical-contributory fixture baseline."""

from __future__ import annotations

import json
import os
from pathlib import Path

from mechanogenesis_bench.canonical import digest
from mechanogenesis_engine.compiler import load_world
from mechanogenesis_engine.fixture_search import FixtureGoal, SearchResult, search_fixture
from mechanogenesis_engine.ir import program_to_dict


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def store_object(store: Path, value: object) -> str:
    object_digest = digest(value)
    write_json(store / f"{object_digest[7:]}.json", value)
    return object_digest


def core_receipts(result: SearchResult) -> list[dict[str, object]]:
    return [
        {
            "operation_hash": receipt.operation_hash,
            "parent_world_hash": receipt.parent_world_hash,
            "child_world_hash": receipt.child_world_hash,
            "balances": [balance.to_dict() for balance in receipt.balances],
        }
        for receipt in result.execution.receipts
    ]


def mrs_bundle(
    store: Path,
    result: SearchResult,
    *,
    stage: str,
    goal: dict[str, object],
    evaluator_contract: dict[str, object],
) -> dict[str, str]:
    program = program_to_dict(result.program)
    objects: dict[str, object] = {
        "language": {
            "kind": "canonical_mechanism_ir",
            "version": "0.3",
            "stage": stage,
            "generated_fragment": [
                "axis_aligned_csg",
                "rigid_assembly",
                "subtractive_manufacturing",
                "stateful_process_qualification",
            ],
        },
        "semantics": {
            "kind": "deterministic_stateful_transition_system",
            "parent_world_hash": result.execution.parent_world_hash,
            "invariants": [
                "material_closure",
                "process_world_separation",
                "receipt_chain",
                "physical_capability_citation",
            ],
        },
        "compiler": {
            "kind": "fixture_program_generator",
            "stage": stage,
            "target": "canonical_mechanism_ir_v0.3",
        },
        "compiler_certificate": {
            "kind": "reference_execution_certificate",
            "process_hash": result.execution.process_hash,
            "parent_world_hash": result.execution.parent_world_hash,
            "child_world_hash": result.execution.child_world_hash,
            "receipt_count": len(result.execution.receipts),
        },
        "theory_portfolio": {
            "kind": "physical_contribution_hypothesis",
            "stage": stage,
            "claim": (
                "fixture-local metrology plus transfer error can strictly reduce "
                "the machine absolute setup bound"
            ),
            "selected_parameters": result.selected_parameters,
        },
        "construction_program": program,
        "experiment_program": {
            "kind": "hidden_span_disturbance_interventions",
            "stage": stage,
            "public_goal": goal,
        },
        "evaluator_contract": evaluator_contract,
        "update_proposal": {
            "kind": "physical_process_update" if stage == "qualifier" else "successor_evidence",
            "stage": stage,
            "attempted_candidates": result.attempted_candidates,
            "feasible_candidates": result.feasible_candidates,
        },
    }
    return {name: store_object(store, value) for name, value in objects.items()}


def consumed_mass_mg(result: SearchResult) -> int:
    return sum(
        balance.input_q
        for receipt in result.execution.receipts
        if receipt.operation in {"machine_part", "consume_component"}
        for balance in receipt.balances
    )


def artifact_for(result: SearchResult, *, stage: str) -> dict[str, object]:
    capabilities = result.execution.final_state["capabilities"]
    assert isinstance(capabilities, dict)
    fixture = capabilities[result.fixture_capability_id]
    artifact: dict[str, object] = {
        "artifact_type": "generated_metrology_fixture",
        "stage": stage,
        "program_hash": result.execution.process_hash,
        "parent_world_hash": result.execution.parent_world_hash,
        "child_world_hash": result.execution.child_world_hash,
        "fixture_capability_id": result.fixture_capability_id,
        "fixture_capability": fixture,
        "selected_parameters": result.selected_parameters,
    }
    if result.qualified_process_capability_id is not None:
        artifact["qualified_process_capability_id"] = (
            result.qualified_process_capability_id
        )
        artifact["qualified_process_capability"] = capabilities[
            result.qualified_process_capability_id
        ]
    return artifact


def main() -> int:
    public_root = Path(os.environ["MBENCH_TASK_DIR"]) / "public"
    output = Path(os.environ["MBENCH_OUTPUT_DIR"])
    store = output / "objects"
    store.mkdir(parents=True, exist_ok=True)
    world = load_world(public_root / "mechanism_world.json")
    goal_raw = json.loads((public_root / "fixture_goal.json").read_text(encoding="utf-8"))
    goal = FixtureGoal.from_mapping(goal_raw)
    benchmark_world = json.loads((public_root / "world.json").read_text(encoding="utf-8"))
    evaluator_contract = json.loads(
        (public_root / "evaluator_contract.json").read_text(encoding="utf-8")
    )

    qualifier = search_fixture(world, goal, qualify_process=True)
    assert qualifier.qualified_process_capability_id is not None
    successor = search_fixture(
        world,
        goal,
        parent_state=qualifier.execution.final_state,
        namespace="successor",
        process_capability_id=qualifier.qualified_process_capability_id,
        qualify_process=False,
    )
    artifacts = [
        artifact_for(qualifier, stage="qualifier"),
        artifact_for(successor, stage="successor"),
    ]
    results = [qualifier, successor]
    stages = ["qualifier", "successor"]
    generations = []
    parent_process_hash = benchmark_world["baseline_process_hash"]
    for index, (result, stage, artifact) in enumerate(
        zip(results, stages, artifacts, strict=True)
    ):
        generations.append(
            {
                "index": index,
                "parent_process_hash": parent_process_hash,
                "child_process_hash": result.execution.process_hash,
                "parent_world_hash": result.execution.parent_world_hash,
                "child_world_hash": result.execution.child_world_hash,
                "mrs": mrs_bundle(
                    store,
                    result,
                    stage=stage,
                    goal=goal_raw,
                    evaluator_contract=evaluator_contract,
                ),
                "artifact": artifact,
                "artifact_hash": digest(artifact),
                "construction_receipts": core_receipts(result),
                "experiment_receipts": [
                    {
                        "kind": "stateful_fixture_intervention_sweep",
                        "stage": stage,
                        "attempted_candidates": result.attempted_candidates,
                        "selected_parameters": result.selected_parameters,
                    }
                ],
            }
        )
        parent_process_hash = result.execution.process_hash

    submission = {
        "schema_version": "0.1",
        "system_name": "recursive-fixture-process-baseline",
        "system_version": "0.3.0",
        "declared_evidence_tier": "conformance",
        "resource_use": {
            "wall_time_s": 0.0,
            "monetary_cost_usd": 100.0,
            "tokens": 0,
            "energy_j": sum(item.execution.total_energy_mj for item in results)
            / 1000.0,
            "material_kg": sum(consumed_mass_mg(item) for item in results)
            / 1_000_000.0,
            "human_intervention_s": 0.0,
            "attempts": sum(item.attempted_candidates for item in results),
        },
        "generations": generations,
    }
    write_json(Path(os.environ["MBENCH_SUBMISSION_PATH"]), submission)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
