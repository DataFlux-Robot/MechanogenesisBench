from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Mapping, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from mechanogenesis_bench.canonical import digest

from .errors import ExecutionError, IRValidationError
from .fixture_search import FixtureGoal, SearchResult, search_fixture
from .ir import WorldSpec, program_to_dict, world_to_dict
from .research_strategy import FixtureResearchStrategy


@dataclass(frozen=True)
class ResearchRequest:
    mission: str
    world: WorldSpec
    goal: FixtureGoal
    max_executions: int
    prior_evidence: tuple[Mapping[str, object], ...] = ()

    def __post_init__(self) -> None:
        if not self.mission.strip():
            raise IRValidationError("research mission must be non-empty")
        if len(self.mission) > 20_000:
            raise IRValidationError("research mission exceeds 20,000 characters")
        if (
            isinstance(self.max_executions, bool)
            or not isinstance(self.max_executions, int)
            or self.max_executions <= 0
        ):
            raise IRValidationError("research max_executions must be positive")
        if self.max_executions > 100_000:
            raise IRValidationError("research max_executions exceeds trusted limit")
        if len(self.prior_evidence) > 256:
            raise IRValidationError("prior evidence exceeds 256 records")

    def public_payload(self) -> dict[str, object]:
        return {
            "mission": self.mission,
            "world": world_to_dict(self.world),
            "goal": self.goal.to_dict(),
            "budget": {"max_executions": self.max_executions},
            "prior_evidence": [dict(item) for item in self.prior_evidence],
        }


class StrategyProposer(Protocol):
    proposer_id: str

    def propose(self, request: ResearchRequest) -> FixtureResearchStrategy:
        """Generate a task-specific research strategy, not a mechanism directly."""


def _validate_proposal(
    strategy: FixtureResearchStrategy, request: ResearchRequest
) -> FixtureResearchStrategy:
    strategy.validate_goal_domains(request.goal)
    if strategy.search.max_executions > request.max_executions:
        raise IRValidationError("strategy exceeds the research execution budget")
    return strategy


