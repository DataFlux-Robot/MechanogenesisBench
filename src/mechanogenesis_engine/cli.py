from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .compiler import load_program, load_world, write_program
from .errors import MechanogenesisEngineError
from .fixture_search import FixtureGoal, search_fixture
from .interpreter import ReferenceInterpreter, initial_world_hash


def _load_goal(path: Path) -> FixtureGoal:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise MechanogenesisEngineError(f"cannot load fixture goal: {error}") from error
    if not isinstance(raw, dict):
        raise MechanogenesisEngineError("fixture goal must be an object")
    return FixtureGoal.from_mapping(raw)


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mengine")
    commands = parser.add_subparsers(dest="command", required=True)
    world_hash = commands.add_parser("world-hash")
    world_hash.add_argument("world", type=Path)
    execute = commands.add_parser("execute")
    execute.add_argument("world", type=Path)
    execute.add_argument("program", type=Path)
    execute.add_argument("--output", type=Path)
    search = commands.add_parser("search-fixture")
    search.add_argument("world", type=Path)
    search.add_argument("goal", type=Path)
    search.add_argument("--program-output", type=Path, required=True)
    search.add_argument("--execution-output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        world = load_world(args.world)
        if args.command == "world-hash":
            print(initial_world_hash(world))
            return 0
        if args.command == "execute":
            result = ReferenceInterpreter().execute(world, load_program(args.program))
            payload = result.to_dict()
            if args.output:
                _write(args.output, payload)
            else:
                print(json.dumps(payload, indent=2, sort_keys=True))
            return 0
        result = search_fixture(world, _load_goal(args.goal))
        write_program(args.program_output, result.program)
        payload = {
            "attempted_candidates": result.attempted_candidates,
            "executable_candidates": result.executable_candidates,
            "feasible_candidates": result.feasible_candidates,
            "selected_parameters": result.selected_parameters,
            "execution": result.execution.to_dict(),
        }
        if args.execution_output:
            _write(args.execution_output, payload)
        else:
            print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    except MechanogenesisEngineError as error:
        print(f"mengine: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
