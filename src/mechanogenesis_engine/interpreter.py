from __future__ import annotations

from dataclasses import dataclass
from math import isqrt
from typing import Any, Mapping

from mechanogenesis_bench.canonical import digest

from .errors import ExecutionError, IRValidationError
from .geometry import (
    GeometryFacts,
    ceil_div,
    find_shape,
    primitive_aabb,
    validate_geometry,
)
from .ir import (
    AssemblySpec,
    InventoryItemSpec,
    MachineSpec,
    MaterialSpec,
    MechanismProgram,
    OccurrenceSpec,
    PartSpec,
    PoseQ,
    ShapeNode,
    Vec3Q,
    WorldSpec,
    program_to_dict,
    world_to_dict,
)


@dataclass(frozen=True)
class MaterialBalanceQ:
    material: str
    input_q: int
    reserve_draw_q: int
    output_q: int
    waste_q: int

    def to_dict(self) -> dict[str, object]:
        return {
            "material": self.material,
            "input_q": self.input_q,
            "reserve_draw_q": self.reserve_draw_q,
            "output_q": self.output_q,
            "waste_q": self.waste_q,
        }


@dataclass(frozen=True)
class ExecutionReceipt:
    index: int
    operation: str
    operation_hash: str
    parent_world_hash: str
    child_world_hash: str
    balances: tuple[MaterialBalanceQ, ...]
    duration_us: int
    energy_mj: int
    facts: dict[str, object]

    def to_dict(self) -> dict[str, object]:
        return {
            "index": self.index,
            "operation": self.operation,
            "operation_hash": self.operation_hash,
            "parent_world_hash": self.parent_world_hash,
            "child_world_hash": self.child_world_hash,
            "balances": [balance.to_dict() for balance in self.balances],
            "duration_us": self.duration_us,
            "energy_mj": self.energy_mj,
            "facts": self.facts,
        }


@dataclass(frozen=True)
class ExecutionResult:
    process_hash: str
    parent_world_hash: str
    child_world_hash: str
    final_state: dict[str, object]
    receipts: tuple[ExecutionReceipt, ...]
    geometry_facts: dict[str, GeometryFacts]
    total_duration_us: int
    total_energy_mj: int

    def to_dict(self) -> dict[str, object]:
        return {
            "process_hash": self.process_hash,
            "parent_world_hash": self.parent_world_hash,
            "child_world_hash": self.child_world_hash,
            "final_state": self.final_state,
            "receipts": [receipt.to_dict() for receipt in self.receipts],
            "geometry_facts": {
                part_id: {
                    "aabb_min_um": facts.aabb.minimum_um.to_list(),
                    "aabb_max_um": facts.aabb.maximum_um.to_list(),
                    "volume_lower_um3": facts.volume_um3.lower,
                    "volume_upper_um3": facts.volume_um3.upper,
                    "primitive_count": facts.primitive_count,
                }
                for part_id, facts in self.geometry_facts.items()
            },
            "total_duration_us": self.total_duration_us,
            "total_energy_mj": self.total_energy_mj,
        }


def initial_state(world: WorldSpec) -> dict[str, object]:
    return {
        "schema_version": world.schema_version,
        "world_spec_hash": digest(world_to_dict(world)),
        "inventory": {item.item_id: item.quantity for item in world.inventory},
        "parts": {},
        "assemblies": {},
        "capabilities": {
            "baseline_metrology": {
                "kind": "bounded_pose_error",
                "worst_case_error_um": world.baseline_capability_error_um,
            }
        },
        "sequence": 0,
    }


def initial_world_hash(world: WorldSpec) -> str:
    return digest(initial_state(world))


def _require_exact(operation: Mapping[str, Any], keys: set[str], index: int) -> None:
    missing = sorted(keys - set(operation))
    extra = sorted(set(operation) - keys)
    if missing or extra:
        raise ExecutionError(
            f"operation {index} fields mismatch; missing={missing}, extra={extra}"
        )


def _positive_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ExecutionError(f"{field} must be a positive integer")
    return value


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ExecutionError(f"{field} must be non-empty text")
    return value


def _fits(inner: Vec3Q, outer: Vec3Q) -> bool:
    return inner.x <= outer.x and inner.y <= outer.y and inner.z <= outer.z


