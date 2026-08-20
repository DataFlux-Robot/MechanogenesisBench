from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .errors import MechanogenesisBenchError
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
    return parser


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
        verification, score = evaluate_completed_run(args.run_directory)
        if args.command == "verify":
            _print_json(verification.to_dict())
            return 0 if verification.valid else 2
        _print_json(score.to_dict())
        return 0 if score.eligible else 2
    except MechanogenesisBenchError as error:
        print(f"mbench: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
