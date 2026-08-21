#!/usr/bin/env python3
"""Trusted evaluator for generated canonical fixture programs."""

from __future__ import annotations

import argparse
from math import ceil
import json
import os
from pathlib import Path

from mechanogenesis_engine.compiler import load_world
from mechanogenesis_engine.fixture_search import FixtureGoal, search_fixture
from mechanogenesis_engine.interpreter import ReferenceInterpreter
from mechanogenesis_engine.ir import MechanismProgram
from mechanogenesis_engine.research_strategy import FixtureResearchStrategy
from mechanogenesis_engine.sovereign import (
    SovereignCertificate,
    find_promotion_checker,
    find_sovereign_checker,
    promotion_envelope,
    verify_promotion_with_lean,
    verify_with_lean,
)


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


def load_mrs_object(
    submission_path: Path, generation: dict[str, object], name: str
) -> object:
    object_digest = generation["mrs"][name]
    object_path = submission_path.parent / "objects" / f"{object_digest[7:]}.json"
    return json.loads(object_path.read_text(encoding="utf-8"))


def mrs_object_path(
    submission_path: Path, generation: dict[str, object], name: str
) -> Path:
    object_digest = generation["mrs"][name]
    return submission_path.parent / "objects" / f"{object_digest[7:]}.json"


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
        language_object = load_mrs_object(args.submission, generation, "language")
        valid = valid and language_object["kind"] == (
            "gtheta_generated_research_language"
        )
        strategy = FixtureResearchStrategy.from_mapping(
            language_object["research_strategy"]
        )
        valid = valid and language_object["strategy_hash"] == strategy.strategy_hash
        goal = FixtureGoal.from_mapping(
            json.loads(
                (args.task_dir / "public/fixture_goal.json").read_text(encoding="utf-8")
            )
        )
        regenerated = search_fixture(world, goal, strategy=strategy)
        compiler_certificate = load_mrs_object(
            args.submission, generation, "compiler_certificate"
        )
        sovereign = SovereignCertificate.from_mapping(compiler_certificate)
        checker = find_sovereign_checker(args.task_dir.parents[2])
        if checker is None:
            raise RuntimeError("Lean sovereign checker is unavailable")
        verify_with_lean(
            mrs_object_path(args.submission, generation, "compiler_certificate"),
            checker,
        )
        theory_portfolio = load_mrs_object(
            args.submission, generation, "theory_portfolio"
        )
        experiment_program = load_mrs_object(
            args.submission, generation, "experiment_program"
        )
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
        valid = valid and regenerated.execution.process_hash == execution.process_hash
        valid = (
            valid and regenerated.selected_parameters == artifact["selected_parameters"]
        )
        valid = valid and artifact["research_strategy_hash"] == strategy.strategy_hash
        valid = valid and artifact["search"]["attempted_candidates"] == (
            regenerated.attempted_candidates
        )
        valid = valid and artifact["search"]["candidate_support_size"] == (
            regenerated.candidate_support_size
        )
        valid = valid and artifact["search"]["robust_worst_case_error_um"] == (
            regenerated.robust_worst_case_error_um
        )
        valid = valid and artifact["search"]["weighted_model_error_ppm_um"] == (
            regenerated.weighted_model_error_ppm_um
        )
        valid = valid and artifact["search"]["hypothesis_errors_um"] == (
            regenerated.hypothesis_errors_um
        )
        valid = valid and sovereign.strategy_hash == strategy.strategy_hash
        valid = valid and sovereign.program_hash == regenerated.execution.process_hash
        valid = valid and sovereign.child_world_hash == (
            regenerated.execution.child_world_hash
        )
        valid = valid and sovereign.candidate_support_size == (
            regenerated.candidate_support_size
        )
        valid = valid and sovereign.attempted_candidates == (
            regenerated.attempted_candidates
        )
        valid = valid and theory_portfolio["observed_hypothesis_errors_um"] == (
            regenerated.hypothesis_errors_um
        )
        valid = valid and experiment_program["selected_parameters"] == (
            regenerated.selected_parameters
        )
        valid = valid and generation["construction_receipts"] == core_receipts(
            execution
        )
        valid = valid and artifact["program_hash"] == execution.process_hash
        valid = valid and artifact["child_world_hash"] == execution.child_world_hash
        capabilities = execution.final_state["capabilities"]
        fixture_capability = capabilities["generated_fixture_metrology"]
        qualified_process = capabilities["generated_fixture_machine_process"]
        valid = valid and artifact["capability"] == fixture_capability
        valid = valid and artifact["qualified_process_capability_id"] == (
            "generated_fixture_machine_process"
        )
        valid = valid and artifact["qualified_process_capability"] == qualified_process
        valid = valid and qualified_process["position_error_um"] < (
            next(iter(world.machines)).absolute_setup_error_um
        )
    except Exception:
        valid = False

    before_upper = -float(world.baseline_capability_error_um)
    margin = float(spec["promotion_margin_um"])
    robustness = 0.0
    net_value = -1.0
    after_lower = before_upper
    if valid and execution is not None:
        capability = execution.final_state["capabilities"][
            "generated_fixture_metrology"
        ]
        clearance = int(capability["radial_clearance_um"])
        reference_clearance = int(capability["reference_clearance_um"])
        manufacturing_repeatability = int(capability["manufacturing_repeatability_um"])
        spacing = int(capability["locator_spacing_um"])
        case_errors = []
        for case in spec["held_out_cases"]:
            angular = ceil(2 * clearance * int(case["workpiece_span_um"]) / spacing)
            case_errors.append(
                clearance
                + reference_clearance
                + angular
                + manufacturing_repeatability
                + world.probe_repeatability_um
                + world.disturbance_bound_um
                + int(case["extra_disturbance_um"])
            )
        robustness = sum(value <= spec["max_error_um"] for value in case_errors) / len(
            case_errors
        )
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
    sovereign_promotion = None
    if accepted and execution is not None:
        promotion_checker = find_promotion_checker(args.task_dir.parents[2])
        if promotion_checker is None:
            accepted = False
        else:
            try:
                sovereign_promotion = promotion_envelope(
                    sovereign,
                    artifact_hash=generation["artifact_hash"],
                    parent_error_upper=world.baseline_capability_error_um,
                    child_error_upper=worst_error,
                    required_improvement=int(margin),
                    net_value=int(net_value),
                    robustness_passed=robustness >= 0.80,
                )
                verify_promotion_with_lean(sovereign_promotion, promotion_checker)
            except Exception:
                accepted = False
    report = {
        "schema_version": "0.1",
        "task_id": "conformance.generated_metrology_fixture",
        "task_package_digest": os.environ["MBENCH_TASK_PACKAGE_DIGEST"],
        "evaluator_digest": os.environ["MBENCH_EVALUATOR_BUNDLE_DIGEST"],
        "sovereign_promotions": (
            [sovereign_promotion] if sovereign_promotion is not None else []
        ),
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
                "rrc_budget_rate_delta": 0.0,
            }
        ],
    }
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
