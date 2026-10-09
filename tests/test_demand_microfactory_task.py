from __future__ import annotations

import json
from pathlib import Path
import os
import subprocess
import sys

from mechanogenesis_bench.canonical import digest
from mechanogenesis_bench.models import GuidanceLevel
from mechanogenesis_bench.runner import run_task
from mechanogenesis_bench.task import TaskPackage


ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "tasks/simulation/demand_driven_microfactory"
SYSTEM = ROOT / "examples/reference_demand_microfactory_system.py"


def test_demand_microfactory_reference_run(tmp_path: Path, monkeypatch) -> None:
    package = TaskPackage.load(TASK)
    assert package.manifest.generations == 2
    assert package.manifest.evidence_ceiling.value == "simulation"
    existing = os.environ.get("PYTHONPATH", "")
    monkeypatch.setenv(
        "PYTHONPATH",
        str(ROOT / "src") + (os.pathsep + existing if existing else ""),
    )
    verification, score = run_task(
        TASK,
        system_command=[sys.executable, str(SYSTEM)],
        guidance=GuidanceLevel.G5,
        output_directory=tmp_path / "run",
    )
    assert verification.valid, verification.reasons
    assert score.eligible
    assert score.promotions == 2
    evaluation = json.loads((tmp_path / "run/evaluation.json").read_text())
    metrics = evaluation["microfactory_metrics"]
    assert metrics["exact_operator_inheritance"]
    assert metrics["demand_update_gain_ppm"] >= 400000
    assert metrics["inheritance_advantage_ppm"] >= 50000
    assert metrics["human_endorsed_positive_surprise_count"] == 0
    assert evaluation["lean_certificate"]["status"] == "accepted"
    certificate_path = tmp_path / "run/demand_microfactory_certificate.json"
    assert certificate_path.is_file()
    certificate = json.loads(certificate_path.read_text(encoding="utf-8"))
    assert evaluation["lean_certificate"]["sha256"] == digest(certificate)
    submission = json.loads(
        (tmp_path / "run/system/submission.json").read_text(encoding="utf-8")
    )
    assert certificate["generation0"]["planHash"] == (
        submission["generations"][0]["artifact"]["plan_hash"]
    )
    assert certificate["generation1"]["executionHash"] == (
        submission["generations"][1]["artifact"]["execution_hash"]
    )
    assert (
        certificate["generation0"]["outputOperator"]["bundleHash"]
        == certificate["generation1"]["inputOperator"]["bundleHash"]
    )
    checker = ROOT / ".lake/build/bin/demandMicrofactoryCheck"
    accepted = subprocess.run(
        [str(checker), str(certificate_path)], capture_output=True, text=True
    )
    assert accepted.returncode == 0, accepted.stderr

    broken_lineage = json.loads(json.dumps(certificate))
    broken_lineage["generation1"]["inputOperator"]["bundleHash"] = (
        "sha256:" + "0" * 64
    )
    broken_path = tmp_path / "broken-lineage.json"
    broken_path.write_text(json.dumps(broken_lineage), encoding="utf-8")
    rejected = subprocess.run(
        [str(checker), str(broken_path)], capture_output=True, text=True
    )
    assert rejected.returncode != 0

    false_endorsement = json.loads(json.dumps(certificate))
    false_endorsement["generation1"]["humanEndorsedPositiveSurprise"] = True
    endorsement_path = tmp_path / "false-endorsement.json"
    endorsement_path.write_text(json.dumps(false_endorsement), encoding="utf-8")
    rejected = subprocess.run(
        [str(checker), str(endorsement_path)], capture_output=True, text=True
    )
    assert rejected.returncode != 0