def _mass_interval(facts: GeometryFacts, material: MaterialSpec) -> tuple[int, int]:
    lower = (
        facts.volume_um3.lower * material.density_numerator_mg
        // material.density_denominator_um3
    )
    upper = ceil_div(
        facts.volume_um3.upper * material.density_numerator_mg,
        material.density_denominator_um3,
    )
    return lower, upper


def _translated(position: Vec3Q, pose: PoseQ) -> Vec3Q:
    if pose.rotation_mdeg != Vec3Q(0, 0, 0):
        raise IRValidationError(
            "reference interpreter 0.2 supports identity occurrence/datum rotations only"
        )
    return Vec3Q(
        position.x + pose.translation_um.x,
        position.y + pose.translation_um.y,
        position.z + pose.translation_um.z,
    )


def _distance_um(left: Vec3Q, right: Vec3Q) -> int:
    squared = (
        (left.x - right.x) ** 2
        + (left.y - right.y) ** 2
        + (left.z - right.z) ** 2
    )
    root = isqrt(squared)
    return root if root * root == squared else root + 1


class ReferenceInterpreter:
    """Auditable semantics for the axis-aligned CSG/manufacturing 0.2 fragment."""

    def execute(self, world: WorldSpec, program: MechanismProgram) -> ExecutionResult:
        state = initial_state(world)
        parent_hash = digest(state)
        if program.parent_world_hash != parent_hash:
            raise ExecutionError("program parent_world_hash is not the current world")

        materials = {item.material_id: item for item in world.materials}
        inventory_specs = {item.item_id: item for item in world.inventory}
        machines = {item.machine_id: item for item in world.machines}
        parts = {item.part_id: item for item in program.parts}
        assemblies = {item.assembly_id: item for item in program.assemblies}
        for name, values in (
            ("materials", materials),
            ("inventory", inventory_specs),
            ("machines", machines),
            ("parts", parts),
            ("assemblies", assemblies),
        ):
            expected = {
                "materials": len(world.materials),
                "inventory": len(world.inventory),
                "machines": len(world.machines),
                "parts": len(program.parts),
                "assemblies": len(program.assemblies),
            }[name]
            if len(values) != expected:
                raise IRValidationError(f"{name} contains duplicate ids")
        for item in world.inventory:
            if item.material_id not in materials:
                raise IRValidationError(
                    f"inventory item {item.item_id!r} uses unknown material"
                )

        geometry_facts: dict[str, GeometryFacts] = {}
        part_masses: dict[str, int] = {}
        for part in program.parts:
            material = materials.get(part.material_id)
            if material is None:
                raise IRValidationError(f"part {part.part_id!r} uses unknown material")
            facts = validate_geometry(part.geometry)
            geometry_facts[part.part_id] = facts
            _, upper_mass = _mass_interval(facts, material)
            if upper_mass <= 0:
                raise IRValidationError(f"part {part.part_id!r} has zero material mass")
            part_masses[part.part_id] = upper_mass

        self._validate_assemblies(parts, assemblies)
        receipts: list[ExecutionReceipt] = []
        for index, operation in enumerate(program.operations):
            operation_name = _text(operation.get("op"), f"operations[{index}].op")
            before = digest(state)
            if operation_name == "machine_part":
                balances, duration, energy, facts = self._machine_part(
                    state,
                    operation,
                    index,
                    parts,
                    geometry_facts,
                    part_masses,
                    inventory_specs,
                    machines,
                )
            elif operation_name == "consume_component":
                balances, duration, energy, facts = self._consume_component(
                    state,
                    operation,
                    index,
                    parts,
                    geometry_facts,
                    part_masses,
                    inventory_specs,
                    materials,
                    world,
                )
            elif operation_name == "assemble":
                balances, duration, energy, facts = self._assemble(
                    state, operation, index, parts, assemblies, part_masses, world
                )
            elif operation_name == "calibrate":
                balances, duration, energy, facts = self._calibrate(
                    state,
                    operation,
                    index,
                    world,
                    parts,
                    assemblies,
                    part_masses,
                )
            else:
                raise ExecutionError(f"unsupported operation {operation_name!r}")
            state["sequence"] = index + 1
            after = digest(state)
            receipts.append(
                ExecutionReceipt(
                    index=index,
                    operation=operation_name,
                    operation_hash=digest(dict(operation)),
                    parent_world_hash=before,
                    child_world_hash=after,
                    balances=tuple(balances),
                    duration_us=duration,
                    energy_mj=energy,
                    facts=facts,
                )
            )

        return ExecutionResult(
            process_hash=digest(program_to_dict(program)),
            parent_world_hash=parent_hash,
            child_world_hash=digest(state),
            final_state=state,
            receipts=tuple(receipts),
            geometry_facts=geometry_facts,
            total_duration_us=sum(item.duration_us for item in receipts),
            total_energy_mj=sum(item.energy_mj for item in receipts),
        )

    def _validate_assemblies(
        self, parts: dict[str, PartSpec], assemblies: dict[str, AssemblySpec]
    ) -> None:
        for assembly in assemblies.values():
            occurrences = {item.occurrence_id: item for item in assembly.occurrences}
            if assembly.root_occurrence not in occurrences:
                raise IRValidationError(f"assembly {assembly.assembly_id!r} root is missing")
            if len(occurrences) != len(assembly.occurrences):
                raise IRValidationError(f"assembly {assembly.assembly_id!r} has duplicate occurrences")
            for occurrence in assembly.occurrences:
                if occurrence.part_id not in parts:
                    raise IRValidationError(
                        f"occurrence {occurrence.occurrence_id!r} uses unknown part"
                    )
                _translated(Vec3Q(0, 0, 0), occurrence.pose)
            moving_ids: set[str] = set()
            for mate in assembly.mates:
                if mate.fixed_occurrence not in occurrences or mate.moving_occurrence not in occurrences:
                    raise IRValidationError(f"mate {mate.mate_id!r} references unknown occurrence")
                fixed_occurrence = occurrences[mate.fixed_occurrence]
                moving_occurrence = occurrences[mate.moving_occurrence]
                fixed_datum = parts[fixed_occurrence.part_id].datum(mate.fixed_datum)
                moving_datum = parts[moving_occurrence.part_id].datum(mate.moving_datum)
                fixed_position = _translated(
                    _translated(fixed_datum.pose.translation_um, fixed_occurrence.pose),
                    PoseQ(Vec3Q(0, 0, 0), fixed_datum.pose.rotation_mdeg),
                )
                moving_position = _translated(
                    _translated(moving_datum.pose.translation_um, moving_occurrence.pose),
                    PoseQ(Vec3Q(0, 0, 0), moving_datum.pose.rotation_mdeg),
                )
                if _distance_um(fixed_position, moving_position) > mate.tolerance_um:
                    raise IRValidationError(f"mate {mate.mate_id!r} exceeds its position tolerance")
                if fixed_datum.pose.rotation_mdeg != moving_datum.pose.rotation_mdeg:
                    raise IRValidationError(f"mate {mate.mate_id!r} has incompatible frames")
                if mate.moving_occurrence in moving_ids:
                    raise IRValidationError("reference assembly allows one rigid parent per moving occurrence")
                moving_ids.add(mate.moving_occurrence)
            expected_moving = set(occurrences) - {assembly.root_occurrence}
            if moving_ids != expected_moving:
                raise IRValidationError(
                    f"assembly {assembly.assembly_id!r} must rigidly place every non-root occurrence"
                )

    def _machine_part(
        self,
        state: dict[str, object],
        operation: Mapping[str, Any],
        index: int,
        parts: dict[str, PartSpec],
        geometry_facts: dict[str, GeometryFacts],
        part_masses: dict[str, int],
        inventory_specs: dict[str, InventoryItemSpec],
        machines: dict[str, MachineSpec],
    ) -> tuple[list[MaterialBalanceQ], int, int, dict[str, object]]:
        _require_exact(
            operation,
            {"op", "process", "machine_id", "stock_item_id", "part_id"},
            index,
        )
        part_id = _text(operation["part_id"], "part_id")
        process = _text(operation["process"], "process")
        machine_id = _text(operation["machine_id"], "machine_id")
        stock_id = _text(operation["stock_item_id"], "stock_item_id")
        part = parts.get(part_id)
        machine = machines.get(machine_id)
        stock = inventory_specs.get(stock_id)
        if part is None or machine is None or stock is None:
            raise ExecutionError("machine_part references an unknown part, machine or stock")
        if stock.kind != "stock" or part.source_item_id is not None:
            raise ExecutionError("machine_part requires stock and a generated part")
        if process not in machine.operations:
            raise ExecutionError("machine does not support the requested process")
        if part.material_id != stock.material_id:
            raise ExecutionError("part material does not match stock")
        facts = geometry_facts[part_id]
        if not _fits(facts.aabb.size_um, machine.envelope_um):
            raise ExecutionError("part exceeds machine envelope")
        if not _fits(facts.aabb.size_um, stock.envelope_um):
            raise ExecutionError("part exceeds stock envelope")
        for node_label in facts.labels:
            shape = find_shape(part.geometry, node_label)
            if shape.kind == "cylinder" and shape.radius_um is not None:
                if 2 * shape.radius_um < machine.min_feature_um:
                    raise ExecutionError("part contains a feature below machine resolution")
        inventory = state["inventory"]
        assert isinstance(inventory, dict)
        if inventory.get(stock_id, 0) <= 0:
            raise ExecutionError("stock is exhausted")
        state_parts = state["parts"]
        assert isinstance(state_parts, dict)
        if part_id in state_parts:
            raise ExecutionError("part already exists")
        output_mass = part_masses[part_id]
        if output_mass > stock.mass_mg:
            raise ExecutionError("geometry-derived part mass exceeds stock mass")
        inventory[stock_id] -= 1
        state_parts[part_id] = {
            "material_id": part.material_id,
            "mass_mg": output_mass,
            "status": "available",
            "source": stock_id,
        }
        removed_volume = max(0, stock.envelope_um.x * stock.envelope_um.y * stock.envelope_um.z - facts.volume_um3.lower)
        duration = machine.setup_time_us + ceil_div(removed_volume, machine.removal_rate_um3_per_us)
        energy = ceil_div(machine.power_w * duration, 1000)
        return (
            [MaterialBalanceQ(part.material_id, stock.mass_mg, 0, output_mass, stock.mass_mg - output_mass)],
            duration,
            energy,
            {"part_id": part_id, "machine_id": machine_id, "removed_volume_upper_um3": removed_volume},
        )

    def _consume_component(
        self,
        state: dict[str, object],
        operation: Mapping[str, Any],
        index: int,
        parts: dict[str, PartSpec],
        geometry_facts: dict[str, GeometryFacts],
        part_masses: dict[str, int],
        inventory_specs: dict[str, InventoryItemSpec],
        materials: dict[str, MaterialSpec],
        world: WorldSpec,
    ) -> tuple[list[MaterialBalanceQ], int, int, dict[str, object]]:
        _require_exact(operation, {"op", "item_id", "part_id"}, index)
        item_id = _text(operation["item_id"], "item_id")
        part_id = _text(operation["part_id"], "part_id")
        item, part = inventory_specs.get(item_id), parts.get(part_id)
        if item is None or part is None or item.kind != "component":
            raise ExecutionError("consume_component requires a known component and part")
        if part.source_item_id != item_id or part.material_id != item.material_id:
            raise ExecutionError("component part provenance does not match inventory")
        lower_mass, upper_mass = _mass_interval(geometry_facts[part_id], materials[part.material_id])
        if not lower_mass <= item.mass_mg <= upper_mass:
            raise ExecutionError("component mass is inconsistent with canonical geometry")
        inventory = state["inventory"]
        state_parts = state["parts"]
        assert isinstance(inventory, dict) and isinstance(state_parts, dict)
        if inventory.get(item_id, 0) <= 0 or part_id in state_parts:
            raise ExecutionError("component is exhausted or the part already exists")
        inventory[item_id] -= 1
        part_masses[part_id] = item.mass_mg
        state_parts[part_id] = {
            "material_id": part.material_id,
            "mass_mg": item.mass_mg,
            "status": "available",
            "source": item_id,
        }
        duration = world.assembly_time_per_part_us
        energy = ceil_div(world.cell_power_w * duration, 1000)
        return (
            [MaterialBalanceQ(part.material_id, item.mass_mg, 0, item.mass_mg, 0)],
            duration,
            energy,
            {"part_id": part_id, "inventory_item": item_id},
        )

    def _assemble(
        self,
        state: dict[str, object],
        operation: Mapping[str, Any],
        index: int,
        parts: dict[str, PartSpec],
        assemblies: dict[str, AssemblySpec],
        part_masses: dict[str, int],
        world: WorldSpec,
    ) -> tuple[list[MaterialBalanceQ], int, int, dict[str, object]]:
        _require_exact(operation, {"op", "assembly_id"}, index)
        assembly_id = _text(operation["assembly_id"], "assembly_id")
        assembly = assemblies.get(assembly_id)
        if assembly is None:
            raise ExecutionError("assemble references an unknown assembly")
        state_parts = state["parts"]
        state_assemblies = state["assemblies"]
        assert isinstance(state_parts, dict) and isinstance(state_assemblies, dict)
        if assembly_id in state_assemblies:
            raise ExecutionError("assembly already exists")
        grouped: dict[str, int] = {}
        for occurrence in assembly.occurrences:
            record = state_parts.get(occurrence.part_id)
            if not isinstance(record, dict) or record.get("status") != "available":
                raise ExecutionError(f"part {occurrence.part_id!r} is unavailable for assembly")
            material_id = parts[occurrence.part_id].material_id
            grouped[material_id] = grouped.get(material_id, 0) + part_masses[occurrence.part_id]
            record["status"] = f"installed:{assembly_id}"
        state_assemblies[assembly_id] = {
            "status": "assembled",
            "occurrences": [item.occurrence_id for item in assembly.occurrences],
            "mass_mg": sum(grouped.values()),
        }
        duration = world.assembly_time_per_part_us * len(assembly.occurrences)
        energy = ceil_div(world.cell_power_w * duration, 1000)
        return (
            [MaterialBalanceQ(material, mass, 0, mass, 0) for material, mass in sorted(grouped.items())],
            duration,
            energy,
            {"assembly_id": assembly_id, "occurrence_count": len(assembly.occurrences)},
        )

    def _calibrate(
        self,
        state: dict[str, object],
        operation: Mapping[str, Any],
        index: int,
        world: WorldSpec,
        parts: dict[str, PartSpec],
        assemblies: dict[str, AssemblySpec],
        part_masses: dict[str, int],
    ) -> tuple[list[MaterialBalanceQ], int, int, dict[str, object]]:
        _require_exact(operation, {"op", "assembly_id", "capability_id", "locator_occurrences", "reference_occurrence", "workpiece_span_um"}, index)
        assembly_id = _text(operation["assembly_id"], "assembly_id")
        capability_id = _text(operation["capability_id"], "capability_id")
        locator_ids = operation["locator_occurrences"]
        if not isinstance(locator_ids, list) or len(locator_ids) != 2:
            raise ExecutionError("calibrate requires exactly two locator occurrences")
        locator_ids = [_text(item, "locator_occurrences") for item in locator_ids]
        reference_id = _text(operation["reference_occurrence"], "reference_occurrence")
        if len(set(locator_ids)) != 2 or reference_id in locator_ids:
            raise ExecutionError("calibration roles must be distinct occurrences")
        workpiece_span = _positive_int(operation["workpiece_span_um"], "workpiece_span_um")
        state_assemblies = state["assemblies"]
        capabilities = state["capabilities"]
        assert isinstance(state_assemblies, dict) and isinstance(capabilities, dict)
        if assembly_id not in state_assemblies or capability_id in capabilities:
            raise ExecutionError("calibration assembly is absent or capability already exists")
        assembly = assemblies[assembly_id]
        occurrences = {item.occurrence_id: item for item in assembly.occurrences}
        if any(item not in occurrences for item in [*locator_ids, reference_id]):
            raise ExecutionError("calibration roles reference unknown occurrences")
        locators = [occurrences[item] for item in locator_ids]
        pin_shapes = [parts[item.part_id].geometry for item in locators]
        if any(shape.kind != "cylinder" or shape.axis != "z" for shape in pin_shapes):
            raise ExecutionError("reference calibration requires vertical cylindrical locators")
        positions = [item.pose.translation_um for item in locators]
        spacing = _distance_um(positions[0], positions[1])
        if spacing <= 0:
            raise ExecutionError("locator spacing must be positive")
        root = occurrences[assembly.root_occurrence]
        base_part = parts[root.part_id]
        if base_part.geometry.kind != "difference":
            raise ExecutionError(
                "reference calibration requires a subtractively bored base"
            )

        base_aabb = validate_geometry(base_part.geometry).aabb
        base_top_world = base_aabb.maximum_um.z + root.pose.translation_um.z

        def matching_bore(
            occurrence: OccurrenceSpec,
            component_shape: ShapeNode,
            role: str,
        ) -> ShapeNode:
            candidates = [
                node
                for node in base_part.geometry.children[1:]
                if node.kind == "cylinder"
                and node.center_um is not None
                and node.center_um.x + root.pose.translation_um.x
                == occurrence.pose.translation_um.x
                and node.center_um.y + root.pose.translation_um.y
                == occurrence.pose.translation_um.y
            ]
            if len(candidates) != 1:
                raise ExecutionError(f"{role} must match one canonical base bore")
            bore = candidates[0]
            bore_aabb = primitive_aabb(bore)
            component_aabb = primitive_aabb(component_shape)
            bore_bottom_world = bore_aabb.minimum_um.z + root.pose.translation_um.z
            bore_top_world = bore_aabb.maximum_um.z + root.pose.translation_um.z
            insertion_bottom_world = (
                component_aabb.minimum_um.z + occurrence.pose.translation_um.z
            )
            if (
                bore_bottom_world > insertion_bottom_world
                or bore_top_world < base_top_world
            ):
                raise ExecutionError(f"{role} bore does not span the insertion path")
            return bore

        hole_radii: list[int] = []
        for occurrence, pin_shape in zip(locators, pin_shapes, strict=True):
            bore = matching_bore(occurrence, pin_shape, "locator")
            assert bore.radius_um is not None and pin_shape.radius_um is not None
            if bore.radius_um < pin_shape.radius_um:
                raise ExecutionError("locator does not fit its bore")
            hole_radii.append(bore.radius_um)
        clearances = [
            hole_radius - int(pin_shape.radius_um or 0)
            for hole_radius, pin_shape in zip(hole_radii, pin_shapes, strict=True)
        ]
        radial_clearance = max(clearances)
        reference_occurrence = occurrences[reference_id]
        reference_shape = parts[reference_occurrence.part_id].geometry
        if reference_shape.kind != "cylinder" or reference_shape.axis != "z":
            raise ExecutionError(
                "reference calibration requires a vertical cylindrical reference"
            )
        reference_bore = matching_bore(
            reference_occurrence, reference_shape, "reference post"
        )
        assert reference_bore.radius_um is not None
        assert reference_shape.radius_um is not None
        if reference_bore.radius_um < reference_shape.radius_um:
            raise ExecutionError("reference post does not fit its bore")
        reference_clearance = reference_bore.radius_um - reference_shape.radius_um
        angular_tip_error = ceil_div(2 * radial_clearance * workpiece_span, spacing)
        worst_error = (
            radial_clearance
            + reference_clearance
            + angular_tip_error
            + world.probe_repeatability_um
            + world.disturbance_bound_um
        )
        capabilities[capability_id] = {
            "kind": "two_locator_metrology_fixture",
            "assembly_id": assembly_id,
            "locator_spacing_um": spacing,
            "radial_clearance_um": radial_clearance,
            "reference_clearance_um": reference_clearance,
            "angular_tip_error_um": angular_tip_error,
            "worst_case_error_um": worst_error,
            "reference_occurrence": reference_id,
        }
        grouped: dict[str, int] = {}
        for occurrence in assembly.occurrences:
            material = parts[occurrence.part_id].material_id
            grouped[material] = grouped.get(material, 0) + part_masses[occurrence.part_id]
        duration = world.calibration_time_us
        energy = ceil_div(world.cell_power_w * duration, 1000)
        return (
            [MaterialBalanceQ(material, mass, 0, mass, 0) for material, mass in sorted(grouped.items())],
            duration,
            energy,
            {
                "capability_id": capability_id,
                "locator_spacing_um": spacing,
                "radial_clearance_um": radial_clearance,
                "reference_clearance_um": reference_clearance,
                "worst_case_error_um": worst_error,
            },
        )
