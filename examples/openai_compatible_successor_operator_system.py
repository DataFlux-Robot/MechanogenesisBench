#!/usr/bin/env python3
"""Audited two-call LLM system for the physical successor-operator task."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tomllib

from mechanogenesis_bench.canonical import digest
from mechanogenesis_bench.successor_operator import execute_successor_operator_chain
from mechanogenesis_engine.compiler import load_world
from mechanogenesis_engine.fixture_search import FixtureGoal
from mechanogenesis_engine.gtheta import GThetaRuntime, ResearchRequest, StaticStrategyProposer

from openai_compatible_fixture_system import generate_strategy, store_object, write_json


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

    endpoint = os.environ.get(
        "MBENCH_API_ENDPOINT", "https://open.bigmodel.cn/api/paas/v4"
    )
    model = os.environ.get("MBENCH_MODEL", "glm-5.3-flash")
    history_mode = os.environ.get("MBENCH_HISTORY_MODE", "public_evidence")
    if history_mode not in {"none", "public_evidence"}:
        raise SystemExit(
            "MBENCH_HISTORY_MODE must be 'none' or 'public_evidence'"
        )
    api_key_env = os.environ.get("MBENCH_API_KEY_ENV", "ZHIPU_API_KEY")
    api_key = os.environ.get(api_key_env, "")
    replay_paths = [
        os.environ.get(f"MBENCH_REPLAY_MODEL_CALL_G{index}") for index in range(2)
    ]
    if not api_key and not all(replay_paths):
        raise SystemExit(
            f"missing {api_key_env}; provide the credential only through the process environment"
        )
    if all(replay_paths):
        api_key = "offline-replay-no-credential"

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

    strategies = []
    actions = []
    provider_generations = []
    prior_evidence: list[dict[str, object]] = []
    parent_state = None
    process_capability_id = None
    original_replay = os.environ.get("MBENCH_REPLAY_MODEL_CALL")
    try:
        for index, goal in enumerate(goals):
            replay_path = replay_paths[index]
            if replay_path:
                os.environ["MBENCH_REPLAY_MODEL_CALL"] = replay_path
            else:
                os.environ.pop("MBENCH_REPLAY_MODEL_CALL", None)
            request = ResearchRequest(
                mission=json.dumps(briefs[index], sort_keys=True),
                world=world,
                goal=goal,
                max_executions=int(manifest["budget"]["attempts"]) // 2,
                prior_evidence=(
                    tuple(prior_evidence)
                    if history_mode == "public_evidence"
                    else ()
                ),
            )
            strategy, provider_generation, action = generate_strategy(
                request,
                output=output / "model_calls" / f"g{index}",
                endpoint=endpoint,
                model=model,
                api_key=api_key,
            )
            preview = GThetaRuntime(StaticStrategyProposer(strategy)).run_fixture(
                request,
                evaluator_contract=evaluator_contract,
                parent_state=parent_state,
                namespace=f"g{index}",
                process_capability_id=process_capability_id,
            )
            result = preview.search_result
            assert result.qualified_process_capability_id is not None
            output_operator = result.execution.final_state["capabilities"][
                result.qualified_process_capability_id
            ]
            prior_evidence.append(
                {
                    "schema_version": "public-physical-evidence/v1",
                    "generation": index,
                    "program_hash": result.execution.process_hash,
                    "child_world_hash": result.execution.child_world_hash,
                    "selected_parameters": result.selected_parameters,
                    "output_operator_id": result.qualified_process_capability_id,
                    "output_operator": output_operator,
                }
            )
            strategies.append(strategy)
            actions.append(action)
            provider_generations.append(provider_generation)
            parent_state = result.execution.final_state
            process_capability_id = result.qualified_process_capability_id
    finally:
        if original_replay is None:
            os.environ.pop("MBENCH_REPLAY_MODEL_CALL", None)
        else:
            os.environ["MBENCH_REPLAY_MODEL_CALL"] = original_replay

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
    for edge, action in zip(chain.generations, actions, strict=True):
        result = edge.run.search_result
        mrs_objects = dict(edge.run.mrs_objects)
        update = dict(mrs_objects["update_proposal"])
        update["model_action"] = action
        mrs_objects["update_proposal"] = update
        mrs = {name: store_object(store, value) for name, value in mrs_objects.items()}
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

    total_tokens = 0
    total_wall_time_us = 0
    for provider_generation in provider_generations:
        usage = provider_generation.receipt.usage.get("total_tokens", 0)
        if not isinstance(usage, bool) and isinstance(usage, int):
            total_tokens += usage
        total_wall_time_us += provider_generation.receipt.wall_time_us
    write_json(
        Path(os.environ["MBENCH_SUBMISSION_PATH"]),
        {
            "schema_version": "0.1",
            "system_name": f"openai-compatible-{model}-{history_mode}",
            "system_version": "0.1.0",
            "declared_evidence_tier": "conformance",
            "resource_use": {
                "wall_time_s": total_wall_time_us / 1_000_000.0,
                "monetary_cost_usd": float(os.environ.get("MBENCH_MODEL_COST_USD", "0")),
                "tokens": total_tokens,
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
