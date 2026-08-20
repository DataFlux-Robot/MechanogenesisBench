from __future__ import annotations

import json
import os
from pathlib import Path
import shlex
import subprocess
import time
from typing import Sequence

from .errors import RunnerError
from .models import GuidanceLevel
from .score import ScoreCard, score_run
from .submission import EvaluationReport, Submission
from .task import TaskPackage
from .verify import VerificationReport, verify_run


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _write_run_manifest(
    run_dir: Path,
    *,
    task: TaskPackage,
    command: Sequence[str],
    guidance: GuidanceLevel,
    observed_wall_time_s: float,
    status: str,
    system_exit_code: int | None,
    evaluator_exit_code: int | None,
) -> None:
    _write_json(
        run_dir / "run.json",
        {
            "schema_version": "0.1",
            "status": status,
            "task_id": task.manifest.task_id,
            "task_source": str(task.root),
            "task_package_digest": task.package_digest,
            "guidance": guidance.value,
            "system_command": list(command),
            "isolation": "process_only_NOT_competition_safe",
            "observed_system_wall_time_s": observed_wall_time_s,
            "system_exit_code": system_exit_code,
            "evaluator_exit_code": evaluator_exit_code,
        },
    )


def load_completed_run(
    run_directory: str | Path,
) -> tuple[TaskPackage, Submission, EvaluationReport, float]:
    run_dir = Path(run_directory).resolve()
    try:
        metadata = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RunnerError(f"cannot load run metadata: {error}") from error
    if metadata.get("status") != "complete":
        raise RunnerError(f"run is not complete: status={metadata.get('status')!r}")
    task = TaskPackage.load(metadata.get("task_source", ""))
    if task.package_digest != metadata.get("task_package_digest"):
        raise RunnerError("task package changed after the run")
    submission = Submission.load(run_dir / "system" / "submission.json")
    evaluation = EvaluationReport.load(run_dir / "evaluation.json")
    observed = metadata.get("observed_system_wall_time_s")
    if isinstance(observed, bool) or not isinstance(observed, (int, float)) or observed < 0:
        raise RunnerError("run metadata has invalid observed wall time")
    return task, submission, evaluation, float(observed)


def evaluate_completed_run(
    run_directory: str | Path,
) -> tuple[VerificationReport, ScoreCard]:
    task, submission, evaluation, observed = load_completed_run(run_directory)
    verification = verify_run(
        task,
        submission,
        evaluation,
        observed_wall_time_s=observed,
    )
    return verification, score_run(task, submission, evaluation, verification)


def run_task(
    task_directory: str | Path,
    *,
    system_command: str | Sequence[str],
    guidance: GuidanceLevel,
    output_directory: str | Path,
) -> tuple[VerificationReport, ScoreCard]:
    task = TaskPackage.load(task_directory)
    if guidance not in task.manifest.guidance_levels:
        raise RunnerError(f"task does not support guidance {guidance.value}")

    command = (
        shlex.split(system_command) if isinstance(system_command, str) else list(system_command)
    )
    if not command:
        raise RunnerError("system command cannot be empty")

    run_dir = Path(output_directory).resolve()
    if run_dir.exists():
        raise RunnerError(f"refusing to overwrite existing run directory: {run_dir}")
    run_dir.mkdir(parents=True)
    public_task_dir = task.materialize_public(run_dir / "input", guidance)
    system_dir = run_dir / "system"
    system_dir.mkdir()
    submission_path = system_dir / "submission.json"

    environment = os.environ.copy()
    environment.update(
        {
            "MBENCH_TASK_DIR": str(public_task_dir),
            "MBENCH_OUTPUT_DIR": str(system_dir),
            "MBENCH_SUBMISSION_PATH": str(submission_path),
            "MBENCH_GUIDANCE": guidance.value,
            "MBENCH_TASK_PACKAGE_DIGEST": task.package_digest,
            "MBENCH_EVALUATOR_BUNDLE_DIGEST": task.evaluator_digest,
        }
    )

    started = time.monotonic()
    try:
        system_result = subprocess.run(
            command,
            env=environment,
            text=True,
            capture_output=True,
            timeout=max(task.manifest.budget.wall_time_s, 0.001),
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        observed = time.monotonic() - started
        (run_dir / "system.stdout.log").write_text(error.stdout or "", encoding="utf-8")
        (run_dir / "system.stderr.log").write_text(error.stderr or "", encoding="utf-8")
        _write_run_manifest(
            run_dir,
            task=task,
            command=command,
            guidance=guidance,
            observed_wall_time_s=observed,
            status="system_timeout",
            system_exit_code=None,
            evaluator_exit_code=None,
        )
        raise RunnerError("system exceeded the task wall-time budget") from error

    observed = time.monotonic() - started
    (run_dir / "system.stdout.log").write_text(system_result.stdout, encoding="utf-8")
    (run_dir / "system.stderr.log").write_text(system_result.stderr, encoding="utf-8")
    if system_result.returncode != 0:
        _write_run_manifest(
            run_dir,
            task=task,
            command=command,
            guidance=guidance,
            observed_wall_time_s=observed,
            status="system_failed",
            system_exit_code=system_result.returncode,
            evaluator_exit_code=None,
        )
        raise RunnerError(f"system process failed with exit code {system_result.returncode}")
    if not submission_path.is_file():
        _write_run_manifest(
            run_dir,
            task=task,
            command=command,
            guidance=guidance,
            observed_wall_time_s=observed,
            status="submission_missing",
            system_exit_code=system_result.returncode,
            evaluator_exit_code=None,
        )
        raise RunnerError("system did not produce submission.json")

    # Parse before executing trusted evaluator so malformed submissions fail early.
    Submission.load(submission_path)
    evaluation_path = run_dir / "evaluation.json"
    evaluator_command = [
        *task.manifest.evaluator_command,
        "--submission",
        str(submission_path),
        "--task-dir",
        str(task.root),
        "--output",
        str(evaluation_path),
    ]
    evaluator_result = subprocess.run(
        evaluator_command,
        cwd=task.root,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    (run_dir / "evaluator.stdout.log").write_text(
        evaluator_result.stdout, encoding="utf-8"
    )
    (run_dir / "evaluator.stderr.log").write_text(
        evaluator_result.stderr, encoding="utf-8"
    )
    if evaluator_result.returncode != 0 or not evaluation_path.is_file():
        _write_run_manifest(
            run_dir,
            task=task,
            command=command,
            guidance=guidance,
            observed_wall_time_s=observed,
            status="evaluator_failed",
            system_exit_code=system_result.returncode,
            evaluator_exit_code=evaluator_result.returncode,
        )
        raise RunnerError(
            f"trusted evaluator failed with exit code {evaluator_result.returncode}"
        )

    _write_run_manifest(
        run_dir,
        task=task,
        command=command,
        guidance=guidance,
        observed_wall_time_s=observed,
        status="complete",
        system_exit_code=system_result.returncode,
        evaluator_exit_code=evaluator_result.returncode,
    )
    verification, score = evaluate_completed_run(run_dir)
    _write_json(run_dir / "verification.json", verification.to_dict())
    _write_json(run_dir / "score.json", score.to_dict())
    return verification, score
