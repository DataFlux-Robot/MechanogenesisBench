#!/usr/bin/env python3
"""Audited two-call LLM adapter for demand-driven microfactory planning."""

from __future__ import annotations

from datetime import datetime, timezone
from dataclasses import asdict
import json
import os
from pathlib import Path
import time

from mechanogenesis_bench.canonical import digest
from mechanogenesis_bench.demand_microfactory import (
    MicrofactoryPlan,
    execute_plan,
    initial_operator_from_world,
)
from mechanogenesis_engine.gtheta import OpenAICompatibleJSONGenerator

from openai_compatible_fixture_system import (
    append_jsonl,
    env_float,
    env_int,
    model_action_record,
    replay_generation,
    write_json,
)
from reference_demand_microfactory_system import build_submission


SYSTEM_PROMPT = """You are an autonomous product-and-production researcher.
Infer a calibrated demand belief from aggregate preference evidence, then emit
one complete low-speed mobility product and microfactory capital plan. Your
action directly fixes the product, mechanical assembly fixture, PCB test
fixture and battery calibration station; no downstream search will choose
parameters for you.

Return exactly one bare JSON object with schema demand-microfactory-plan/v1.
The required fields and example are in the supplied benchmark guidance. Both
ppm mappings must sum to 1,000,000. Use the exact available operator bundle
hash. Do not claim real human endorsement: observations in this task are
synthetic benchmark stimuli."""


def _parse_plan(content: str, *, generation: int, operator_hash: str) -> MicrofactoryPlan:
    try:
        raw = json.loads(content.strip())
    except json.JSONDecodeError as error:
        raise ValueError("model action is not one exact JSON object") from error
    if not isinstance(raw, dict):
        raise ValueError("model action must be a JSON object")
    plan = MicrofactoryPlan.from_mapping(raw)
    if plan.generation != generation:
        raise ValueError("model plan has the wrong generation")
    if plan.input_operator_bundle_hash != operator_hash:
        raise ValueError("model plan did not bind the exact available operator")
    return plan


