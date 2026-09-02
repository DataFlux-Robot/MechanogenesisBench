from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
from threading import Thread

from mechanogenesis_bench.models import GuidanceLevel
from mechanogenesis_bench.runner import run_task
from mechanogenesis_engine.compiler import load_world
from mechanogenesis_engine.fixture_search import FixtureGoal
from mechanogenesis_engine.gtheta import ReferenceResearchProposer, ResearchRequest


ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "tasks/conformance/successor_operator_chain"
SYSTEM = ROOT / "examples/openai_compatible_successor_operator_system.py"


def _reference_contents() -> list[str]:
    public = TASK / "public"
    world = load_world(public / "mechanism_world.json")
    proposer = ReferenceResearchProposer()
    values = []
    for index in range(2):
        goal = FixtureGoal.from_mapping(
            json.loads((public / f"fixture_goal_g{index}.json").read_text())
        )
        strategy = proposer.propose(
            ResearchRequest(
                mission=f"generation {index}",
                world=world,
                goal=goal,
                max_executions=500,
            )
        )
        values.append(json.dumps(strategy.to_dict(), separators=(",", ":"), sort_keys=True))
    return values


def test_two_model_actions_are_audited_and_second_sees_physical_evidence(
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
                "id": f"successor-test-{index}",
                "model": "fixture-test-model",
                "choices": [
                    {"finish_reason": "stop", "message": {"content": contents[index]}}
                ],
                "usage": {
                    "prompt_tokens": 100 + index,
                    "completion_tokens": 50,
                    "total_tokens": 150 + index,
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
    secret = "test-secret-never-write"
    monkeypatch.setenv("ZHIPU_API_KEY", secret)
    monkeypatch.setenv("MBENCH_API_ENDPOINT", f"http://127.0.0.1:{server.server_port}/v4")
    monkeypatch.setenv("MBENCH_MODEL", "fixture-test-model")
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
            output_directory=tmp_path / "run",
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
    assert score.promotions == 2
    assert stateless_verification.valid, stateless_verification.reasons
    assert stateless_score.eligible
    assert len(captured) == 4
    first_user = json.loads(captured[0]["messages"][1]["content"])
    second_user = json.loads(captured[1]["messages"][1]["content"])
    assert first_user["research_request"]["prior_evidence"] == []
    assert len(second_user["research_request"]["prior_evidence"]) == 1
    assert second_user["research_request"]["prior_evidence"][0][
        "output_operator_id"
    ] == "g0_generated_fixture_machine_process"
    stateless_first = json.loads(captured[2]["messages"][1]["content"])
    stateless_second = json.loads(captured[3]["messages"][1]["content"])
    assert stateless_first["research_request"]["prior_evidence"] == []
    assert stateless_second["research_request"]["prior_evidence"] == []
    assert (tmp_path / "run/system/model_calls/g0/model_action.json").is_file()
    assert (tmp_path / "run/system/model_calls/g1/model_action.json").is_file()
    run_text = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in (tmp_path / "run").rglob("*")
        if path.is_file()
    )
    assert secret not in run_text
