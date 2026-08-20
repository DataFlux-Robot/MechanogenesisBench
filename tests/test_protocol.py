from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys

import pytest

from mechanogenesis_bench.errors import SchemaError
from mechanogenesis_bench.models import GuidanceLevel
from mechanogenesis_bench.runner import evaluate_completed_run, run_task
from mechanogenesis_bench.submission import Submission
from mechanogenesis_bench.task import TaskPackage


ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "tasks/conformance/calibration_to_fixture"
REFERENCE = ROOT / "examples/reference_system.py"


def run_reference(tmp_path: Path, task: Path = TASK) -> Path:
    run_dir = tmp_path / "run"
    verification, score = run_task(
        task,
        system_command=[sys.executable, str(REFERENCE)],
        guidance=GuidanceLevel.G3,
        output_directory=run_dir,
    )
    assert verification.valid
    assert score.eligible
    return run_dir


def test_task_and_reference_episode_are_valid(tmp_path: Path) -> None:
    task = TaskPackage.load(TASK)
    assert task.manifest.generations == 2
    run_dir = run_reference(tmp_path)
    verification, score = evaluate_completed_run(run_dir)
    assert verification.valid
    assert verification.promotions == 2
    assert score.capability_gain == pytest.approx(0.385)
    assert score.certified_evidence_tier == "conformance"


def test_material_nonclosure_fails_closed(tmp_path: Path) -> None:
    run_dir = run_reference(tmp_path)
    submission_path = run_dir / "system/submission.json"
    submission = json.loads(submission_path.read_text(encoding="utf-8"))
    submission["generations"][0]["construction_receipts"][0]["balances"][0][
        "waste_q"
    ] += 1
    submission_path.write_text(json.dumps(submission), encoding="utf-8")
    verification, score = evaluate_completed_run(run_dir)
    assert not verification.valid
    assert not score.eligible
    assert any("material closure" in reason for reason in verification.reasons)


def test_mrs_hash_must_resolve_to_real_content(tmp_path: Path) -> None:
    run_dir = run_reference(tmp_path)
    submission_path = run_dir / "system/submission.json"
    raw = json.loads(submission_path.read_text(encoding="utf-8"))
    object_digest = raw["generations"][0]["mrs"]["language"]
    object_path = run_dir / "system/objects" / f"{object_digest[7:]}.json"
    object_path.write_text('{"tampered":true}\n', encoding="utf-8")
    with pytest.raises(SchemaError, match="does not match"):
        Submission.load(submission_path)


def test_private_evaluator_assets_are_version_bound(tmp_path: Path) -> None:
    task_copy = tmp_path / "task"
    shutil.copytree(TASK, task_copy)
    original = TaskPackage.load(task_copy)
    private_path = task_copy / "private/spec.json"
    private = json.loads(private_path.read_text(encoding="utf-8"))
    private["minimum_robustness"] = 0.99
    private_path.write_text(json.dumps(private), encoding="utf-8")
    modified = TaskPackage.load(task_copy)
    assert modified.package_digest == original.package_digest
    assert modified.evaluator_digest != original.evaluator_digest


def test_declared_evidence_cannot_exceed_ceiling(tmp_path: Path) -> None:
    run_dir = run_reference(tmp_path)
    submission_path = run_dir / "system/submission.json"
    submission = json.loads(submission_path.read_text(encoding="utf-8"))
    submission["declared_evidence_tier"] = "simulation"
    submission_path.write_text(json.dumps(submission), encoding="utf-8")
    verification, _ = evaluate_completed_run(run_dir)
    assert not verification.valid
    assert any("evidence tier exceeds" in reason for reason in verification.reasons)