class ReferenceResearchProposer:
    """Deterministic Gθ reference policy for reproducible conformance runs.

    This proposer encodes a physics-motivated research prior: maximize locator
    baseline, minimize clearances, minimize material, and reject designs that
    fail a public plus two extrapolated disturbance models.  It is deliberately
    replaceable by a learned/LLM proposer through the same strict schema.
    """

    proposer_id = "reference_physics_prior_v0_1"

    def propose(self, request: ResearchRequest) -> FixtureResearchStrategy:
        goal = request.goal
        span = goal.workpiece_span_um
        raw = {
            "schema_version": "0.1",
            "strategy_id": "reference_fixture_research_v0_1",
            "research_hypothesis": (
                "A long locator baseline and low radial clearances minimize the "
                "translation-plus-angular error bound; the smallest viable base "
                "preserves material without weakening this bounded model."
            ),
            "language": {
                "language_id": "generated_two_locator_fixture_v0_1",
                "semantic_target": "canonical_fixture_ir_v0_3",
                "topology": "two_locator_one_reference",
                "parameters": [
                    {
                        "symbol": "locatorBaseline",
                        "semantic": "pin_spacing_um",
                        "candidates_um": sorted(
                            goal.pin_spacing_candidates_um, reverse=True
                        ),
                    },
                    {
                        "symbol": "radialFit",
                        "semantic": "bore_clearance_um",
                        "candidates_um": sorted(
                            goal.bore_clearance_candidates_um
                        ),
                    },
                    {
                        "symbol": "referenceOffset",
                        "semantic": "reference_y_um",
                        "candidates_um": sorted(
                            goal.reference_y_candidates_um, key=lambda value: abs(value)
                        ),
                    },
                ],
            },
            "world_hypotheses": [
                {
                    "hypothesis_id": "public_nominal",
                    "workpiece_span_um": span,
                    "extra_disturbance_um": 0,
                    "prior_weight_ppm": 340_000,
                },
                {
                    "hypothesis_id": "span_shift",
                    "workpiece_span_um": span + max(span // 6, 1),
                    "extra_disturbance_um": 10,
                    "prior_weight_ppm": 330_000,
                },
                {
                    "hypothesis_id": "span_and_disturbance_shift",
                    "workpiece_span_um": span + max(span // 3, 1),
                    "extra_disturbance_um": 20,
                    "prior_weight_ppm": 330_000,
                },
            ],
            "search": {
                "mode": "ordered_first_feasible",
                "base_order": "smallest_first",
                "objective_order": [
                    "robust_worst_case_error_um",
                    "weighted_model_error_ppm_um",
                    "base_volume_um3",
                    "duration_us",
                ],
                "max_executions": min(request.max_executions, 32),
            },
            "experiment": {
                "intervention_rule": "robust_model_sweep",
                "required_hypotheses": 3,
            },
        }
        return _validate_proposal(FixtureResearchStrategy.from_mapping(raw), request)


class StaticStrategyProposer:
    """Replay a stored strategy while retaining the same validation boundary."""

    proposer_id = "static_strategy_replay_v0_1"

    def __init__(self, strategy: FixtureResearchStrategy):
        self._strategy = strategy

    def propose(self, request: ResearchRequest) -> FixtureResearchStrategy:
        return _validate_proposal(self._strategy, request)


class OpenAICompatibleProposer:
    """LLM-centered Gθ adapter with a JSON-only, fail-closed trust boundary."""

    proposer_id = "openai_compatible_llm_v0_1"

    def __init__(
        self,
        *,
        endpoint: str,
        model: str,
        api_key: str,
        timeout_s: float = 120.0,
    ):
        if not endpoint.startswith(("http://", "https://")):
            raise ValueError("endpoint must be HTTP(S)")
        if not model.strip() or not api_key.strip():
            raise ValueError("model and api_key must be non-empty")
        if timeout_s <= 0:
            raise ValueError("timeout_s must be positive")
        self.endpoint = endpoint.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout_s = timeout_s

    @staticmethod
    def parse_content(content: str) -> FixtureResearchStrategy:
        if len(content) > 1_000_000:
            raise IRValidationError("LLM strategy response exceeds one megabyte")
        stripped = content.strip()
        if not stripped.startswith("{") or not stripped.endswith("}"):
            raise IRValidationError("LLM response must be one bare JSON object")
        try:
            raw = json.loads(stripped)
        except json.JSONDecodeError as error:
            raise IRValidationError(f"LLM response is not valid JSON: {error}") from error
        if not isinstance(raw, dict):
            raise IRValidationError("LLM strategy response must be an object")
        return FixtureResearchStrategy.from_mapping(raw)

    def propose(self, request: ResearchRequest) -> FixtureResearchStrategy:
        schema_example = ReferenceResearchProposer().propose(request).to_dict()
        system_prompt = (
            "You are G-theta, a physical research-strategy generator. Return exactly "
            "one JSON object and no markdown. The object must match the supplied "
            "schema example exactly. You choose a task language parameter support, "
            "ordered search policy, causal world hypotheses, and experiment policy. "
            "Do not output source code or a final mechanism. Every candidate must be "
            "drawn from the public intervention lists and max_executions must fit budget."
        )
        user_payload = {
            "research_request": request.public_payload(),
            "schema_example": schema_example,
        }
        body = json.dumps(
            {
                "model": self.model,
                "temperature": 0,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": json.dumps(
                            user_payload, sort_keys=True, ensure_ascii=False
                        ),
                    },
                ],
            }
        ).encode("utf-8")
        endpoint = self.endpoint
        if not endpoint.endswith("/chat/completions"):
            endpoint += "/chat/completions"
        http_request = Request(
            endpoint,
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(http_request, timeout=self.timeout_s) as response:
                response_body = response.read(2_000_000)
        except (HTTPError, URLError, TimeoutError) as error:
            raise ExecutionError(f"LLM proposer request failed: {error}") from error
        try:
            envelope = json.loads(response_body)
            content = envelope["choices"][0]["message"]["content"]
        except (json.JSONDecodeError, KeyError, IndexError, TypeError) as error:
            raise ExecutionError("LLM proposer returned an invalid response envelope") from error
        if not isinstance(content, str):
            raise ExecutionError("LLM proposer content is not text")
        return _validate_proposal(self.parse_content(content), request)


@dataclass(frozen=True)
class GThetaRun:
    proposer_id: str
    strategy: FixtureResearchStrategy
    search_result: SearchResult
    mrs_objects: dict[str, object]


class GThetaRuntime:
    """Generate an MRS, compile it, and execute its physical program."""

    def __init__(self, proposer: StrategyProposer):
        self.proposer = proposer

    def run_fixture(
        self,
        request: ResearchRequest,
        *,
        evaluator_contract: Mapping[str, object],
        parent_state: Mapping[str, object] | None = None,
        namespace: str = "",
        process_capability_id: str | None = None,
        qualify_process: bool = True,
    ) -> GThetaRun:
        strategy = _validate_proposal(self.proposer.propose(request), request)
        result = search_fixture(
            request.world,
            request.goal,
            parent_state=parent_state,
            namespace=namespace,
            process_capability_id=process_capability_id,
            qualify_process=qualify_process,
            strategy=strategy,
        )
        program = program_to_dict(result.program)
        strategy_object = strategy.to_dict()
        mrs_objects: dict[str, object] = {
            "language": {
                "kind": "gtheta_generated_research_language",
                "strategy_hash": strategy.strategy_hash,
                "research_strategy": strategy_object,
            },
            "semantics": {
                "kind": "trusted_fixture_strategy_transition_system",
                "semantic_target": strategy.language.semantic_target,
                "parent_world_hash": result.execution.parent_world_hash,
                "invariants": [
                    "public_intervention_domain",
                    "canonical_ir_validation",
                    "material_closure",
                    "world_lineage",
                    "multi_world_error_gate",
                ],
            },
            "compiler": {
                "kind": "bounded_fixture_strategy_compiler",
                "trusted_fragment": strategy.language.topology,
                "input_strategy_hash": strategy.strategy_hash,
                "target": "canonical_mechanism_ir_v0.3",
                "proposer_id": self.proposer.proposer_id,
            },
            "compiler_certificate": {
                "kind": "executed_strategy_compiler_certificate",
                "strategy_hash": strategy.strategy_hash,
                "candidate_support_size": result.candidate_support_size,
                "attempted_candidates": result.attempted_candidates,
                "process_hash": result.execution.process_hash,
                "child_world_hash": result.execution.child_world_hash,
                "receipt_count": len(result.execution.receipts),
            },
            "theory_portfolio": {
                "kind": "generated_multi_world_theory_portfolio",
                "research_hypothesis": strategy.research_hypothesis,
                "world_hypotheses": [
                    item.to_dict() for item in strategy.world_hypotheses
                ],
                "observed_hypothesis_errors_um": result.hypothesis_errors_um,
            },
            "construction_program": program,
            "experiment_program": {
                "kind": "compiled_multi_world_intervention_sweep",
                "policy": strategy.experiment.to_dict(),
                "acceptance_threshold_um": request.goal.max_worst_case_error_um,
                "selected_parameters": result.selected_parameters,
            },
            "evaluator_contract": dict(evaluator_contract),
            "update_proposal": {
                "kind": "gtheta_strategy_update_proposal",
                "strategy_hash": strategy.strategy_hash,
                "proposal": (
                    "retain the certified support ordering; on failure expand the "
                    "parameter support or add a separating world hypothesis"
                ),
                "candidate_support_size": result.candidate_support_size,
                "attempted_candidates": result.attempted_candidates,
                "feasible_candidates": result.feasible_candidates,
                "robust_worst_case_error_um": result.robust_worst_case_error_um,
                "weighted_model_error_ppm_um": result.weighted_model_error_ppm_um,
            },
        }
        if digest(strategy_object) != strategy.strategy_hash:
            raise ExecutionError("strategy serialization is not content stable")
        return GThetaRun(
            proposer_id=self.proposer.proposer_id,
            strategy=strategy,
            search_result=result,
            mrs_objects=mrs_objects,
        )
