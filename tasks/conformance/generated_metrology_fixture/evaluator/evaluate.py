#!/usr/bin/env python3
"""Trusted evaluator for generated canonical fixture programs."""

from __future__ import annotations

import argparse
from math import ceil
import json
import os
from pathlib import Path

from mechanogenesis_engine.compiler import load_world
from mechanogenesis_engine.interpreter import ReferenceInterpreter
from mechanogenesis_engine.ir import MechanismProgram


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
    parser = argparse.ArgumentParser()
    parser.add_argument("--submission", type=Path, required=True)
    parser.add_argument("--task-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    submission = json.loads(args.submission.read_text(encoding="utf-8"))
    generation = submission["generations"][0]
    artifact = generation["artifact"]
    world = load_world(args.task_dir / "public/mechanism_world.json")
    spec = json.loads((args.task_dir / "private/spec.json").read_text(encoding="utf-8"))

    valid = True
    execution = None
    try:
        program_digest = generation["mrs"]["construction_program"]
        program_path = args.submission.parent / "objects" / f"{program_digest[7:]}.json"
        program = MechanismProgram.from_mapping(
            json.loads(program_path.read_text(encoding="utf-8"))
        )
        execution = ReferenceInterpreter().execute(world, program)
        valid = valid and generation["parent_world_hash"] == execution.parent_world_hash
        valid = valid and generation["child_world_hash"] == execution.child_world_hash
        valid = valid and generation["child_process_hash"] == execution.process_hash
        valid = valid and program_digest == execution.process_hash
        valid = valid and generation["construction_receipts"] == core_receipts(execution)
        valid = valid and artifact["program_hash"] == execution.process_hash
        valid = valid and artifact["child_world_hash"] == execution.child_world_hash
    except Exception:
        valid = False

    before_upper = -float(world.baseline_capability_error_um)
    margin = float(spec["promotion_margin_um"])
    robustness = 0.0
    net_value = -1.0
    after_lower = before_upper
    if valid and execution is not None:
        capability = execution.final_state["capabilities"]["generated_fixture_metrology"]
        clearance = int(capability["radial_clearance_um"])
        reference_clearance = int(capability["reference_clearance_um"])
        spacing = int(capability["locator_spacing_um"])
        case_errors = []
        for case in spec["held_out_cases"]:
            angular = ceil(
                2 * clearance * int(case["workpiece_span_um"]) / spacing
            )
            case_errors.append(
                clearance
                + reference_clearance
                + angular
                + world.probe_repeatability_um
                + world.disturbance_bound_um
                + int(case["extra_disturbance_um"])
            )
        robustness = sum(value <= spec["max_error_um"] for value in case_errors) / len(case_errors)
        worst_error = max(case_errors)
        after_lower = -float(worst_error)
        improvement = world.baseline_capability_error_um - worst_error
        input_mass_mg = sum(
            balance.input_q
            for receipt in execution.receipts
            if receipt.operation in {"machine_part", "consume_component"}
            for balance in receipt.balances
        )
        benefit = (
            improvement
            * int(spec["reuse_count"])
            * int(spec["value_per_um_improvement_milliusd"])
        )
        material_cost = input_mass_mg * int(spec["material_cost_milliusd_per_mg"])
        net_value = float(benefit - material_cost)

    accepted = (
        valid
        and after_lower >= before_upper + margin
        and net_value > 0
        and robustness >= 0.80
    )
    report = {
        "schema_version": "0.1",
        "task_id": "conformance.generated_metrology_fixture",
        "task_package_digest": os.environ["MBENCH_TASK_PACKAGE_DIGEST"],
        "evaluator_digest": os.environ["MBENCH_EVALUATOR_BUNDLE_DIGEST"],
        "decisions": [
            {
                "index": 0,
                "artifact_hash": generation["artifact_hash"],
                "accepted": accepted,
                "before_upper": before_upper,
                "after_lower": after_lower,
                "margin": margin,
                "net_value": net_value,
                "robustness_pass_rate": robustness,
                "evidence_tier": "conformance",
                "rrc_time_rate_delta": 0.0,
                "rrc_budget_rate_delta": 0.0
            }
        ]
    }
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
