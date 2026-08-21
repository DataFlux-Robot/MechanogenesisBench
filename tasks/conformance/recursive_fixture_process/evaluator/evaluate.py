#!/usr/bin/env python3
"""Trusted evaluator for the two-generation physical-contribution chain."""

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


def load_program(submission_path: Path, generation: dict[str, object]) -> MechanismProgram:
    mrs = generation["mrs"]
    assert isinstance(mrs, dict)
    program_digest = mrs["construction_program"]
    assert isinstance(program_digest, str)
    object_path = submission_path.parent / "objects" / f"{program_digest[7:]}.json"
    return MechanismProgram.from_mapping(
        json.loads(object_path.read_text(encoding="utf-8"))
    )


def bind_generation(generation, program_digest: str, execution) -> bool:
    artifact = generation["artifact"]
    capabilities = execution.final_state["capabilities"]
    fixture_id = artifact["fixture_capability_id"]
    capability_bound = artifact["fixture_capability"] == capabilities[fixture_id]
    qualified_bound = True
    if "qualified_process_capability_id" in artifact:
        qualified_id = artifact["qualified_process_capability_id"]
        qualified_bound = artifact["qualified_process_capability"] == capabilities[
            qualified_id
        ]
    return bool(
        generation["parent_world_hash"] == execution.parent_world_hash
        and generation["child_world_hash"] == execution.child_world_hash
        and generation["child_process_hash"] == execution.process_hash
        and program_digest == execution.process_hash
        and generation["construction_receipts"] == core_receipts(execution)
        and artifact["program_hash"] == execution.process_hash
        and artifact["parent_world_hash"] == execution.parent_world_hash
        and artifact["child_world_hash"] == execution.child_world_hash
        and capability_bound
        and qualified_bound
    )


def local_error(capability, case, world) -> int:
    clearance = int(capability["radial_clearance_um"])
    spacing = int(capability["locator_spacing_um"])
    angular = ceil(2 * clearance * int(case["workpiece_span_um"]) / spacing)
    return (
        clearance
        + int(capability["reference_clearance_um"])
        + angular
        + int(capability["manufacturing_repeatability_um"])
        + world.probe_repeatability_um
        + world.disturbance_bound_um
        + int(case["extra_disturbance_um"])
    )


def consumed_mass(execution) -> int:
    return sum(
        balance.input_q
        for receipt in execution.receipts
        if receipt.operation in {"machine_part", "consume_component"}
        for balance in receipt.balances
    )


def decision(
    *,
    index: int,
    artifact_hash: str,
    valid: bool,
    before_error: int,
    after_error: int,
    robustness: float,
    limit: float,
    margin: float,
    net_value: float,
) -> dict[str, object]:
    before_upper = -float(before_error)
    after_lower = -float(after_error)
    accepted = bool(
        valid
        and after_lower >= before_upper + margin
        and net_value > 0
        and robustness >= limit
    )
    return {
        "index": index,
        "artifact_hash": artifact_hash,
        "accepted": accepted,
        "before_upper": before_upper,
        "after_lower": after_lower,
        "margin": margin,
        "net_value": net_value,
        "robustness_pass_rate": robustness,
        "evidence_tier": "conformance",
        "rrc_time_rate_delta": 0.0,
        "rrc_budget_rate_delta": 0.0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--submission", type=Path, required=True)
    parser.add_argument("--task-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    submission = json.loads(args.submission.read_text(encoding="utf-8"))
    generations = submission.get("generations", [])
    world = load_world(args.task_dir / "public/mechanism_world.json")
    spec = json.loads((args.task_dir / "private/spec.json").read_text(encoding="utf-8"))
    valid = isinstance(generations, list) and len(generations) == 2
    executions = []
    programs = []
    try:
        interpreter = ReferenceInterpreter()
        first_program = load_program(args.submission, generations[0])
        first_execution = interpreter.execute(world, first_program)
        second_program = load_program(args.submission, generations[1])
        second_execution = interpreter.execute_from_state(
            world, first_execution.final_state, second_program
        )
        programs = [first_program, second_program]
        executions = [first_execution, second_execution]
        for generation, program, execution in zip(
            generations, programs, executions, strict=True
        ):
            program_digest = generation["mrs"]["construction_program"]
            valid = valid and bind_generation(
                generation, program_digest, execution
            )
        valid = valid and (
            generations[1]["parent_process_hash"]
            == first_execution.process_hash
        )
        qualified_id = generations[0]["artifact"][
            "qualified_process_capability_id"
        ]
        valid = valid and second_program.operations[0][
            "process_capability_id"
        ] == qualified_id
    except Exception:
        valid = False

    margin = float(spec["promotion_margin_um"])
    minimum_robustness = 0.80
    decisions = []
    if valid:
        first_execution, second_execution = executions
        first_artifact = generations[0]["artifact"]
        second_artifact = generations[1]["artifact"]
        first_fixture = first_artifact["fixture_capability"]
        second_fixture = second_artifact["fixture_capability"]
        qualified = first_artifact["qualified_process_capability"]
        transfer = int(qualified["transfer_error_um"])
        base_process_error = next(iter(world.machines)).absolute_setup_error_um
        first_local_cases = [
            local_error(first_fixture, case, world)
            for case in spec["held_out_cases"]
        ]
        second_local_cases = [
            local_error(second_fixture, case, world)
            for case in spec["held_out_cases"]
        ]
        qualified_cases = [value + transfer for value in first_local_cases]
        parent_artifact_cases = [
            base_process_error + value for value in first_local_cases
        ]
        successor_cases = [
            process_error + local
            for process_error, local in zip(
                qualified_cases, second_local_cases, strict=True
            )
        ]
        process_robustness = sum(
            value <= spec["max_qualified_process_error_um"]
            for value in qualified_cases
        ) / len(qualified_cases)
        successor_robustness = sum(
            value <= spec["max_successor_absolute_error_um"]
            for value in successor_cases
        ) / len(successor_cases)
        first_gain = base_process_error - max(qualified_cases)
        second_gain = max(parent_artifact_cases) - max(successor_cases)
        values = [first_gain, second_gain]
        robust = [process_robustness, successor_robustness]
        before_errors = [base_process_error, max(parent_artifact_cases)]
        after_errors = [max(qualified_cases), max(successor_cases)]
        for index, execution in enumerate(executions):
            benefit = (
                values[index]
                * int(spec["reuse_count"])
                * int(spec["value_per_um_improvement_milliusd"])
            )
            material_cost = consumed_mass(execution) * int(
                spec["material_cost_milliusd_per_mg"]
            )
            decisions.append(
                decision(
                    index=index,
                    artifact_hash=generations[index]["artifact_hash"],
                    valid=valid,
                    before_error=before_errors[index],
                    after_error=after_errors[index],
                    robustness=robust[index],
                    limit=minimum_robustness,
                    margin=margin,
                    net_value=float(benefit - material_cost),
                )
            )
    else:
        for index, generation in enumerate(generations[:2]):
            decisions.append(
                decision(
                    index=index,
                    artifact_hash=generation["artifact_hash"],
                    valid=False,
                    before_error=1,
                    after_error=1,
                    robustness=0.0,
                    limit=minimum_robustness,
                    margin=margin,
                    net_value=-1.0,
                )
            )

    report = {
        "schema_version": "0.1",
        "task_id": "conformance.recursive_fixture_process",
        "task_package_digest": os.environ["MBENCH_TASK_PACKAGE_DIGEST"],
        "evaluator_digest": os.environ["MBENCH_EVALUATOR_BUNDLE_DIGEST"],
        "decisions": decisions,
    }
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
