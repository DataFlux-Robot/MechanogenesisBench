from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Any, Mapping

from .errors import ExecutionError, IRValidationError
from .interpreter import ExecutionResult, ReferenceInterpreter, initial_world_hash
from .ir import MechanismProgram, WorldSpec


def _positive_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise IRValidationError(f"{field} must be a positive integer")
    return value


def _positive_list(value: Any, field: str) -> tuple[int, ...]:
    if not isinstance(value, list) or not value:
        raise IRValidationError(f"{field} must be a non-empty list")
    result = tuple(_positive_int(item, f"{field}[{index}]") for index, item in enumerate(value))
    if len(set(result)) != len(result):
        raise IRValidationError(f"{field} must not contain duplicates")
    return result


@dataclass(frozen=True)
class FixtureGoal:
    max_worst_case_error_um: int
    base_min_size_um: tuple[int, int, int]
    minimum_edge_margin_um: int
    workpiece_span_um: int
    insert_depth_um: int
    pin_spacing_candidates_um: tuple[int, ...]
    bore_clearance_candidates_um: tuple[int, ...]
    reference_y_candidates_um: tuple[int, ...]

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "FixtureGoal":
        expected = {
            "max_worst_case_error_um",
            "base_min_size_um",
            "minimum_edge_margin_um",
            "workpiece_span_um",
            "insert_depth_um",
            "pin_spacing_candidates_um",
            "bore_clearance_candidates_um",
            "reference_y_candidates_um",
        }
        if set(raw) != expected:
            raise IRValidationError(
                f"fixture goal fields mismatch; missing={sorted(expected-set(raw))}, extra={sorted(set(raw)-expected)}"
            )
        base = _positive_list(raw["base_min_size_um"], "base_min_size_um")
        if len(base) != 3:
            raise IRValidationError("base_min_size_um must have three components")
        return cls(
            max_worst_case_error_um=_positive_int(raw["max_worst_case_error_um"], "max_worst_case_error_um"),
            base_min_size_um=(base[0], base[1], base[2]),
            minimum_edge_margin_um=_positive_int(raw["minimum_edge_margin_um"], "minimum_edge_margin_um"),
            workpiece_span_um=_positive_int(raw["workpiece_span_um"], "workpiece_span_um"),
            insert_depth_um=_positive_int(raw["insert_depth_um"], "insert_depth_um"),
            pin_spacing_candidates_um=_positive_list(raw["pin_spacing_candidates_um"], "pin_spacing_candidates_um"),
            bore_clearance_candidates_um=_positive_list(raw["bore_clearance_candidates_um"], "bore_clearance_candidates_um"),
            reference_y_candidates_um=_positive_list(raw["reference_y_candidates_um"], "reference_y_candidates_um"),
        )


@dataclass(frozen=True)
class SearchResult:
    program: MechanismProgram
    execution: ExecutionResult
    attempted_candidates: int
    executable_candidates: int
    feasible_candidates: int
    selected_parameters: dict[str, int]


def _pose(x: int, y: int, z: int) -> dict[str, object]:
    return {"translation_um": [x, y, z], "rotation_mdeg": [0, 0, 0]}


def _cylinder(label: str, radius: int, height: int) -> dict[str, object]:
    return {
        "label": label,
        "kind": "cylinder",
        "center_um": [0, 0, 0],
        "radius_um": radius,
        "height_um": height,
        "axis": "z",
    }


