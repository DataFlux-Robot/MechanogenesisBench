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
TASK = ROOT / "tasks/conformance/generated_metrology_fixture"
SYSTEM = ROOT / "examples/openai_compatible_fixture_system.py"


def reference_strategy_content() -> str:
    world = load_world(TASK / "public/mechanism_world.json")
    goal = FixtureGoal.from_mapping(
        json.loads((TASK / "public/fixture_goal.json").read_text(encoding="utf-8"))
    )
    request = ResearchRequest(
        mission=(TASK / "guidance/G5.md").read_text(encoding="utf-8"),
        world=world,
        goal=goal,
        max_executions=500,
    )
    return json.dumps(
        ReferenceResearchProposer().propose(request).to_dict(),
        separators=(",", ":"),
        sort_keys=True,
    )


def test_generic_model_adapter_is_scored_and_retains_action_bytes(
    tmp_path: Path, monkeypatch
) -> None:
    captured: dict[str, object] = {}
    content = reference_strategy_content()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers["Content-Length"])
            captured["authorization"] = self.headers.get("Authorization")
            captured["request"] = json.loads(self.rfile.read(length))
            envelope = {
                "id": "fixture-test-request",
                "model": "fixture-test-model",
                "choices": [
                    {"finish_reason": "stop", "message": {"content": content}}
                ],
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 50,
                    "total_tokens": 150,
                },
            }
            body = json.dumps(envelope).encode("utf-8")
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
    monkeypatch.setenv(
        "MBENCH_API_ENDPOINT", f"http://127.0.0.1:{server.server_port}/v4"
    )
    monkeypatch.setenv("MBENCH_MODEL", "fixture-test-model")
    monkeypatch.setenv("MBENCH_THINKING", "omit")
    monkeypatch.setenv("MBENCH_REASONING_EFFORT", "omit")
    monkeypatch.setenv("MBENCH_TOP_P", "0.95")
    existing_pythonpath = os.environ.get("PYTHONPATH", "")
    monkeypatch.setenv(
        "PYTHONPATH",
        str(ROOT / "src")
        + (os.pathsep + existing_pythonpath if existing_pythonpath else ""),
    )
    try:
        verification, score = run_task(
            TASK,
            system_command=[sys.executable, str(SYSTEM)],
            guidance=GuidanceLevel.G5,
            output_directory=tmp_path / "run",
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert verification.valid
    assert score.eligible
    assert score.promotions == 1
    assert score.capability_gain == 640.0
    assert score.robustness_pass_rate == 1.0
    assert captured["authorization"] == f"Bearer {secret}"
    assert captured["request"]["response_format"] == {"type": "json_object"}
    assert captured["request"]["top_p"] == 0.95

    action_path = tmp_path / "run/system/model_action.json"
    action = json.loads(action_path.read_text(encoding="utf-8"))
    assert action["response_content"] == content
    assert action["response_envelope_status"] == "complete"
    assert action["response_envelope"]["id"] == "fixture-test-request"
    assert (
        action["response_envelope_hash"]
        == action["provider_receipt"]["response_hash"]
    )
    assert action["provider_receipt"]["usage"]["total_tokens"] == 150
    run_text = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in (tmp_path / "run").rglob("*")
        if path.is_file()
    )
    assert secret not in run_text

    submission = json.loads(
        (tmp_path / "run/system/submission.json").read_text(encoding="utf-8")
    )
    assert submission["resource_use"]["tokens"] == 150
    update_digest = submission["generations"][0]["mrs"]["update_proposal"]
    update_object = json.loads(
        (
            tmp_path
            / "run/system/objects"
            / f"{update_digest[7:]}.json"
        ).read_text(encoding="utf-8")
    )
    assert update_object["model_action"] == action
    assert os.environ["ZHIPU_API_KEY"] == secret

    monkeypatch.delenv("ZHIPU_API_KEY")
    monkeypatch.setenv("MBENCH_REPLAY_MODEL_CALL", str(action_path))
    replay_verification, replay_score = run_task(
        TASK,
        system_command=[sys.executable, str(SYSTEM)],
        guidance=GuidanceLevel.G5,
        output_directory=tmp_path / "replay",
    )
    assert replay_verification.valid
    assert replay_score.eligible
    replay_action = json.loads(
        (tmp_path / "replay/system/model_action.json").read_text(encoding="utf-8")
    )
    assert replay_action["request_payload_status"] == "complete"
    assert replay_action["request_payload_hash"] == action["request_payload_hash"]
    assert replay_action["response_content_hash"] == action["response_content_hash"]
    assert replay_action["response_envelope_hash"] == action["response_envelope_hash"]
    replay_submission = json.loads(
        (tmp_path / "replay/system/submission.json").read_text(encoding="utf-8")
    )
    assert (
        replay_submission["resource_use"]["wall_time_s"]
        == submission["resource_use"]["wall_time_s"]
    )
