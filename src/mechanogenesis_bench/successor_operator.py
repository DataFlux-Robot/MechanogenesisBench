from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from mechanogenesis_engine.fixture_search import FixtureGoal
from mechanogenesis_engine.gtheta import GThetaRun, GThetaRuntime, ResearchRequest, StaticStrategyProposer
from mechanogenesis_engine.interpreter import base_process_capability_id, initial_state
from mechanogenesis_engine.ir import WorldSpec
from mechanogenesis_engine.research_strategy import FixtureResearchStrategy

from .canonical import digest
from .errors import SchemaError


@dataclass(frozen=True)
class SuccessorOperatorGeneration:
    """One executable physical-operator edge in a successor chain.

    The input and output identities bind the complete capability records, not
    merely human-readable capability names.  ``used_input_operator`` is derived
    from the canonical interpreter receipts.
    """

    index: int
    input_operator_id: str
    input_operator_hash: str
    output_operator_id: str
    output_operator_hash: str
    parent_world_hash: str
    child_world_hash: str
    program_hash: str
    input_position_error_um: int
    output_position_error_um: int
    product_absolute_frame_error_um: int
    used_input_operator: bool
    run: GThetaRun

    def to_receipt(self) -> dict[str, object]:
        return {
            "schema_version": "successor-operator-generation/v1",
            "index": self.index,
            "input_operator_id": self.input_operator_id,
            "input_operator_hash": self.input_operator_hash,
            "output_operator_id": self.output_operator_id,
            "output_operator_hash": self.output_operator_hash,
            "parent_world_hash": self.parent_world_hash,
            "child_world_hash": self.child_world_hash,
            "program_hash": self.program_hash,
            "input_position_error_um": self.input_position_error_um,
            "output_position_error_um": self.output_position_error_um,
            "product_absolute_frame_error_um": (
                self.product_absolute_frame_error_um
            ),
            "used_input_operator": self.used_input_operator,
        }


@dataclass(frozen=True)
class SuccessorOperatorChain:
    generations: tuple[SuccessorOperatorGeneration, ...]

    @property
    def final_product_absolute_frame_error_um(self) -> int:
        return self.generations[-1].product_absolute_frame_error_um

    @property
    def strict_operator_improvements(self) -> int:
        return sum(
            item.output_position_error_um < item.input_position_error_um
            for item in self.generations
        )


def _machine_process(
    state: Mapping[str, object], capability_id: str
) -> Mapping[str, object]:
    capabilities = state.get("capabilities")
    if not isinstance(capabilities, Mapping):
        raise SchemaError("world state has no capability mapping")
    capability = capabilities.get(capability_id)
    if not isinstance(capability, Mapping):
        raise SchemaError(f"unknown physical operator {capability_id}")
    if capability.get("kind") != "machine_process":
        raise SchemaError(f"{capability_id} is not a machine-process operator")
    error = capability.get("position_error_um")
    if isinstance(error, bool) or not isinstance(error, int) or error <= 0:
        raise SchemaError(f"{capability_id} has an invalid position-error bound")
    return capability


def execute_successor_operator_chain(
    world: WorldSpec,
    goals: Sequence[FixtureGoal],
    strategies: Sequence[FixtureResearchStrategy],
    *,
    missions: Sequence[str] | None = None,
    evaluator_contract: Mapping[str, object] | None = None,
    max_executions: int = 500,
) -> SuccessorOperatorChain:
    """Execute a finite physical successor chain through canonical semantics.

    Generation ``k + 1`` receives the exact final world state from generation
    ``k`` and must machine its product with generation ``k``'s output operator.
    Replacing that operator by an equal-looking or procured capability changes
    the input identity and therefore fails lineage validation.
    """

    if len(goals) < 2 or len(goals) != len(strategies):
        raise SchemaError("successor-operator chain requires matched goals and strategies")
    if missions is not None and len(missions) != len(goals):
        raise SchemaError("missions must match the number of generations")
    contract = dict(evaluator_contract or {})
    state: Mapping[str, object] = initial_state(world)
    milling_machine = next(
        (machine for machine in world.machines if "milling" in machine.operations),
        None,
    )
    if milling_machine is None:
        raise SchemaError("world has no milling-capable machine")
    input_operator_id = base_process_capability_id(milling_machine.machine_id)
    generations: list[SuccessorOperatorGeneration] = []

    for index, (goal, strategy) in enumerate(zip(goals, strategies, strict=True)):
        input_operator = _machine_process(state, input_operator_id)
        request = ResearchRequest(
            mission=(
                missions[index]
                if missions is not None
                else f"Generate physical successor operator {index}."
            ),
            world=world,
            goal=goal,
            max_executions=max_executions,
            prior_evidence=tuple(item.to_receipt() for item in generations),
        )
        run = GThetaRuntime(StaticStrategyProposer(strategy)).run_fixture(
            request,
            evaluator_contract=contract,
            parent_state=state,
            namespace=f"g{index}",
            process_capability_id=input_operator_id,
            qualify_process=True,
        )
        result = run.search_result
        output_operator_id = result.qualified_process_capability_id
        if output_operator_id is None:
            raise SchemaError("generation did not produce a successor operator")
        output_operator = _machine_process(result.execution.final_state, output_operator_id)
        if output_operator.get("parent_process_capability_id") != input_operator_id:
            raise SchemaError("successor operator does not name the exact input operator")

        machining_receipts = [
            receipt
            for receipt in result.execution.receipts
            if receipt.operation == "machine_part"
        ]
        used_input = bool(machining_receipts) and all(
            receipt.facts.get("process_capability_id") == input_operator_id
            for receipt in machining_receipts
        )
        fixture = result.execution.final_state["capabilities"][
            result.fixture_capability_id
        ]
        if not isinstance(fixture, Mapping):
            raise SchemaError("generated product capability is malformed")
        absolute_error = fixture.get("absolute_frame_error_um")
        if (
            isinstance(absolute_error, bool)
            or not isinstance(absolute_error, int)
            or absolute_error <= 0
        ):
            raise SchemaError("generated product lacks an absolute-frame error bound")

        generation = SuccessorOperatorGeneration(
            index=index,
            input_operator_id=input_operator_id,
            input_operator_hash=digest(dict(input_operator)),
            output_operator_id=output_operator_id,
            output_operator_hash=digest(dict(output_operator)),
            parent_world_hash=result.execution.parent_world_hash,
            child_world_hash=result.execution.child_world_hash,
            program_hash=result.execution.process_hash,
            input_position_error_um=int(input_operator["position_error_um"]),
            output_position_error_um=int(output_operator["position_error_um"]),
            product_absolute_frame_error_um=absolute_error,
            used_input_operator=used_input,
            run=run,
        )
        if not used_input:
            raise SchemaError("construction did not use the declared input operator")
        if generation.output_position_error_um >= generation.input_position_error_um:
            raise SchemaError("successor operator does not strictly improve its parent")
        if generations:
            previous = generations[-1]
            if generation.parent_world_hash != previous.child_world_hash:
                raise SchemaError("physical world lineage is discontinuous")
            if generation.input_operator_id != previous.output_operator_id:
                raise SchemaError("output operator is not the next generation input")
            if generation.input_operator_hash != previous.output_operator_hash:
                raise SchemaError("physical operator bytes changed across generations")
        generations.append(generation)
        state = result.execution.final_state
        input_operator_id = output_operator_id

    return SuccessorOperatorChain(tuple(generations))
