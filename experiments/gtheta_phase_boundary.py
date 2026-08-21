#!/usr/bin/env python3
"""Executable support and world-separation ablation for Gθ/MRS 0.1."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from mechanogenesis_engine.compiler import load_world
from mechanogenesis_engine.errors import ExecutionError
from mechanogenesis_engine.fixture_search import FixtureGoal, search_fixture
from mechanogenesis_engine.gtheta import ReferenceResearchProposer, ResearchRequest
from mechanogenesis_engine.research_strategy import FixtureResearchStrategy


ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "tasks/conformance/generated_metrology_fixture"


def run_strategy(
    world, goal: FixtureGoal, strategy: FixtureResearchStrategy
) -> dict[str, object]:
    try:
        result = search_fixture(world, goal, strategy=strategy)
    except ExecutionError as error:
        return {"feasible_output": False, "failure": str(error)}
    return {
        "feasible_output": True,
        "strategy_hash": strategy.strategy_hash,
        "attempted_candidates": result.attempted_candidates,
        "candidate_support_size": result.candidate_support_size,
        "robust_worst_case_error_um": result.robust_worst_case_error_um,
        "weighted_model_error_ppm_um": result.weighted_model_error_ppm_um,
        "hypothesis_errors_um": result.hypothesis_errors_um,
        "selected_parameters": result.selected_parameters,
    }


def main() -> int:
    world = load_world(TASK / "public/mechanism_world.json")
    goal = FixtureGoal.from_mapping(
        json.loads((TASK / "public/fixture_goal.json").read_text(encoding="utf-8"))
    )
    request = ResearchRequest(
        mission=(TASK / "guidance/G5.md").read_text(encoding="utf-8"),
        world=world,
        goal=goal,
        max_executions=32,
    )
    reference = ReferenceResearchProposer().propose(request)

    unsupported_raw = deepcopy(reference.to_dict())
    unsupported_domains = {
        item["semantic"]: item
        for item in unsupported_raw["language"]["parameters"]
    }
    unsupported_domains["pin_spacing_um"]["candidates_um"] = [40_000]
    unsupported_domains["bore_clearance_um"]["candidates_um"] = [80]
    unsupported_domains["reference_y_um"]["candidates_um"] = [25_000]
    unsupported_raw["search"]["max_executions"] = 1
    unsupported = FixtureResearchStrategy.from_mapping(unsupported_raw)

    expanded_raw = deepcopy(reference.to_dict())
    marginal_domains = {
        item["semantic"]: item
        for item in expanded_raw["language"]["parameters"]
    }
    marginal_domains["pin_spacing_um"]["candidates_um"] = [80_000]
    marginal_domains["bore_clearance_um"]["candidates_um"] = [40]
    marginal_domains["reference_y_um"]["candidates_um"] = [15_000]
    expanded_raw["search"]["max_executions"] = 1
    expanded = FixtureResearchStrategy.from_mapping(expanded_raw)

    nominal_raw = deepcopy(expanded_raw)
    nominal_raw["world_hypotheses"] = [
        {
            "hypothesis_id": "public_nominal",
            "workpiece_span_um": 60_000,
            "extra_disturbance_um": 0,
            "prior_weight_ppm": 1_000_000,
        }
    ]
    nominal_raw["experiment"]["required_hypotheses"] = 1
    nominal = FixtureResearchStrategy.from_mapping(nominal_raw)

    report = {
        "schema_version": "0.1",
        "claim": (
            "budgeted feasible support is necessary for output, and a separating "
            "world hypothesis can remove a nominally feasible candidate"
        ),
        "reference_strategy": run_strategy(world, goal, reference),
        "support_removed": run_strategy(world, goal, unsupported),
        "marginal_nominal_only": run_strategy(world, goal, nominal),
        "marginal_grounded_expansion": run_strategy(world, goal, expanded),
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
