#!/usr/bin/env python3
"""Trusted simulation evaluator for the demand-driven microfactory task."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import sys

REPO_SRC = Path(__file__).resolve().parents[4] / "src"
if str(REPO_SRC) not in sys.path:
    sys.path.insert(0, str(REPO_SRC))

from mechanogenesis_bench.canonical import digest  # noqa: E402
from mechanogenesis_bench.demand_microfactory import (  # noqa: E402
    DEMAND_ATTRIBUTES,
    FACTORY_CAPITAL_COST_MILLIUSD,
    MicrofactoryPlan,
    PRODUCT_UNIT_COST_MILLIUSD,
    demand_calibration_error_ppm,
    evaluate_demand_outcome,
    execute_plan,
    initial_operator_from_world,
    product_metrics,
)
from mechanogenesis_engine.sovereign import (  # noqa: E402
    find_demand_microfactory_checker,
    verify_with_lean,
)


def _load(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def _mean(values: list[int]) -> int:
    return sum(values) // len(values)


def _operator_certificate(operator: object) -> dict[str, object]:
    return {
        "bundleHash": str(getattr(operator, "bundle_hash")),
        "mechanicalPositionErrorUm": int(
            getattr(operator, "mechanical_position_error_um")
        ),
        "pcbEscapeRatePpm": int(getattr(operator, "pcb_escape_rate_ppm")),
        "batteryCalibrationErrorMv": int(
            getattr(operator, "battery_calibration_error_mv")
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--submission", type=Path, required=True)
    parser.add_argument("--task-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    submission = _load(args.submission)
    public = args.task_dir / "public"
    world = _load(public / "world.json")
    inventory = _load(public / "inventory.json")
    contract = _load(public / "evaluator_contract.json")
    accounting = _load(public / "production_accounting.json")
    if accounting["factory_capital_cost"] != FACTORY_CAPITAL_COST_MILLIUSD:
        raise ValueError("public factory cost schedule disagrees with execution semantics")
    if accounting["product_unit_cost"] != PRODUCT_UNIT_COST_MILLIUSD:
        raise ValueError("public product cost schedule disagrees with execution semantics")
    if int(accounting["registered_lifecycle_value_milliusd_per_utility_micro"]) != int(
        contract["lifecycle_value_milliusd_per_utility_micro"]
    ):
        raise ValueError("public lifecycle value schedule disagrees with evaluator contract")
    observations = _load(public / "demand_observations.json")["generations"]
    private = _load(args.task_dir / "private/spec.json")
    submitted = submission.get("generations")
    if not isinstance(submitted, list):
        raise ValueError("submission generations are missing")

    operator = initial_operator_from_world(world)
    initial_operator = operator
    parent_world_hash = str(world["baseline_world_hash"])
    executions = []
    plans = []
    detailed = []
    decisions = []
    structural_failures: list[str] = []
    inventory_remaining = {
        str(item["id"]): int(item["available_mg"])
        for item in inventory["materials"]
    }
    for index in range(2):
        raw_generation = submitted[index]
        if not isinstance(raw_generation, dict):
            raise ValueError("submitted generation must be an object")
        artifact = raw_generation.get("artifact")
        if not isinstance(artifact, dict):
            raise ValueError("generation artifact is missing")
        plan_raw = artifact.get("plan")
        if not isinstance(plan_raw, dict):
            raise ValueError("artifact does not contain the literal model plan")
        plan = MicrofactoryPlan.from_mapping(plan_raw)
        execution = execute_plan(
            plan,
            operator,
            parent_world_hash=parent_world_hash,
            capital_budget_milliusd=int(contract["capital_budget_milliusd"][index]),
        )
        plans.append(plan)
        executions.append(execution)
        if raw_generation.get("parent_world_hash") != execution.parent_world_hash:
            structural_failures.append(f"generation {index} parent world mismatch")
        if raw_generation.get("child_world_hash") != execution.child_world_hash:
            structural_failures.append(f"generation {index} child world mismatch")
        if artifact.get("plan_hash") != execution.plan_hash:
            structural_failures.append(f"generation {index} plan hash mismatch")
        if artifact.get("execution_hash") != execution.execution_hash:
            structural_failures.append(f"generation {index} execution hash mismatch")
        if artifact.get("product_hash") != execution.product_hash:
            structural_failures.append(f"generation {index} product hash mismatch")
        if artifact.get("output_operator_bundle") != asdict(execution.output_operator):
            structural_failures.append(f"generation {index} output operator mismatch")
        if artifact.get("capital_cost_milliusd") != execution.capital_cost_milliusd:
            structural_failures.append(f"generation {index} capital cost mismatch")
        if artifact.get("product_cost_milliusd") != execution.product_cost_milliusd:
            structural_failures.append(f"generation {index} product cost mismatch")
        if artifact.get("total_cost_milliusd") != execution.total_cost_milliusd:
            structural_failures.append(f"generation {index} total cost mismatch")
        if raw_generation.get("construction_receipts") != list(
            execution.construction_receipts
        ):
            structural_failures.append(f"generation {index} construction trace mismatch")
        if artifact.get("demand_evidence_hash") != digest(observations[index]):
            structural_failures.append(f"generation {index} demand evidence mismatch")
        if artifact.get("human_endorsed_positive_surprise") is not False:
            structural_failures.append(
                f"generation {index} synthetic task claimed human endorsement"
            )
        for receipt in execution.construction_receipts:
            for balance in receipt["balances"]:
                material = str(balance["material"])
                if material not in inventory_remaining:
                    structural_failures.append(
                        f"generation {index} used unregistered material {material}"
                    )
                    continue
                inventory_remaining[material] -= int(balance["input_q"])
                if inventory_remaining[material] < 0:
                    structural_failures.append(
                        f"generation {index} exceeded inventory for {material}"
                    )

        truth = private["truth_attribute_weights_ppm"][index]
        calibration_error = demand_calibration_error_ppm(plan.demand_belief, truth)
        holdout_metrics = [
            product_metrics(plan.product, operator, disturbance=case)
            for case in private["holdout_disturbances"][index]
        ]
        robustness = sum(bool(metrics["physical_pass"]) for metrics in holdout_metrics) / len(holdout_metrics)
        outcomes = [
            evaluate_demand_outcome(
                plan,
                metrics,
                truth,
                latent_novel_affordance=private["latent_novel_affordance"][index],
            )
            for metrics in holdout_metrics
        ]
        minimum_utility = min(int(value["utility_micro"]) for value in outcomes)
        mean_brier = _mean([int(value["outcome_brier_ppm2"]) for value in outcomes])
        strict_operator_improvement = bool(
            execution.output_operator.mechanical_position_error_um
            < operator.mechanical_position_error_um
            and execution.output_operator.pcb_escape_rate_ppm
            < operator.pcb_escape_rate_ppm
            and execution.output_operator.battery_calibration_error_mv
            < operator.battery_calibration_error_mv
        )
        detailed.append(
            {
                "generation": index,
                "plan_hash": execution.plan_hash,
                "input_operator_bundle_hash": operator.bundle_hash,
                "output_operator_bundle_hash": execution.output_operator.bundle_hash,
                "demand_calibration_error_ppm": calibration_error,
                "minimum_product_utility_micro": minimum_utility,
                "mean_outcome_brier_ppm2": mean_brier,
                "robustness_pass_rate": robustness,
                "robustness_passes": sum(
                    bool(metrics["physical_pass"]) for metrics in holdout_metrics
                ),
                "robustness_trials": len(holdout_metrics),
                "strict_operator_improvement": strict_operator_improvement,
                "synthetic_positive_surprise_proxy": any(
                    bool(value["synthetic_positive_surprise_proxy"])
                    for value in outcomes
                ),
                "human_endorsed_positive_surprise": False,
                "holdout_metrics": holdout_metrics,
            }
        )
        operator = execution.output_operator
        parent_world_hash = execution.child_world_hash

    g0_on_g1_error = sum(
        abs(
            plans[0].demand_belief.weight_map[name]
            - int(private["truth_attribute_weights_ppm"][1][name])
        )
        for name in DEMAND_ATTRIBUTES
    )
    demand_update_gain = g0_on_g1_error - int(
        detailed[1]["demand_calibration_error_ppm"]
    )
    inherited_quality = []
    counterfactual_quality = []
    for case in private["holdout_disturbances"][1]:
        inherited_quality.append(
            int(product_metrics(plans[1].product, executions[0].output_operator, disturbance=case)["physical_quality_ppm"])
        )
        counterfactual_quality.append(
            int(product_metrics(plans[1].product, initial_operator, disturbance=case)["physical_quality_ppm"])
        )
    inheritance_advantage = _mean(inherited_quality) - _mean(counterfactual_quality)
    exact_lineage = bool(
        executions[0].output_operator.bundle_hash
        == executions[1].input_operator.bundle_hash
        == plans[1].input_operator_bundle_hash
    )

    for index in range(2):
        current = detailed[index]
        accepted = bool(
            not structural_failures
            and current["strict_operator_improvement"]
            and current["robustness_pass_rate"]
            >= int(contract["minimum_robustness_pass_rate_ppm"]) / 1_000_000
            and int(current["demand_calibration_error_ppm"])
            <= int(contract["maximum_demand_calibration_error_ppm"][index])
            and int(current["minimum_product_utility_micro"])
            >= int(contract["minimum_product_utility_micro"][index])
            and (
                index == 0
                or (
                    exact_lineage
                    and demand_update_gain >= int(contract["minimum_demand_update_gain_ppm"])
                    and inheritance_advantage >= int(contract["minimum_inheritance_advantage_ppm"])
                )
            )
        )
        before = 0 if index == 0 else int(detailed[index - 1]["minimum_product_utility_micro"])
        after = int(current["minimum_product_utility_micro"])
        decisions.append(
            {
                "index": index,
                "artifact_hash": raw_artifact_hash(submitted[index]),
                "accepted": accepted,
                "before_upper": before / 1000.0,
                "after_lower": after / 1000.0,
                "margin": 1.0,
                "net_value": float(
                    after
                    * int(contract["lifecycle_value_milliusd_per_utility_micro"])
                    - executions[index].total_cost_milliusd
                ),
                "robustness_pass_rate": float(current["robustness_pass_rate"]),
                "evidence_tier": "simulation",
                "rrc_time_rate_delta": 0.0,
                "rrc_budget_rate_delta": (
                    inheritance_advantage / 1_000_000.0 if index == 1 else 0.0
                ),
            }
        )

    certificate = {
        "schemaVersion": "demand-microfactory-certificate/v1",
        "taskPackageDigest": os.environ["MBENCH_TASK_PACKAGE_DIGEST"],
        "evaluatorDigest": os.environ["MBENCH_EVALUATOR_BUNDLE_DIGEST"],
        "generation0": {
            "generation": 0,
            "planHash": executions[0].plan_hash,
            "productHash": executions[0].product_hash,
            "executionHash": executions[0].execution_hash,
            "constructionTraceHash": digest(
                list(executions[0].construction_receipts)
            ),
            "inputOperator": _operator_certificate(executions[0].input_operator),
            "outputOperator": _operator_certificate(executions[0].output_operator),
            "demandCalibrationErrorPpm": int(
                detailed[0]["demand_calibration_error_ppm"]
            ),
            "maximumDemandCalibrationErrorPpm": int(
                contract["maximum_demand_calibration_error_ppm"][0]
            ),
            "minimumProductUtilityMicro": int(
                detailed[0]["minimum_product_utility_micro"]
            ),
            "requiredProductUtilityMicro": int(
                contract["minimum_product_utility_micro"][0]
            ),
            "robustnessPasses": int(detailed[0]["robustness_passes"]),
            "robustnessTrials": int(detailed[0]["robustness_trials"]),
            "minimumRobustnessPpm": int(
                contract["minimum_robustness_pass_rate_ppm"]
            ),
            "syntheticDemandEvidence": True,
            "humanEndorsedPositiveSurprise": False,
        },
        "generation1": {
            "generation": 1,
            "planHash": executions[1].plan_hash,
            "productHash": executions[1].product_hash,
            "executionHash": executions[1].execution_hash,
            "constructionTraceHash": digest(
                list(executions[1].construction_receipts)
            ),
            "inputOperator": _operator_certificate(executions[1].input_operator),
            "outputOperator": _operator_certificate(executions[1].output_operator),
            "demandCalibrationErrorPpm": int(
                detailed[1]["demand_calibration_error_ppm"]
            ),
            "maximumDemandCalibrationErrorPpm": int(
                contract["maximum_demand_calibration_error_ppm"][1]
            ),
            "minimumProductUtilityMicro": int(
                detailed[1]["minimum_product_utility_micro"]
            ),
            "requiredProductUtilityMicro": int(
                contract["minimum_product_utility_micro"][1]
            ),
            "robustnessPasses": int(detailed[1]["robustness_passes"]),
            "robustnessTrials": int(detailed[1]["robustness_trials"]),
            "minimumRobustnessPpm": int(
                contract["minimum_robustness_pass_rate_ppm"]
            ),
            "syntheticDemandEvidence": True,
            "humanEndorsedPositiveSurprise": False,
        },
        "demandUpdateGainPpm": demand_update_gain,
        "requiredDemandUpdateGainPpm": int(
            contract["minimum_demand_update_gain_ppm"]
        ),
        "inheritanceAdvantagePpm": inheritance_advantage,
        "requiredInheritanceAdvantagePpm": int(
            contract["minimum_inheritance_advantage_ppm"]
        ),
    }
    certificate_path = args.output.with_name("demand_microfactory_certificate.json")
    certificate_path.write_text(
        json.dumps(certificate, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    lean_status = "not_applicable_nonpromoted"
    if all(bool(decision["accepted"]) for decision in decisions):
        checker = find_demand_microfactory_checker(args.task_dir.parents[2])
        if checker is None:
            raise RuntimeError("Lean demand microfactory checker is unavailable")
        verify_with_lean(certificate_path, checker)
        lean_status = "accepted"

    report = {
        "schema_version": "0.1",
        "task_id": "simulation.demand_driven_microfactory",
        "task_package_digest": os.environ["MBENCH_TASK_PACKAGE_DIGEST"],
        "evaluator_digest": os.environ["MBENCH_EVALUATOR_BUNDLE_DIGEST"],
        "decisions": decisions,
        "lean_certificate": {
            "status": lean_status,
            "path": certificate_path.name,
            "sha256": digest(certificate),
        },
        "microfactory_metrics": {
            "generations": detailed,
            "demand_update_gain_ppm": demand_update_gain,
            "exact_operator_inheritance": exact_lineage,
            "inheritance_advantage_ppm": inheritance_advantage,
            "structural_failures": structural_failures,
            "inventory_remaining_mg": inventory_remaining,
            "human_endorsed_positive_surprise_count": 0,
            "synthetic_positive_surprise_proxy_count": sum(
                bool(value["synthetic_positive_surprise_proxy"])
                for value in detailed
            ),
        },
    }
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0


def raw_artifact_hash(raw_generation: object) -> str:
    if not isinstance(raw_generation, dict):
        raise ValueError("generation is malformed")
    value = raw_generation.get("artifact_hash")
    if not isinstance(value, str):
        raise ValueError("generation artifact hash is missing")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