def generate_plan(
    *,
    generation_index: int,
    current_operator,
    mission: dict[str, object],
    demand_evidence: dict[str, object],
    prior_evidence: list[dict[str, object]],
    guidance: str,
    output: Path,
    endpoint: str,
    model: str,
    api_key: str,
):
    replay_raw = os.environ.get(f"MBENCH_REPLAY_MODEL_CALL_G{generation_index}")
    if replay_raw:
        generation = replay_generation(Path(replay_raw).resolve(), expected_model=model)
        plan = _parse_plan(
            generation.content,
            generation=generation_index,
            operator_hash=current_operator.bundle_hash,
        )
        action = model_action_record(generation, endpoint=endpoint)
        append_jsonl(
            output / "model_attempts.jsonl",
            {
                "schema_version": "mbench-model-attempt/v1",
                "attempt": 0,
                "status": "replayed",
                "model": model,
                "request_payload_hash": action["request_payload_hash"],
                "response_content_hash": action["response_content_hash"],
                "recorded_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        write_json(output / "model_action.json", action)
        return plan, generation, action

    thinking_raw = os.environ.get("MBENCH_THINKING", "enabled")
    reasoning_raw = os.environ.get("MBENCH_REASONING_EFFORT", "max")
    generator = OpenAICompatibleJSONGenerator(
        endpoint=endpoint,
        model=model,
        api_key=api_key,
        timeout_s=env_float("MBENCH_API_TIMEOUT_S", 120.0),
        temperature=env_float("MBENCH_TEMPERATURE", 1.0),
        top_p=env_float("MBENCH_TOP_P", 0.95),
        max_tokens=env_int("MBENCH_MAX_TOKENS", 8192),
        json_response=True,
        thinking=None if thinking_raw == "omit" else thinking_raw,
        reasoning_effort=None if reasoning_raw == "omit" else reasoning_raw,
    )
    user = {
        "schema_version": "demand-microfactory-model-request/v1",
        "generation": generation_index,
        "mission": mission,
        "current_demand_evidence": demand_evidence,
        "available_operator_bundle": asdict(current_operator),
        "prior_public_evidence": prior_evidence,
        "benchmark_guidance": guidance,
    }
    attempts_path = output / "model_attempts.jsonl"
    max_attempts = env_int("MBENCH_MAX_ATTEMPTS", 1)
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            generated = generator.generate(
                system_prompt=SYSTEM_PROMPT,
                user_content=json.dumps(user, sort_keys=True, ensure_ascii=False),
            )
            plan = _parse_plan(
                generated.content,
                generation=generation_index,
                operator_hash=current_operator.bundle_hash,
            )
        except ValueError as error:
            last_error = error
            append_jsonl(
                attempts_path,
                {
                    "schema_version": "mbench-model-attempt/v1",
                    "attempt": attempt,
                    "status": "failed",
                    "model": model,
                    "error_type": type(error).__name__,
                    "error": str(error),
                    "recorded_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            if attempt < max_attempts:
                time.sleep(min(2 ** (attempt - 1), 4))
            continue
        action = model_action_record(generated, endpoint=endpoint)
        append_jsonl(
            attempts_path,
            {
                "schema_version": "mbench-model-attempt/v1",
                "attempt": attempt,
                "status": "succeeded",
                "model": model,
                "request_payload_hash": action["request_payload_hash"],
                "response_content_hash": action["response_content_hash"],
                "provider_request_id": generated.receipt.provider_request_id,
                "recorded_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        write_json(output / "model_action.json", action)
        return plan, generated, action
    assert last_error is not None
    raise last_error


def main() -> int:
    task_root = Path(os.environ["MBENCH_TASK_DIR"])
    public = task_root / "public"
    output = Path(os.environ["MBENCH_OUTPUT_DIR"])
    store = output / "objects"
    store.mkdir(parents=True, exist_ok=True)
    endpoint = os.environ.get(
        "MBENCH_API_ENDPOINT", "https://open.bigmodel.cn/api/paas/v4"
    )
    model = os.environ.get("MBENCH_MODEL", "glm-5.3-flash")
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
    history_mode = os.environ.get("MBENCH_HISTORY_MODE", "public_evidence")
    if history_mode not in {"none", "public_evidence"}:
        raise SystemExit("MBENCH_HISTORY_MODE must be none or public_evidence")

    world = json.loads((public / "world.json").read_text(encoding="utf-8"))
    observations = json.loads(
        (public / "demand_observations.json").read_text(encoding="utf-8")
    )["generations"]
    briefs = json.loads((public / "demand_briefs.json").read_text(encoding="utf-8"))[
        "briefs"
    ]
    contract = json.loads(
        (public / "evaluator_contract.json").read_text(encoding="utf-8")
    )
    guidance = (task_root / "mission.md").read_text(encoding="utf-8")
    operator = initial_operator_from_world(world)
    parent_world_hash = world["baseline_world_hash"]
    prior_evidence: list[dict[str, object]] = []
    plans_and_actions = []
    provider_generations = []
    for index in range(2):
        plan, generated, action = generate_plan(
            generation_index=index,
            current_operator=operator,
            mission=briefs[index],
            demand_evidence=observations[index],
            prior_evidence=(prior_evidence if history_mode == "public_evidence" else []),
            guidance=guidance,
            output=output / "model_calls" / f"g{index}",
            endpoint=endpoint,
            model=model,
            api_key=api_key,
        )
        execution = execute_plan(
            plan,
            operator,
            parent_world_hash=parent_world_hash,
            capital_budget_milliusd=contract["capital_budget_milliusd"][index],
        )
        prior_evidence.append(
            {
                "schema_version": "microfactory-public-evidence/v1",
                "generation": index,
                "demand_belief": {
                    "attribute_weights_ppm": plan.demand_belief.weight_map,
                    "outcome_forecast_ppm": plan.demand_belief.outcome_map,
                },
                "product_hash": execution.product_hash,
                "product_metrics": execution.metrics,
                "output_operator_bundle": asdict(execution.output_operator),
                "capital_cost_milliusd": execution.capital_cost_milliusd,
            }
        )
        plans_and_actions.append((plan, action))
        provider_generations.append(generated)
        operator = execution.output_operator
        parent_world_hash = execution.child_world_hash

    tokens = 0
    wall_us = 0
    for generated in provider_generations:
        observed_tokens = generated.receipt.usage.get("total_tokens", 0)
        if isinstance(observed_tokens, int) and not isinstance(observed_tokens, bool):
            tokens += observed_tokens
        wall_us += generated.receipt.wall_time_us
    submission = build_submission(
        public=public,
        store=store,
        plans_and_actions=plans_and_actions,
        provider_wall_time_s=wall_us / 1_000_000.0,
        provider_tokens=tokens,
    )
    submission["system_name"] = f"openai-compatible-{model}-{history_mode}"
    submission["resource_use"]["monetary_cost_usd"] += float(
        os.environ.get("MBENCH_MODEL_COST_USD", "0")
    )
    write_json(Path(os.environ["MBENCH_SUBMISSION_PATH"]), submission)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
