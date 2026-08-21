from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from mechanogenesis_bench.canonical import digest
from mechanogenesis_engine.compiler import load_world
from mechanogenesis_engine.errors import ExecutionError, IRValidationError
from mechanogenesis_engine.fixture_search import FixtureGoal
from mechanogenesis_engine.gtheta import (
    GThetaRuntime,
    OpenAICompatibleProposer,
    ReferenceResearchProposer,
    ResearchRequest,
    StaticStrategyProposer,
)
from mechanogenesis_engine.research_strategy import FixtureResearchStrategy


ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "tasks/conformance/generated_metrology_fixture"


def request(*, max_executions: int = 32) -> ResearchRequest:
    world = load_world(TASK / "public/mechanism_world.json")
    goal = FixtureGoal.from_mapping(
        json.loads((TASK / "public/fixture_goal.json").read_text(encoding="utf-8"))
    )
    return ResearchRequest(
        mission=(TASK / "guidance/G5.md").read_text(encoding="utf-8"),
        world=world,
        goal=goal,
        max_executions=max_executions,
    )


def evaluator_contract() -> dict[str, object]:
    return json.loads(
        (TASK / "public/evaluator_contract.json").read_text(encoding="utf-8")
    )


def test_reference_gtheta_generates_executable_mrs() -> None:
    research = GThetaRuntime(ReferenceResearchProposer()).run_fixture(
        request(), evaluator_contract=evaluator_contract()
    )
    result = research.search_result
    assert result.strategy_hash == research.strategy.strategy_hash
    assert result.attempted_candidates == 1
    assert result.candidate_support_size == 240
    assert result.robust_worst_case_error_um == 160
    assert result.weighted_model_error_ppm_um == 144_850_000
    assert result.hypothesis_errors_um == {
        "public_nominal": 130,
        "span_shift": 145,
        "span_and_disturbance_shift": 160,
    }
    language = research.mrs_objects["language"]
    assert isinstance(language, dict)
    assert digest(language["research_strategy"]) == research.strategy.strategy_hash
    assert digest(research.mrs_objects["construction_program"]) == (
        result.execution.process_hash
    )


def test_strategy_support_ablation_removes_feasible_candidate() -> None:
    research_request = request(max_executions=1)
    raw = deepcopy(ReferenceResearchProposer().propose(research_request).to_dict())
    domains = {
        item["semantic"]: item for item in raw["language"]["parameters"]
    }
    domains["pin_spacing_um"]["candidates_um"] = [40_000]
    domains["bore_clearance_um"]["candidates_um"] = [80]
    domains["reference_y_um"]["candidates_um"] = [25_000]
    raw["search"]["max_executions"] = 1
    ablated = FixtureResearchStrategy.from_mapping(raw)
    with pytest.raises(ExecutionError, match="multi-world evidence gates"):
        GThetaRuntime(StaticStrategyProposer(ablated)).run_fixture(
            research_request, evaluator_contract=evaluator_contract()
        )


def test_grounded_world_expansion_separates_a_marginal_candidate() -> None:
    research_request = request(max_executions=1)
    expanded_raw = deepcopy(
        ReferenceResearchProposer().propose(research_request).to_dict()
    )
    domains = {
        item["semantic"]: item
        for item in expanded_raw["language"]["parameters"]
    }
    domains["pin_spacing_um"]["candidates_um"] = [80_000]
    domains["bore_clearance_um"]["candidates_um"] = [40]
    domains["reference_y_um"]["candidates_um"] = [15_000]
    expanded_raw["search"]["max_executions"] = 1

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
    nominal_run = GThetaRuntime(StaticStrategyProposer(nominal)).run_fixture(
        research_request, evaluator_contract=evaluator_contract()
    )
    assert nominal_run.search_result.robust_worst_case_error_um == 200
    assert nominal_run.search_result.weighted_model_error_ppm_um == 200_000_000

    expanded = FixtureResearchStrategy.from_mapping(expanded_raw)
    with pytest.raises(ExecutionError, match="multi-world evidence gates"):
        GThetaRuntime(StaticStrategyProposer(expanded)).run_fixture(
            research_request, evaluator_contract=evaluator_contract()
        )


def test_strategy_cannot_invent_an_unavailable_intervention() -> None:
    research_request = request()
    raw = deepcopy(ReferenceResearchProposer().propose(research_request).to_dict())
    raw["language"]["parameters"][0]["candidates_um"] = [999_999]
    strategy = FixtureResearchStrategy.from_mapping(raw)
    with pytest.raises(IRValidationError, match="outside public intervention access"):
        StaticStrategyProposer(strategy).propose(research_request)


def test_llm_boundary_rejects_markdown_and_unknown_fields() -> None:
    raw = ReferenceResearchProposer().propose(request()).to_dict()
    with pytest.raises(IRValidationError, match="bare JSON object"):
        OpenAICompatibleProposer.parse_content(
            "```json\n" + json.dumps(raw) + "\n```"
        )
    raw["untrusted_code"] = "import os"
    with pytest.raises(IRValidationError, match="fields mismatch"):
        OpenAICompatibleProposer.parse_content(json.dumps(raw))


def test_strategy_cannot_exceed_request_budget() -> None:
    large_request = request(max_executions=32)
    raw = deepcopy(ReferenceResearchProposer().propose(large_request).to_dict())
    raw["search"]["max_executions"] = 33
    strategy = FixtureResearchStrategy.from_mapping(raw)
    with pytest.raises(IRValidationError, match="exceeds the research execution budget"):
        StaticStrategyProposer(strategy).propose(large_request)
