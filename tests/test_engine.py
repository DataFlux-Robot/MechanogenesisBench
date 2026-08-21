from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

from mechanogenesis_bench.models import GuidanceLevel
from mechanogenesis_bench.runner import run_task
from mechanogenesis_engine.compiler import load_world
from mechanogenesis_engine.errors import ExecutionError, IRValidationError
from mechanogenesis_engine.fixture_search import FixtureGoal, search_fixture
from mechanogenesis_engine.interpreter import ReferenceInterpreter, initial_world_hash
from mechanogenesis_engine.ir import MechanismProgram, program_to_dict


ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "tasks/conformance/generated_metrology_fixture"
WORLD_PATH = TASK / "public/mechanism_world.json"
GOAL_PATH = TASK / "public/fixture_goal.json"
SYSTEM = ROOT / "examples/generated_fixture_search_system.py"
RECURSIVE_TASK = ROOT / "tasks/conformance/recursive_fixture_process"
RECURSIVE_SYSTEM = ROOT / "examples/recursive_fixture_process_system.py"


def generated_fixture():
    world = load_world(WORLD_PATH)
    goal = FixtureGoal.from_mapping(json.loads(GOAL_PATH.read_text(encoding="utf-8")))
    return world, search_fixture(world, goal)


def test_fixture_search_generates_and_executes_a_program() -> None:
    world, result = generated_fixture()
    assert initial_world_hash(world) == (
        "sha256:6d1db13f5a19318b6e13d081ee77acbcb61339c5f6e915c13d06d3ceea7eadf7"
    )
    assert result.attempted_candidates == 240
    assert result.executable_candidates == 240
    assert result.feasible_candidates == 72
    assert result.selected_parameters == {
        "base_x_um": 120_000,
        "base_y_um": 80_000,
        "base_z_um": 10_000,
        "pin_spacing_um": 80_000,
        "bore_clearance_um": 20,
        "reference_y_um": 15_000,
        "worst_case_error_um": 130,
    }
    capability = result.execution.final_state["capabilities"]
    assert capability["generated_fixture_metrology"]["worst_case_error_um"] == 130
    assert capability["generated_fixture_machine_process"]["position_error_um"] == 140


def test_receipts_are_world_chained_and_material_closed() -> None:
    _, result = generated_fixture()
    previous = result.execution.parent_world_hash
    for receipt in result.execution.receipts:
        assert receipt.parent_world_hash == previous
        assert receipt.operation_hash.startswith("sha256:")
        for balance in receipt.balances:
            assert balance.input_q + balance.reserve_draw_q == (
                balance.output_q + balance.waste_q
            )
        previous = receipt.child_world_hash
    assert previous == result.execution.child_world_hash


def test_escaping_csg_cutter_is_rejected() -> None:
    world, result = generated_fixture()
    raw = deepcopy(program_to_dict(result.program))
    raw["parts"][0]["geometry"]["children"][1]["center_um"][0] = 1_000_000
    with pytest.raises(IRValidationError, match="escapes its base"):
        ReferenceInterpreter().execute(world, MechanismProgram.from_mapping(raw))


def test_rigid_mate_drift_is_rejected() -> None:
    world, result = generated_fixture()
    raw = deepcopy(program_to_dict(result.program))
    raw["assemblies"][0]["occurrences"][1]["pose"]["translation_um"][0] += 1
    with pytest.raises(IRValidationError, match="position tolerance"):
        ReferenceInterpreter().execute(world, MechanismProgram.from_mapping(raw))


def test_unavailable_manufacturing_process_is_rejected() -> None:
    world, result = generated_fixture()
    raw = deepcopy(program_to_dict(result.program))
    raw["operations"][0]["process"] = "laser_powder_bed_fusion"
    with pytest.raises(ExecutionError, match="does not support"):
        ReferenceInterpreter().execute(world, MechanismProgram.from_mapping(raw))


