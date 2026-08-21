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


def generated_fixture():
    world = load_world(WORLD_PATH)
    goal = FixtureGoal.from_mapping(json.loads(GOAL_PATH.read_text(encoding="utf-8")))
    return world, search_fixture(world, goal)


def test_fixture_search_generates_and_executes_a_program() -> None:
    world, result = generated_fixture()
    assert initial_world_hash(world) == (
        "sha256:6cc284661c5f5e96d7fbc7be1365610d8c1904597a9ef46208d4767fa303f3d8"
    )
    assert result.attempted_candidates == 240
    assert result.executable_candidates == 240
    assert result.feasible_candidates == 84
    assert result.selected_parameters == {
        "base_x_um": 120_000,
        "base_y_um": 80_000,
        "base_z_um": 10_000,
        "pin_spacing_um": 80_000,
        "bore_clearance_um": 20,
        "reference_y_um": 15_000,
        "worst_case_error_um": 120,
    }
    capability = result.execution.final_state["capabilities"]
    assert capability["generated_fixture_metrology"]["worst_case_error_um"] == 120


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


def test_blind_bore_that_misses_insertion_path_is_rejected() -> None:
    world, result = generated_fixture()
    raw = deepcopy(program_to_dict(result.program))
    bore = raw["parts"][0]["geometry"]["children"][1]
    bore["center_um"][2] = 9_000
    bore["height_um"] = 2_000
    with pytest.raises(ExecutionError, match="does not span the insertion path"):
        ReferenceInterpreter().execute(world, MechanismProgram.from_mapping(raw))


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
    assert score.capability_gain == pytest.approx(650.0)
    assert score.robustness_pass_rate == pytest.approx(1.0)
    assert score.certified_evidence_tier == "conformance"
