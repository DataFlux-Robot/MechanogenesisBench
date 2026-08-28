from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from .errors import MechanogenesisBenchError
from .generalization import (
    EngineeringEvidenceReceipt,
    FactorizedCase,
    GeneralizationGate,
    evaluate_generalization,
    lean_generalization_certificate,
    registered_shortcut_projections,
)
from .models import GuidanceLevel
from .runner import evaluate_completed_run, run_task
from .task import TaskPackage


def _print_json(value: object) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mbench")
    commands = parser.add_subparsers(dest="command", required=True)

    task = commands.add_parser("task", help="task-package operations")
    task_commands = task.add_subparsers(dest="task_command", required=True)
    validate = task_commands.add_parser("validate", help="validate a task package")
    validate.add_argument("task_directory", type=Path)

    run = commands.add_parser("run", help="execute and independently evaluate a system")
    run.add_argument("task_directory", type=Path)
    run.add_argument("--system-command", required=True)
    run.add_argument("--guidance", type=GuidanceLevel, required=True)
    run.add_argument("--output", type=Path, required=True)

    verify = commands.add_parser("verify", help="re-verify a completed run")
    verify.add_argument("run_directory", type=Path)

    score = commands.add_parser("score", help="score a completed run")
    score.add_argument("run_directory", type=Path)

    generalization = commands.add_parser(
        "generalization", help="evaluator-owned anti-shortcut audit"
    )
    generalization_commands = generalization.add_subparsers(
        dest="generalization_command", required=True
    )
    audit = generalization_commands.add_parser(
        "audit", help="audit compositional generalization and engineering evidence"
    )
    audit.add_argument("corpus", type=Path)
    audit.add_argument("--predictions", type=Path, required=True)
    audit.add_argument("--engineering-receipt", type=Path, required=True)
    audit.add_argument("--shortcut-order", type=int, default=2)
    audit.add_argument("--allow-simulation-only", action="store_true")
    audit.add_argument("--certificate-output", type=Path)
    audit.add_argument("--lean-checker", type=Path)
    return parser


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _audit_generalization(args: argparse.Namespace) -> dict[str, object]:
    corpus = _load_json(args.corpus)
    predictions = _load_json(args.predictions)
    engineering = _load_json(args.engineering_receipt)
    if not isinstance(corpus, dict) or set(corpus) != {"train", "sealed"}:
        raise ValueError("generalization corpus requires exactly train and sealed")
    if not isinstance(corpus["train"], list) or not isinstance(corpus["sealed"], list):
        raise ValueError("generalization corpus splits must be lists")
    if not isinstance(predictions, dict) or not isinstance(engineering, dict):
        raise ValueError("predictions and engineering receipt must be objects")
    train = tuple(FactorizedCase.from_mapping(item) for item in corpus["train"])
    sealed = tuple(FactorizedCase.from_mapping(item) for item in corpus["sealed"])
    normalized_predictions = {
        str(key): str(value) for key, value in predictions.items()
    }
    receipt = EngineeringEvidenceReceipt.from_mapping(engineering)
    gate = GeneralizationGate(require_physical=not args.allow_simulation_only)
    report = evaluate_generalization(
        train,
        sealed,
        normalized_predictions,
        receipt,
        projections=registered_shortcut_projections(args.shortcut_order),
        gate=gate,
    )
    certificate = lean_generalization_certificate(
        train,
        sealed,
        normalized_predictions,
        report,
        receipt,
        gate=gate,
    )
    if args.certificate_output is not None:
        args.certificate_output.write_text(
            json.dumps(certificate, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    default_checker = (
        Path(__file__).resolve().parents[2] / ".lake/build/bin/generalizationCheck"
    )
    checker = args.lean_checker or (default_checker if default_checker.is_file() else None)
    lean_checker_pass: bool | None = None
    lean_checker_stdout = ""
    if checker is not None:
        with tempfile.TemporaryDirectory(prefix="mbench-generalization-") as directory:
            certificate_path = Path(directory) / "certificate.json"
            certificate_path.write_text(
                json.dumps(certificate, sort_keys=True) + "\n", encoding="utf-8"
            )
            checked = subprocess.run(
                [str(checker), str(certificate_path)],
                text=True,
                capture_output=True,
                check=False,
            )
        lean_checker_pass = checked.returncode == 0
        lean_checker_stdout = (checked.stdout + checked.stderr).strip()
    payload = report.to_dict()
    payload["lean_certificate"] = certificate
    payload["lean_checker_pass"] = lean_checker_pass
    payload["lean_checker_output"] = lean_checker_stdout
    if report.eligible and lean_checker_pass is False:
        payload["eligible"] = False
        payload["violations"] = [
            *payload["violations"],
            "python_lean_certificate_disagreement",
        ]
    return payload


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "task" and args.task_command == "validate":
            task = TaskPackage.load(args.task_directory)
            _print_json(
                {
                    "valid": True,
                    "task_id": task.manifest.task_id,
                    "track": task.manifest.track.value,
                    "evidence_ceiling": task.manifest.evidence_ceiling.value,
                    "package_digest": task.package_digest,
                }
            )
            return 0
        if args.command == "run":
            verification, score = run_task(
                args.task_directory,
                system_command=args.system_command,
                guidance=args.guidance,
                output_directory=args.output,
            )
            _print_json(
                {"verification": verification.to_dict(), "score": score.to_dict()}
            )
            return 0 if verification.valid else 2
        if args.command == "generalization":
            report = _audit_generalization(args)
            _print_json(report)
            return 0 if report["eligible"] else 2
        verification, score = evaluate_completed_run(args.run_directory)
        if args.command == "verify":
            _print_json(verification.to_dict())
            return 0 if verification.valid else 2
        _print_json(score.to_dict())
        return 0 if score.eligible else 2
    except (MechanogenesisBenchError, ValueError, OSError, json.JSONDecodeError) as error:
        print(f"mbench: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