def _program_mapping(
    world: WorldSpec,
    goal: FixtureGoal,
    *,
    base_size: tuple[int, int, int],
    pin_spacing: int,
    clearance: int,
    reference_y: int,
) -> dict[str, object]:
    stock = next(item for item in world.inventory if item.role == "fixture_base_stock")
    locator_item = next(item for item in world.inventory if item.role == "locator_pin")
    reference_item = next(item for item in world.inventory if item.role == "reference_post")
    machine = next(item for item in world.machines if "milling" in item.operations)

    base_x, base_y, base_z = base_size
    pin_radius = locator_item.envelope_um.x // 2
    reference_radius = reference_item.envelope_um.x // 2
    hole_radius = pin_radius + clearance
    reference_hole_radius = reference_radius + clearance
    locator_y = -10_000
    locator_x = pin_spacing // 2
    seat_z = base_z - goal.insert_depth_um
    locator_center_z = seat_z + locator_item.envelope_um.z // 2
    reference_center_z = seat_z + reference_item.envelope_um.z // 2

    base_geometry = {
        "label": "fixture_base_with_bores",
        "kind": "difference",
        "children": [
            {
                "label": "fixture_base_blank",
                "kind": "box",
                "center_um": [0, 0, base_z // 2],
                "size_um": [base_x, base_y, base_z],
            },
            {
                "label": "locator_bore_a",
                "kind": "cylinder",
                "center_um": [-locator_x, locator_y, base_z // 2],
                "radius_um": hole_radius,
                "height_um": base_z,
                "axis": "z",
            },
            {
                "label": "locator_bore_b",
                "kind": "cylinder",
                "center_um": [locator_x, locator_y, base_z // 2],
                "radius_um": hole_radius,
                "height_um": base_z,
                "axis": "z",
            },
            {
                "label": "reference_bore",
                "kind": "cylinder",
                "center_um": [0, reference_y, base_z // 2],
                "radius_um": reference_hole_radius,
                "height_um": base_z,
                "axis": "z",
            },
        ],
    }
    zero = _pose(0, 0, 0)
    parts = [
        {
            "part_id": "fixture_base",
            "label": "generated_fixture_base",
            "material_id": stock.material_id,
            "source_item_id": None,
            "geometry": base_geometry,
            "datums": [
                {"datum_id": "root", "pose": zero},
                {"datum_id": "locator_a_seat", "pose": _pose(-locator_x, locator_y, seat_z)},
                {"datum_id": "locator_b_seat", "pose": _pose(locator_x, locator_y, seat_z)},
                {"datum_id": "reference_seat", "pose": _pose(0, reference_y, seat_z)},
            ],
        },
        {
            "part_id": "locator_pin_a",
            "label": "locator_pin_left",
            "material_id": locator_item.material_id,
            "source_item_id": locator_item.item_id,
            "geometry": _cylinder("locator_pin_body_a", pin_radius, locator_item.envelope_um.z),
            "datums": [
                {
                    "datum_id": "mount",
                    "pose": _pose(0, 0, -locator_item.envelope_um.z // 2),
                }
            ],
        },
        {
            "part_id": "locator_pin_b",
            "label": "locator_pin_right",
            "material_id": locator_item.material_id,
            "source_item_id": locator_item.item_id,
            "geometry": _cylinder("locator_pin_body_b", pin_radius, locator_item.envelope_um.z),
            "datums": [
                {
                    "datum_id": "mount",
                    "pose": _pose(0, 0, -locator_item.envelope_um.z // 2),
                }
            ],
        },
        {
            "part_id": "reference_post",
            "label": "probe_reference_post",
            "material_id": reference_item.material_id,
            "source_item_id": reference_item.item_id,
            "geometry": _cylinder("reference_post_body", reference_radius, reference_item.envelope_um.z),
            "datums": [
                {
                    "datum_id": "mount",
                    "pose": _pose(0, 0, -reference_item.envelope_um.z // 2),
                }
            ],
        },
    ]
    occurrences = [
        {"occurrence_id": "base", "part_id": "fixture_base", "pose": zero},
        {"occurrence_id": "locator_a", "part_id": "locator_pin_a", "pose": _pose(-locator_x, locator_y, locator_center_z)},
        {"occurrence_id": "locator_b", "part_id": "locator_pin_b", "pose": _pose(locator_x, locator_y, locator_center_z)},
        {"occurrence_id": "reference_post", "part_id": "reference_post", "pose": _pose(0, reference_y, reference_center_z)},
    ]
    mates = [
        {
            "mate_id": "seat_locator_a",
            "relation": "rigid",
            "fixed_occurrence": "base",
            "fixed_datum": "locator_a_seat",
            "moving_occurrence": "locator_a",
            "moving_datum": "mount",
            "tolerance_um": 0,
        },
        {
            "mate_id": "seat_locator_b",
            "relation": "rigid",
            "fixed_occurrence": "base",
            "fixed_datum": "locator_b_seat",
            "moving_occurrence": "locator_b",
            "moving_datum": "mount",
            "tolerance_um": 0,
        },
        {
            "mate_id": "seat_reference_post",
            "relation": "rigid",
            "fixed_occurrence": "base",
            "fixed_datum": "reference_seat",
            "moving_occurrence": "reference_post",
            "moving_datum": "mount",
            "tolerance_um": 0,
        },
    ]
    return {
        "schema_version": "0.2",
        "program_id": f"generated_metrology_fixture_s{pin_spacing}_c{clearance}_r{reference_y}",
        "parent_world_hash": initial_world_hash(world),
        "parts": parts,
        "assemblies": [
            {
                "assembly_id": "metrology_fixture",
                "label": "generated_metrology_fixture",
                "root_occurrence": "base",
                "occurrences": occurrences,
                "mates": mates,
            }
        ],
        "operations": [
            {
                "op": "machine_part",
                "process": "milling",
                "machine_id": machine.machine_id,
                "stock_item_id": stock.item_id,
                "part_id": "fixture_base",
            },
            {"op": "consume_component", "item_id": locator_item.item_id, "part_id": "locator_pin_a"},
            {"op": "consume_component", "item_id": locator_item.item_id, "part_id": "locator_pin_b"},
            {"op": "consume_component", "item_id": reference_item.item_id, "part_id": "reference_post"},
            {"op": "assemble", "assembly_id": "metrology_fixture"},
            {
                "op": "calibrate",
                "assembly_id": "metrology_fixture",
                "capability_id": "generated_fixture_metrology",
                "locator_occurrences": ["locator_a", "locator_b"],
                "reference_occurrence": "reference_post",
                "workpiece_span_um": goal.workpiece_span_um,
            },
        ],
    }


def _edge_clearance_ok(
    base_size: tuple[int, int, int],
    pin_spacing: int,
    locator_y: int,
    pin_radius: int,
    reference_y: int,
    reference_radius: int,
    minimum: int,
) -> bool:
    half_x, half_y = base_size[0] // 2, base_size[1] // 2
    return (
        half_x - pin_spacing // 2 - pin_radius >= minimum
        and half_y - abs(locator_y) - pin_radius >= minimum
        and half_x - reference_radius >= minimum
        and half_y - abs(reference_y) - reference_radius >= minimum
    )


def search_fixture(world: WorldSpec, goal: FixtureGoal) -> SearchResult:
    """Enumerate and execute geometry programs; no prebuilt fixture is selected."""

    stock = next((item for item in world.inventory if item.role == "fixture_base_stock"), None)
    locator = next((item for item in world.inventory if item.role == "locator_pin"), None)
    reference = next((item for item in world.inventory if item.role == "reference_post"), None)
    if stock is None or locator is None or reference is None:
        raise IRValidationError("world lacks stock, locator or reference roles")
    if locator.quantity < 2 or reference.quantity < 1:
        raise IRValidationError("inventory cannot instantiate the fixture assembly")
    if any(goal.base_min_size_um[index] > stock.envelope_um.to_list()[index] for index in range(3)):
        raise IRValidationError("minimum base does not fit available stock")

    base_sizes = []
    for trim_x in range(0, stock.envelope_um.x - goal.base_min_size_um[0] + 1, 5_000):
        for trim_y in range(0, stock.envelope_um.y - goal.base_min_size_um[1] + 1, 5_000):
            base_sizes.append(
                (
                    stock.envelope_um.x - trim_x,
                    stock.envelope_um.y - trim_y,
                    goal.base_min_size_um[2],
                )
            )
    attempted = 0
    executable = 0
    feasible: list[tuple[tuple[int, int, int], MechanismProgram, ExecutionResult, dict[str, int]]] = []
    interpreter = ReferenceInterpreter()
    for base_size, spacing, clearance, reference_y in product(
        base_sizes,
        goal.pin_spacing_candidates_um,
        goal.bore_clearance_candidates_um,
        goal.reference_y_candidates_um,
    ):
        attempted += 1
        if not _edge_clearance_ok(
            base_size,
            spacing,
            -10_000,
            locator.envelope_um.x // 2 + clearance,
            reference_y,
            reference.envelope_um.x // 2 + clearance,
            goal.minimum_edge_margin_um,
        ):
            continue
        try:
            program = MechanismProgram.from_mapping(
                _program_mapping(
                    world,
                    goal,
                    base_size=base_size,
                    pin_spacing=spacing,
                    clearance=clearance,
                    reference_y=reference_y,
                )
            )
            execution = interpreter.execute(world, program)
        except (ExecutionError, IRValidationError):
            continue
        executable += 1
        capability = execution.final_state["capabilities"]
        assert isinstance(capability, dict)
        generated = capability["generated_fixture_metrology"]
        assert isinstance(generated, dict)
        worst_error = int(generated["worst_case_error_um"])
        if worst_error <= goal.max_worst_case_error_um:
            parameters = {
                "base_x_um": base_size[0],
                "base_y_um": base_size[1],
                "base_z_um": base_size[2],
                "pin_spacing_um": spacing,
                "bore_clearance_um": clearance,
                "reference_y_um": reference_y,
                "worst_case_error_um": worst_error,
            }
            objective = (
                worst_error,
                base_size[0] * base_size[1] * base_size[2],
                execution.total_duration_us,
            )
            feasible.append((objective, program, execution, parameters))
    if not feasible:
        raise ExecutionError("search found no executable fixture satisfying the public goal")
    feasible.sort(key=lambda item: item[0])
    _, program, execution, parameters = feasible[0]
    return SearchResult(
        program=program,
        execution=execution,
        attempted_candidates=attempted,
        executable_candidates=executable,
        feasible_candidates=len(feasible),
        selected_parameters=parameters,
    )
