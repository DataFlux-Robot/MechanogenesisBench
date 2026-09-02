#!/usr/bin/env python3
"""Audited third-party LLM baseline for the generated fixture task.

The model proposes only the typed research strategy.  The benchmark-owned
compiler, canonical interpreter, Lean certificate emitter and trusted evaluator
remain outside the model boundary.  The exact model-facing request and exact
returned action text are content-addressed inside the submitted MRS bundle.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
import tomllib

from mechanogenesis_bench.canonical import digest
from mechanogenesis_engine.compiler import load_world
from mechanogenesis_engine.errors import ExecutionError, IRValidationError
from mechanogenesis_engine.fixture_search import FixtureGoal
from mechanogenesis_engine.gtheta import (
    GThetaRuntime,
    JSONGeneration,
    JSONGenerationReceipt,
    OpenAICompatibleJSONGenerator,
    OpenAICompatibleProposer,
    ResearchRequest,
    StaticStrategyProposer,
)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def append_jsonl(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(
            json.dumps(value, sort_keys=True, ensure_ascii=False) + "\n"
        )


def store_object(store: Path, value: object) -> str:
    object_digest = digest(value)
    write_json(store / f"{object_digest[7:]}.json", value)
    return object_digest


def env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return default
    value = float(raw)
    if value < 0:
        raise ValueError(f"{name} must be nonnegative")
    return value


def env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    value = int(raw)
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


def model_action_record(generation, *, endpoint: str) -> dict[str, object]:
    action: dict[str, object] = {
        "schema_version": "mbench-model-action/v1",
        "endpoint": endpoint.rstrip("/"),
        "response_content": generation.content,
        "response_content_hash": digest(generation.content),
        "provider_receipt": generation.receipt.to_dict(),
    }
    if generation.request_payload is None:
        action["request_payload_status"] = "legacy_hash_only"
        action["request_payload_hash"] = generation.receipt.request_hash
    else:
        action["request_payload_status"] = "complete"
        action["request_payload"] = dict(generation.request_payload)
        action["request_payload_hash"] = digest(generation.request_payload)
    if generation.response_envelope is None:
        action["response_envelope_status"] = "unavailable"
    else:
        action["response_envelope_status"] = "complete"
        action["response_envelope"] = dict(generation.response_envelope)
        action["response_envelope_hash"] = digest(generation.response_envelope)
    return action


def replay_generation(path: Path, *, expected_model: str) -> JSONGeneration:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("replay model call must be an object")
    is_action_record = raw.get("schema_version") == "mbench-model-action/v1"
    content_key = "response_content" if is_action_record else "content"
    content_hash_key = (
        "response_content_hash" if is_action_record else "content_hash"
    )
    content = raw.get(content_key)
    receipt_raw = raw.get("provider_receipt")
    if not isinstance(content, str) or not isinstance(receipt_raw, dict):
        raise ValueError("replay model call has invalid content or receipt")
    if raw.get(content_hash_key) != digest(content):
        raise ValueError("replay model call content hash mismatch")
    if receipt_raw.get("requested_model") != expected_model:
        raise ValueError("replay model call requested_model mismatch")
    usage = receipt_raw.get("usage")
    wall_time_us = receipt_raw.get("wall_time_us")
    if not isinstance(usage, dict):
        raise ValueError("replay provider usage must be an object")
    if (
        isinstance(wall_time_us, bool)
        or not isinstance(wall_time_us, int)
        or wall_time_us < 0
    ):
        raise ValueError("replay provider wall time is invalid")
    request_hash = receipt_raw.get("request_hash")
    response_hash = receipt_raw.get("response_hash")
    if not isinstance(request_hash, str) or not request_hash.startswith("sha256:"):
        raise ValueError("replay provider request hash is invalid")
    if not isinstance(response_hash, str) or not response_hash.startswith("sha256:"):
        raise ValueError("replay provider response hash is invalid")
    request_payload: dict[str, object] | None = None
    if raw.get("request_payload_status") == "complete":
        candidate_payload = raw.get("request_payload")
        if not isinstance(candidate_payload, dict):
            raise ValueError("complete replay request payload is missing")
        if raw.get("request_payload_hash") != digest(candidate_payload):
            raise ValueError("replay request payload hash mismatch")
        if request_hash != digest(candidate_payload):
            raise ValueError("provider receipt does not bind replay request payload")
        request_payload = candidate_payload
    response_envelope: dict[str, object] | None = None
    if raw.get("response_envelope_status") == "complete":
        candidate_envelope = raw.get("response_envelope")
        if not isinstance(candidate_envelope, dict):
            raise ValueError("complete replay response envelope is missing")
        if raw.get("response_envelope_hash") != digest(candidate_envelope):
            raise ValueError("replay response envelope hash mismatch")
        if response_hash != digest(candidate_envelope):
            raise ValueError("provider receipt does not bind replay response envelope")
        response_envelope = candidate_envelope
    return JSONGeneration(
        content=content,
        receipt=JSONGenerationReceipt(
            provider_request_id=(
                receipt_raw.get("provider_request_id")
                if isinstance(receipt_raw.get("provider_request_id"), str)
                else None
            ),
            requested_model=expected_model,
            returned_model=(
                receipt_raw.get("returned_model")
                if isinstance(receipt_raw.get("returned_model"), str)
                else None
            ),
            request_hash=request_hash,
            response_hash=response_hash,
            finish_reason=(
                receipt_raw.get("finish_reason")
                if isinstance(receipt_raw.get("finish_reason"), str)
                else None
            ),
            usage=usage,
            wall_time_us=wall_time_us,
        ),
        request_payload=request_payload,
        response_envelope=response_envelope,
    )


def generate_strategy(
    request: ResearchRequest,
    *,
    output: Path,
    endpoint: str,
    model: str,
    api_key: str,
):
    replay_path_raw = os.environ.get("MBENCH_REPLAY_MODEL_CALL")
    if replay_path_raw:
        replay_path = Path(replay_path_raw).resolve()
        generation = replay_generation(replay_path, expected_model=model)
        strategy = OpenAICompatibleProposer.parse_content(generation.content)
        StaticStrategyProposer(strategy).propose(request)
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
                "source_call_hash": digest(
                    json.loads(replay_path.read_text(encoding="utf-8"))
                ),
                "recorded_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        write_json(output / "model_action.json", action)
        return strategy, generation, action

    thinking_raw = os.environ.get("MBENCH_THINKING", "enabled")
    thinking = None if thinking_raw == "omit" else thinking_raw
    reasoning_raw = os.environ.get("MBENCH_REASONING_EFFORT", "low")
    reasoning_effort = None if reasoning_raw == "omit" else reasoning_raw
    generator = OpenAICompatibleJSONGenerator(
        endpoint=endpoint,
        model=model,
        api_key=api_key,
        timeout_s=env_float("MBENCH_API_TIMEOUT_S", 80.0),
        temperature=env_float("MBENCH_TEMPERATURE", 0.1),
        top_p=(
            env_float("MBENCH_TOP_P", 0.95)
            if "MBENCH_TOP_P" in os.environ
            else None
        ),
        max_tokens=env_int("MBENCH_MAX_TOKENS", 8192),
        json_response=True,
        thinking=thinking,
        reasoning_effort=reasoning_effort,
    )
    system_prompt, user_content = OpenAICompatibleProposer.proposal_prompt(request)
    attempts_path = output / "model_attempts.jsonl"
    max_attempts = env_int("MBENCH_MAX_ATTEMPTS", 1)
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            generation = generator.generate(
                system_prompt=system_prompt,
                user_content=user_content,
            )
            strategy = OpenAICompatibleProposer.parse_content(generation.content)
            StaticStrategyProposer(strategy).propose(request)
        except (ExecutionError, IRValidationError, ValueError) as error:
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
        action = model_action_record(generation, endpoint=endpoint)
        append_jsonl(
            attempts_path,
            {
                "schema_version": "mbench-model-attempt/v1",
                "attempt": attempt,
                "status": "succeeded",
                "model": model,
                "request_payload_hash": action["request_payload_hash"],
                "response_content_hash": action["response_content_hash"],
                "provider_request_id": generation.receipt.provider_request_id,
                "recorded_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        write_json(output / "model_action.json", action)
        return strategy, generation, action
    assert last_error is not None
    raise last_error


def main() -> int:
    public_root = Path(os.environ["MBENCH_TASK_DIR"]) / "public"
    output = Path(os.environ["MBENCH_OUTPUT_DIR"])
    store = output / "objects"
    store.mkdir(parents=True, exist_ok=True)

    endpoint = os.environ.get(
        "MBENCH_API_ENDPOINT", "https://open.bigmodel.cn/api/paas/v4"
    )
    model = os.environ.get("MBENCH_MODEL", "glm-5.3-flash")
    api_key_env = os.environ.get("MBENCH_API_KEY_ENV", "ZHIPU_API_KEY")
    api_key = os.environ.get(api_key_env, "")
    replay_requested = bool(os.environ.get("MBENCH_REPLAY_MODEL_CALL"))
    if not api_key and not replay_requested:
        raise SystemExit(
            f"missing {api_key_env}; provide the credential only through the process environment"
        )
    if replay_requested:
        api_key = "offline-replay-no-credential"

    world = load_world(public_root / "mechanism_world.json")
    raw_goal = json.loads(
        (public_root / "fixture_goal.json").read_text(encoding="utf-8")
    )
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

    strategy, generation, action = generate_strategy(
        request,
        output=output,
        endpoint=endpoint,
        model=model,
        api_key=api_key,
    )
    research = GThetaRuntime(StaticStrategyProposer(strategy)).run_fixture(
        request, evaluator_contract=evaluator_contract
    )
    result = research.search_result
    assert result.qualified_process_capability_id is not None
    update_object = research.mrs_objects["update_proposal"]
    if not isinstance(update_object, dict):
        raise ExecutionError("update proposal MRS object is malformed")
    update_object["model_action"] = action
    mrs = {
        name: store_object(store, value)
        for name, value in research.mrs_objects.items()
    }

    capability = result.execution.final_state["capabilities"][
        "generated_fixture_metrology"
    ]
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
        "proposer_id": f"openai-compatible:{model}",
        "model_action_hash": digest(action),
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
    usage = generation.receipt.usage
    total_tokens = usage.get("total_tokens", 0)
    if isinstance(total_tokens, bool) or not isinstance(total_tokens, int):
        total_tokens = 0
    cost_env_present = "MBENCH_MODEL_COST_USD" in os.environ
    model_cost_usd = env_float("MBENCH_MODEL_COST_USD", 0.0)
    submission = {
        "schema_version": "0.1",
        "system_name": f"openai-compatible-{model}",
        "system_version": "0.1.0",
        "declared_evidence_tier": "conformance",
        "resource_use": {
            "wall_time_s": generation.receipt.wall_time_us / 1_000_000.0,
            "monetary_cost_usd": model_cost_usd,
            "tokens": total_tokens,
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
                        "kind": "public_strategy_and_canonical_execution",
                        "model_action_hash": digest(action),
                        "model_cost_status": (
                            "operator_supplied" if cost_env_present else "unreported"
                        ),
                        "remote_model_energy_status": "unobserved",
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
