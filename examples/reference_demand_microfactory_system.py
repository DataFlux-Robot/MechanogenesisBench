#!/usr/bin/env python3
"""Deterministic open baseline for the demand-driven microfactory task."""

from __future__ import annotations

from dataclasses import asdict
import json
import os
from pathlib import Path

from mechanogenesis_bench.canonical import digest
from mechanogenesis_bench.demand_microfactory import (
    MicrofactoryExecution,
    MicrofactoryPlan,
    execute_plan,
    initial_operator_from_world,
    reference_plan,
)


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


def artifact_for(
    plan: MicrofactoryPlan,
    execution: MicrofactoryExecution,
    *,
    demand_evidence_hash: str,
    model_action: dict[str, object] | None = None,
) -> dict[str, object]:
    value: dict[str, object] = {
        "artifact_type": "demand_driven_microfactory_generation",
        "generation": plan.generation,
        "plan": plan.to_dict(),
        "plan_hash": execution.plan_hash,
        "demand_evidence_hash": demand_evidence_hash,
        "input_operator_bundle": asdict(execution.input_operator),
        "output_operator_bundle": asdict(execution.output_operator),
        "product_hash": execution.product_hash,
        "product_metrics": execution.metrics,
        "capital_cost_milliusd": execution.capital_cost_milliusd,
        "product_cost_milliusd": execution.product_cost_milliusd,
        "total_cost_milliusd": execution.total_cost_milliusd,
        "parent_world_hash": execution.parent_world_hash,
        "child_world_hash": execution.child_world_hash,
        "execution_hash": execution.execution_hash,
        "synthetic_demand_evidence": True,
        "human_endorsed_positive_surprise": False,
    }
    if model_action is not None:
        value["model_action"] = model_action
        value["model_action_hash"] = digest(model_action)
    return value


def mrs_objects(
    plan: MicrofactoryPlan,
    execution: MicrofactoryExecution,
    *,
    evaluator_contract: dict[str, object],
    demand_evidence: dict[str, object],
    model_action: dict[str, object] | None = None,
) -> dict[str, object]:
    update: dict[str, object] = {
        "schema_version": "demand-conditioned-successor-proposal/v1",
        "generation": plan.generation,
        "demand_belief": {
            "attribute_weights_ppm": plan.demand_belief.weight_map,
            "outcome_forecast_ppm": plan.demand_belief.outcome_map,
        },
        "factory_operator_bundle_hash": execution.output_operator.bundle_hash,
        "allowed_history": [],
    }
    if model_action is not None:
        update["model_action"] = model_action
    return {
        "language": {
            "schema_version": "microfactory-language/v1",
            "plan_schema": plan.schema_version,
        },
        "semantics": {
            "schema_version": "microfactory-semantics/v1",
            "reference_semantics": "mechanogenesis_bench.demand_microfactory",
        },
        "compiler": {
            "schema_version": "literal-microfactory-compiler/v1",
            "plan": plan.to_dict(),
        },
        "compiler_certificate": {
            "schema_version": "microfactory-compiler-certificate/v1",
            "plan_hash": execution.plan_hash,
            "execution_hash": execution.execution_hash,
        },
        "theory_portfolio": {
            "schema_version": "microfactory-theory-portfolio/v1",
            "models": [
                "integer_vehicle_performance_v1",
                "multi_operator_capital_v1",
                "aggregate_pairwise_demand_v1",
            ],
        },
        "construction_program": {
            "schema_version": "microfactory-construction-program/v1",
            "product": asdict(plan.product),
            "factory": asdict(plan.factory),
        },
        "experiment_program": {
            "schema_version": "microfactory-experiment-program/v1",
            "demand_evidence_hash": digest(demand_evidence),
            "measurements": [
                "demand_calibration",
                "physical_robustness",
                "successor_operator_inheritance",
                "synthetic_surprise_proxy",
            ],
        },
        "evaluator_contract": evaluator_contract,
        "update_proposal": update,
    }