def test_machine_part_cannot_cite_an_unearned_capability() -> None:
    world, result = generated_fixture()
    raw = deepcopy(program_to_dict(result.program))
    raw["operations"][0]["process_capability_id"] = "invented_precision_process"
    with pytest.raises(ExecutionError, match="matching machine-process"):
        ReferenceInterpreter().execute(world, MechanismProgram.from_mapping(raw))


def test_blind_bore_that_misses_insertion_path_is_rejected() -> None:
    world, result = generated_fixture()
    raw = deepcopy(program_to_dict(result.program))
    bore = raw["parts"][0]["geometry"]["children"][1]
    bore["center_um"][2] = 9_000
    bore["height_um"] = 2_000
    with pytest.raises(ExecutionError, match="does not span the insertion path"):
        ReferenceInterpreter().execute(world, MechanismProgram.from_mapping(raw))


def test_non_improving_process_qualification_is_rejected() -> None:
    world, result = generated_fixture()
    raw = deepcopy(program_to_dict(result.program))
    raw["operations"][-1]["transfer_error_um"] = 1_000
    with pytest.raises(ExecutionError, match="does not strictly improve"):
        ReferenceInterpreter().execute(world, MechanismProgram.from_mapping(raw))


def test_fixture_physically_contributes_to_successor_process() -> None:
    world = load_world(RECURSIVE_TASK / "public/mechanism_world.json")
    goal = FixtureGoal.from_mapping(
        json.loads(
            (RECURSIVE_TASK / "public/fixture_goal.json").read_text(
                encoding="utf-8"
            )
        )
    )
    first = search_fixture(world, goal)
    assert first.qualified_process_capability_id is not None
    second = search_fixture(
        world,
        goal,
        parent_state=first.execution.final_state,
        namespace="successor",
        process_capability_id=first.qualified_process_capability_id,
        qualify_process=False,
    )
    assert first.execution.child_world_hash == second.execution.parent_world_hash
    assert second.execution.final_state["sequence"] == 13
    capabilities = second.execution.final_state["capabilities"]
    assert capabilities["three_axis_mill_v0.base_process"]["position_error_um"] == 800
    assert capabilities["generated_fixture_machine_process"]["position_error_um"] == 140
    assert capabilities["generated_fixture_metrology"]["absolute_frame_error_um"] == 930
    assert capabilities["successor_generated_fixture_metrology"][
        "absolute_frame_error_um"
    ] == 270


def test_state_from_another_world_is_rejected() -> None:
    world, result = generated_fixture()
    state = deepcopy(result.execution.final_state)
    state["world_spec_hash"] = "sha256:" + "0" * 64
    raw = deepcopy(program_to_dict(result.program))
    raw["parent_world_hash"] = "sha256:" + "1" * 64
    with pytest.raises(ExecutionError, match="different world specification"):
        ReferenceInterpreter().execute_from_state(
            world, state, MechanismProgram.from_mapping(raw)
        )


def test_generated_fixture_benchmark_episode_is_eligible(tmp_path: Path) -> None:
    verification, score = run_task(
        TASK,
        system_command=[sys.executable, str(SYSTEM)],
        guidance=GuidanceLevel.G5,
        output_directory=tmp_path / "run",
    )
    assert verification.valid
    assert verification.promotions == 1
    assert score.eligible
    assert score.capability_gain == pytest.approx(640.0)
    assert score.robustness_pass_rate == pytest.approx(1.0)
    assert score.certified_evidence_tier == "conformance"


def test_recursive_fixture_process_episode_has_two_promotions(tmp_path: Path) -> None:
    verification, score = run_task(
        RECURSIVE_TASK,
        system_command=[sys.executable, str(RECURSIVE_SYSTEM)],
        guidance=GuidanceLevel.G5,
        output_directory=tmp_path / "recursive-run",
    )
    assert verification.valid
    assert verification.promotions == 2
    assert score.eligible
    assert score.capability_gain == pytest.approx(630.0)
    assert score.robustness_pass_rate == pytest.approx(1.0)
