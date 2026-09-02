from __future__ import annotations

from pathlib import Path
import os
import sys

from mechanogenesis_bench.models import GuidanceLevel
from mechanogenesis_bench.runner import run_task
from mechanogenesis_bench.task import TaskPackage


ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "tasks/conformance/successor_operator_chain"
SYSTEM = ROOT / "examples/reference_successor_operator_system.py"


def test_successor_operator_task_package_and_reference_run(
    tmp_path: Path, monkeypatch
) -> None:
    package = TaskPackage.load(TASK)
    assert package.manifest.generations == 2
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
    assert verification.promotions == 2
    assert score.eligible
    assert score.robustness_pass_rate == 1.0
    assert score.capability_gain == 660.0