def build_submission(
    *,
    public: Path,
    store: Path,
    plans_and_actions: list[tuple[MicrofactoryPlan, dict[str, object] | None]],
    provider_wall_time_s: float = 0.0,
    provider_tokens: int = 0,
) -> dict[str, object]:
    world = json.loads((public / "world.json").read_text(encoding="utf-8"))
    observations = json.loads(
        (public / "demand_observations.json").read_text(encoding="utf-8")
    )["generations"]
    contract = json.loads(
        (public / "evaluator_contract.json").read_text(encoding="utf-8")
    )
    operator = initial_operator_from_world(world)
    parent_world_hash = world["baseline_world_hash"]
    parent_process_hash = world["baseline_process_hash"]
    generations = []
    total_cost_milliusd = 0
    mass_total_mg = 0
    for index, (plan, model_action) in enumerate(plans_and_actions):
        evidence = observations[index]
        execution = execute_plan(
            plan,
            operator,
            parent_world_hash=parent_world_hash,
            capital_budget_milliusd=contract["capital_budget_milliusd"][index],
        )
        objects = mrs_objects(
            plan,
            execution,
            evaluator_contract=contract,
            demand_evidence=evidence,
            model_action=model_action,
        )
        mrs = {name: store_object(store, value) for name, value in objects.items()}
        artifact = artifact_for(
            plan,
            execution,
            demand_evidence_hash=digest(evidence),
            model_action=model_action,
        )
        generations.append(
            {
                "index": index,
                "parent_process_hash": parent_process_hash,
                "child_process_hash": execution.plan_hash,
                "parent_world_hash": execution.parent_world_hash,
                "child_world_hash": execution.child_world_hash,
                "mrs": mrs,
                "artifact": artifact,
                "artifact_hash": digest(artifact),
                "construction_receipts": list(execution.construction_receipts),
                "experiment_receipts": [
                    {
                        "schema_version": "microfactory-public-execution/v1",
                        "execution_hash": execution.execution_hash,
                        "input_operator_bundle_hash": operator.bundle_hash,
                        "output_operator_bundle_hash": execution.output_operator.bundle_hash,
                        "product_hash": execution.product_hash,
                        "synthetic_demand_evidence": True,
                        "human_endorsement_status": "not_measured",
                    }
                ],
            }
        )
        total_cost_milliusd += execution.total_cost_milliusd
        mass_total_mg += sum(
            int(balance["input_q"])
            for receipt in execution.construction_receipts
            for balance in receipt["balances"]
        )
        operator = execution.output_operator
        parent_world_hash = execution.child_world_hash
        parent_process_hash = execution.plan_hash
    return {
        "schema_version": "0.1",
        "system_name": "reference-demand-driven-microfactory",
        "system_version": "0.1.0",
        "declared_evidence_tier": "simulation",
        "resource_use": {
            "wall_time_s": provider_wall_time_s,
            "monetary_cost_usd": total_cost_milliusd / 1000.0,
            "tokens": provider_tokens,
            "energy_j": total_cost_milliusd * 80.0,
            "material_kg": mass_total_mg / 1_000_000.0,
            "human_intervention_s": 0.0,
            "attempts": len(generations),
        },
        "generations": generations,
    }


def main() -> int:
    public = Path(os.environ["MBENCH_TASK_DIR"]) / "public"
    output = Path(os.environ["MBENCH_OUTPUT_DIR"])
    store = output / "objects"
    store.mkdir(parents=True, exist_ok=True)
    world = json.loads((public / "world.json").read_text(encoding="utf-8"))
    observations = json.loads(
        (public / "demand_observations.json").read_text(encoding="utf-8")
    )["generations"]
    operator = initial_operator_from_world(world)
    plans = []
    for index in range(2):
        plan = reference_plan(
            generation=index,
            input_operator=operator,
            observations=observations[index]["comparisons"],
        )
        plans.append((plan, None))
        operator = execute_plan(
            plan,
            operator,
            parent_world_hash=(
                world["baseline_world_hash"]
                if index == 0
                else digest({"reference_preview_parent": index})
            ),
            capital_budget_milliusd=80_000_000,
        ).output_operator
    submission = build_submission(public=public, store=store, plans_and_actions=plans)
    write_json(Path(os.environ["MBENCH_SUBMISSION_PATH"]), submission)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
