#!/usr/bin/env python3
"""Canned protocol-conformance system, intentionally not a research baseline."""

from __future__ import annotations

import json
import os
from pathlib import Path

from mechanogenesis_bench.canonical import digest
from mechanogenesis_bench.submission import MRS_FIELDS


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def store_object(store: Path, value: object) -> str:
    object_digest = digest(value)
    write_json(store / f"{object_digest[7:]}.json", value)
    return object_digest


def mrs_bundle(store: Path, generation: int, hypothesis: str) -> dict[str, str]:
    objects: dict[str, object] = {
        "language": {
            "kind": "task_specific_mechanism_language",
            "generation": generation,
            "constructs": ["sense", "fabricate", "assemble", "intervene", "measure"],
        },
        "semantics": {
            "kind": "state_transition_relation",
            "generation": generation,
            "conserved": ["material_quanta", "world_lineage"],
        },
        "compiler": {
            "kind": "bounded_recipe_compiler",
            "generation": generation,
            "passes": ["type", "resource", "reachability", "lower"],
        },
        "compiler_certificate": {
            "kind": "conformance_certificate",
            "generation": generation,
            "claim": "all emitted operations belong to public access vocabulary",
        },
        "theory_portfolio": {
            "kind": "competing_causal_hypotheses",
            "generation": generation,
            "selected_hypothesis": hypothesis,
            "alternatives_retained": 2,
        },
        "construction_program": {
            "kind": "mechanism_construction_program",
            "generation": generation,
            "operations": ["probe", "fabricate", "install", "inspect"],
        },
        "experiment_program": {
            "kind": "interventional_test_program",
            "generation": generation,
            "tests": ["blinded_disturbance_sweep", "isolated_generator_fork"],
        },
        "evaluator_contract": {
            "kind": "promotion_contract",
            "generation": generation,
            "criteria": ["lower_bound_gain", "robustness", "net_value", "recursive_credit"],
        },
        "update_proposal": {
            "kind": "generator_update",
            "generation": generation,
            "hypothesis": hypothesis,
            "isolation": "fork_from_identical_parent_checkpoint",
        },
    }
    assert set(objects) == set(MRS_FIELDS)
    return {name: store_object(store, value) for name, value in objects.items()}


def main() -> int:
    output = Path(os.environ["MBENCH_OUTPUT_DIR"])
    output.mkdir(parents=True, exist_ok=True)
    store = output / "objects"
    store.mkdir(exist_ok=True)

    baseline_process = "sha256:" + "0" * 64
    baseline_world = "sha256:" + "1" * 64
    process_one = digest({"process": "probe-compensated calibration", "generation": 0})
    world_one = digest({"world": "calibration fixture installed", "generation": 0})
    process_two = digest({"process": "probe-compensated production fixture", "generation": 1})
    world_two = digest({"world": "production fixture installed", "generation": 1})

    artifact_zero = {
        "artifact_type": "calibration_fixture",
        "pose_error_before_mm": 0.80,
        "pose_error_after_mm": 0.15,
        "design_cost_usd": 8.0,
        "reuse_count": 100,
    }
    experiment_zero = {
        "blinded_pose_errors_mm": [0.14, 0.18, 0.16, 0.19, 0.15],
        "recursive_fork_trials": [
            {
                "baseline_future_time_s": 1000.0,
                "child_future_time_s": 810.0,
                "baseline_future_cost_usd": 100.0,
                "child_future_cost_usd": 82.0,
            },
            {
                "baseline_future_time_s": 980.0,
                "child_future_time_s": 790.0,
                "baseline_future_cost_usd": 98.0,
                "child_future_cost_usd": 80.0,
            },
        ],
    }

    artifact_one = {
        "artifact_type": "production_fixture",
        "yield_before": 0.72,
        "yield_after_trials": [0.86, 0.84, 0.85],
        "cycle_time_before_s": 120.0,
        "cycle_time_after_s": 80.0,
        "design_cost_usd": 12.0,
        "reuse_count": 200,
    }
    experiment_one = {
        "blinded_yields": [0.82, 0.88, 0.84, 0.86, 0.81],
        "recursive_fork_trials": [
            {
                "baseline_future_time_s": 800.0,
                "child_future_time_s": 510.0,
                "baseline_future_cost_usd": 80.0,
                "child_future_cost_usd": 52.0,
            },
            {
                "baseline_future_time_s": 820.0,
                "child_future_time_s": 500.0,
                "baseline_future_cost_usd": 82.0,
                "child_future_cost_usd": 51.0,
            },
        ],
    }

    submission = {
        "schema_version": "0.1",
        "system_name": "conformance-reference-only",
        "system_version": "0.1.0",
        "declared_evidence_tier": "conformance",
        "resource_use": {
            "wall_time_s": 0.0,
            "monetary_cost_usd": 20.0,
            "tokens": 0,
            "energy_j": 1000.0,
            "material_kg": 1.2,
            "human_intervention_s": 0.0,
            "attempts": 2,
        },
        "generations": [
            {
                "index": 0,
                "parent_process_hash": baseline_process,
                "child_process_hash": process_one,
                "parent_world_hash": baseline_world,
                "child_world_hash": world_one,
                "mrs": mrs_bundle(
                    store,
                    0,
                    "active probing can convert pose uncertainty into a reusable datum",
                ),
                "artifact": artifact_zero,
                "artifact_hash": digest(artifact_zero),
                "construction_receipts": [
                    {
                        "operation_hash": digest({"operation": "fabricate calibration fixture"}),
                        "parent_world_hash": baseline_world,
                        "child_world_hash": world_one,
                        "balances": [
                            {
                                "material": "tool_steel",
                                "input_q": 1000,
                                "reserve_draw_q": 0,
                                "output_q": 950,
                                "waste_q": 50,
                            }
                        ],
                    }
                ],
                "experiment_receipts": [experiment_zero],
            },
            {
                "index": 1,
                "parent_process_hash": process_one,
                "child_process_hash": process_two,
                "parent_world_hash": world_one,
                "child_world_hash": world_two,
                "mrs": mrs_bundle(
                    store,
                    1,
                    "the promoted calibration datum can constrain a higher-yield fixture",
                ),
                "artifact": artifact_one,
                "artifact_hash": digest(artifact_one),
                "construction_receipts": [
                    {
                        "operation_hash": digest({"operation": "fabricate production fixture"}),
                        "parent_world_hash": world_one,
                        "child_world_hash": world_two,
                        "balances": [
                            {
                                "material": "tool_steel",
                                "input_q": 950,
                                "reserve_draw_q": 200,
                                "output_q": 1100,
                                "waste_q": 50,
                            }
                        ],
                    }
                ],
                "experiment_receipts": [experiment_one],
            },
        ],
    }
    write_json(Path(os.environ["MBENCH_SUBMISSION_PATH"]), submission)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
