from __future__ import annotations

from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
from threading import Thread

from mechanogenesis_bench.demand_microfactory import (
    execute_plan,
    initial_operator_from_world,
    reference_plan,
)
from mechanogenesis_bench.models import GuidanceLevel
from mechanogenesis_bench.runner import run_task


ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "tasks/simulation/demand_driven_microfactory"
SYSTEM = ROOT / "examples/openai_compatible_demand_microfactory_system.py"


def _reference_contents() -> list[str]:
    public = TASK / "public"
    world = json.loads((public / "world.json").read_text())
    observations = json.loads(
        (public / "demand_observations.json").read_text()
    )["generations"]
    operator = initial_operator_from_world(world)
    parent = world["baseline_world_hash"]
    values = []
    for index in range(2):
        plan = reference_plan(
            generation=index,
            input_operator=operator,
            observations=observations[index]["comparisons"],
        )
        values.append(json.dumps(plan.to_dict(), separators=(",", ":"), sort_keys=True))
        execution = execute_plan(
            plan,
            operator,
            parent_world_hash=parent,
            capital_budget_milliusd=80_000_000,
        )
        operator = execution.output_operator
        parent = execution.child_world_hash
    return values


def test_two_complete_model_plans_are_audited_and_history_is_explicit(
    tmp_path: Path, monkeypatch
) -> None:
    captured: list[dict[str, object]] = []
    contents = _reference_contents()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers["Content-Length"])
            captured.append(json.loads(self.rfile.read(length)))
            index = (len(captured) - 1) % 2
            envelope = {
                "id": f"microfactory-test-{index}",
                "model": "microfactory-test-model",
                "choices": [
                    {"finish_reason": "stop", "message": {"content": contents[index]}}
                ],
                "usage": {
                    "prompt_tokens": 500 + index,
                    "completion_tokens": 300,
                    "total_tokens": 800 + index,
                },
            }
            body = json.dumps(envelope).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format: str, *_args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    secret = "microfactory-test-secret-never-write"
    monkeypatch.setenv("ZHIPU_API_KEY", secret)
    monkeypatch.setenv("MBENCH_API_ENDPOINT", f"http://127.0.0.1:{server.server_port}/v4")
    monkeypatch.setenv("MBENCH_MODEL", "microfactory-test-model")
    monkeypatch.setenv("MBENCH_THINKING", "omit")
    monkeypatch.setenv("MBENCH_REASONING_EFFORT", "omit")
    existing = os.environ.get("PYTHONPATH", "")
    monkeypatch.setenv(
        "PYTHONPATH",
        str(ROOT / "src") + (os.pathsep + existing if existing else ""),
    )
    try:
        verification, score = run_task(
            TASK,
            system_command=[sys.executable, str(SYSTEM)],
            guidance=GuidanceLevel.G5,
            output_directory=tmp_path / "history",
        )
        monkeypatch.setenv("MBENCH_HISTORY_MODE", "none")
        stateless_verification, stateless_score = run_task(
            TASK,
            system_command=[sys.executable, str(SYSTEM)],
            guidance=GuidanceLevel.G5,
            output_directory=tmp_path / "stateless",
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert verification.valid, verification.reasons
    assert score.eligible
    assert stateless_verification.valid, stateless_verification.reasons
    assert stateless_score.eligible
    assert len(captured) == 4
    history_g0 = json.loads(captured[0]["messages"][1]["content"])
    history_g1 = json.loads(captured[1]["messages"][1]["content"])
    stateless_g1 = json.loads(captured[3]["messages"][1]["content"])
    assert history_g0["prior_public_evidence"] == []
    assert len(history_g1["prior_public_evidence"]) == 1
    assert stateless_g1["prior_public_evidence"] == []
    assert history_g1["available_operator_bundle"]["bundle_hash"] == (
        history_g1["prior_public_evidence"][0]["output_operator_bundle"]["bundle_hash"]
    )
    run_text = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in (tmp_path / "history").rglob("*")
        if path.is_file()
    )
    assert secret not in run_text
    assert (tmp_path / "history/system/model_calls/g0/model_action.json").is_file()
    assert (tmp_path / "history/system/model_calls/g1/model_action.json").is_file()
