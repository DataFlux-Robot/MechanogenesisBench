from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from .compiler import load_program, load_state, load_world, write_program, write_state
from .errors import MechanogenesisEngineError
from .fixture_search import FixtureGoal, search_fixture
from .gtheta import (
    GThetaRuntime,
    OpenAICompatibleProposer,
    ReferenceResearchProposer,
    ResearchRequest,
)
from .interpreter import ReferenceInterpreter, initial_world_hash
from .research_strategy import FixtureResearchStrategy


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


def _load_mapping(path: Path, field: str) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise MechanogenesisEngineError(f"cannot load {field}: {error}") from error
    if not isinstance(value, dict):
        raise MechanogenesisEngineError(f"{field} must be an object")
    return value


def _load_text(path: Path, field: str) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as error:
        raise MechanogenesisEngineError(f"cannot load {field}: {error}") from error


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mengine")
    commands = parser.add_subparsers(dest="command", required=True)
    world_hash = commands.add_parser("world-hash")
    world_hash.add_argument("world", type=Path)
    execute = commands.add_parser("execute")
    execute.add_argument("world", type=Path)
    execute.add_argument("program", type=Path)
    execute.add_argument("--output", type=Path)
    execute.add_argument("--parent-state", type=Path)
    execute.add_argument("--state-output", type=Path)
    search = commands.add_parser("search-fixture")
    search.add_argument("world", type=Path)
    search.add_argument("goal", type=Path)
    search.add_argument("--program-output", type=Path, required=True)
    search.add_argument("--execution-output", type=Path)
    search.add_argument("--parent-state", type=Path)
    search.add_argument("--state-output", type=Path)
    search.add_argument("--namespace", default="")
    search.add_argument("--process-capability-id")
    search.add_argument("--no-qualify", action="store_true")
    search.add_argument("--strategy", type=Path)
    research = commands.add_parser(
        "research-fixture", help="generate an MRS strategy and compile it to a fixture"
    )
    research.add_argument("world", type=Path)
    research.add_argument("goal", type=Path)
    research.add_argument("--mission", type=Path, required=True)
    research.add_argument("--evaluator-contract", type=Path, required=True)
    research.add_argument("--strategy-output", type=Path, required=True)
    research.add_argument("--mrs-output", type=Path, required=True)
    research.add_argument("--program-output", type=Path, required=True)
    research.add_argument("--execution-output", type=Path)
    research.add_argument("--max-executions", type=int, default=500)
    research.add_argument(
        "--proposer", choices=("reference", "openai-compatible"), default="reference"
    )
    research.add_argument("--llm-endpoint")
    research.add_argument("--llm-model")
    research.add_argument("--api-key-env", default="OPENAI_API_KEY")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        world = load_world(args.world)
        if args.command == "world-hash":
            print(initial_world_hash(world))
            return 0
        if args.command == "execute":
            interpreter = ReferenceInterpreter()
            program = load_program(args.program)
            result = (
                interpreter.execute_from_state(
                    world, load_state(args.parent_state), program
                )
                if args.parent_state
                else interpreter.execute(world, program)
            )
            payload = result.to_dict()
            if args.state_output:
                write_state(args.state_output, result.final_state)
            if args.output:
                _write(args.output, payload)
            else:
                print(json.dumps(payload, indent=2, sort_keys=True))
            return 0
        if args.command == "research-fixture":
            if args.proposer == "reference":
                proposer = ReferenceResearchProposer()
            else:
                api_key = os.environ.get(args.api_key_env, "")
                if not args.llm_endpoint or not args.llm_model or not api_key:
                    raise MechanogenesisEngineError(
                        "openai-compatible proposer requires --llm-endpoint, "
                        "--llm-model and the configured API-key environment variable"
                    )
                proposer = OpenAICompatibleProposer(
                    endpoint=args.llm_endpoint,
                    model=args.llm_model,
                    api_key=api_key,
                )
            research = GThetaRuntime(proposer).run_fixture(
                ResearchRequest(
                    mission=_load_text(args.mission, "research mission"),
                    world=world,
                    goal=_load_goal(args.goal),
                    max_executions=args.max_executions,
                ),
                evaluator_contract=_load_mapping(
                    args.evaluator_contract, "evaluator contract"
                ),
            )
            write_program(args.program_output, research.search_result.program)
            _write(args.strategy_output, research.strategy.to_dict())
            _write(args.mrs_output, research.mrs_objects)
            if args.execution_output:
                _write(
                    args.execution_output,
                    research.search_result.execution.to_dict(),
                )
            return 0
        strategy = (
            FixtureResearchStrategy.from_mapping(
                _load_mapping(args.strategy, "research strategy")
            )
            if args.strategy
            else None
        )
        result = search_fixture(
            world,
            _load_goal(args.goal),
            parent_state=(load_state(args.parent_state) if args.parent_state else None),
            namespace=args.namespace,
            process_capability_id=args.process_capability_id,
            qualify_process=not args.no_qualify,
            strategy=strategy,
        )
        write_program(args.program_output, result.program)
        payload = {
            "attempted_candidates": result.attempted_candidates,
            "executable_candidates": result.executable_candidates,
            "feasible_candidates": result.feasible_candidates,
            "selected_parameters": result.selected_parameters,
            "strategy_hash": result.strategy_hash,
            "candidate_support_size": result.candidate_support_size,
            "robust_worst_case_error_um": result.robust_worst_case_error_um,
            "weighted_model_error_ppm_um": result.weighted_model_error_ppm_um,
            "hypothesis_errors_um": result.hypothesis_errors_um,
            "execution": result.execution.to_dict(),
        }
        if args.execution_output:
            _write(args.execution_output, payload)
        else:
            print(json.dumps(payload, indent=2, sort_keys=True))
        if args.state_output:
            write_state(args.state_output, result.execution.final_state)
        return 0
    except MechanogenesisEngineError as error:
        print(f"mengine: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
