from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from .errors import IRValidationError


SCHEMA_VERSION = "0.3"


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise IRValidationError(f"{field} must be an object")
    return value


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise IRValidationError(f"{field} must be non-empty text")
    return value


def _nat(value: Any, field: str, *, positive: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise IRValidationError(f"{field} must be an integer")
    if value < (1 if positive else 0):
        qualifier = "positive" if positive else "nonnegative"
        raise IRValidationError(f"{field} must be {qualifier}")
    return value


def _keys(raw: Mapping[str, Any], expected: set[str], field: str) -> None:
    missing = sorted(expected - set(raw))
    extra = sorted(set(raw) - expected)
    if missing or extra:
        raise IRValidationError(f"{field} fields mismatch; missing={missing}, extra={extra}")


@dataclass(frozen=True)
class Vec3Q:
    """Fixed-point vector. Field names at use sites define the physical unit."""

    x: int
    y: int
    z: int

    @classmethod
    def from_value(cls, value: Any, field: str) -> "Vec3Q":
        if not isinstance(value, list) or len(value) != 3:
            raise IRValidationError(f"{field} must be a three-integer list")
        return cls(*(_nat(item, f"{field}[{index}]") if field.endswith("size_um") else _signed_int(item, f"{field}[{index}]") for index, item in enumerate(value)))

    def to_list(self) -> list[int]:
        return [self.x, self.y, self.z]


def _signed_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise IRValidationError(f"{field} must be an integer")
    return value


def _positive_vec3(value: Any, field: str) -> Vec3Q:
    vector = Vec3Q.from_value(value, field)
    if min(vector.x, vector.y, vector.z) <= 0:
        raise IRValidationError(f"{field} components must be positive")
    return vector


@dataclass(frozen=True)
class PoseQ:
    translation_um: Vec3Q
    rotation_mdeg: Vec3Q

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any], field: str) -> "PoseQ":
        _keys(raw, {"translation_um", "rotation_mdeg"}, field)
        return cls(
            translation_um=Vec3Q.from_value(raw["translation_um"], f"{field}.translation_um"),
            rotation_mdeg=Vec3Q.from_value(raw["rotation_mdeg"], f"{field}.rotation_mdeg"),
        )

    @classmethod
    def identity(cls) -> "PoseQ":
        return cls(Vec3Q(0, 0, 0), Vec3Q(0, 0, 0))

    def to_dict(self) -> dict[str, object]:
        return {
            "translation_um": self.translation_um.to_list(),
            "rotation_mdeg": self.rotation_mdeg.to_list(),
        }


@dataclass(frozen=True)
class ShapeNode:
    label: str
    kind: str
    center_um: Vec3Q | None = None
    size_um: Vec3Q | None = None
    radius_um: int | None = None
    height_um: int | None = None
    axis: str | None = None
    children: tuple["ShapeNode", ...] = ()

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any], field: str) -> "ShapeNode":
        kind = _text(raw.get("kind"), f"{field}.kind")
        label = _text(raw.get("label"), f"{field}.label")
        if kind == "box":
            _keys(raw, {"label", "kind", "center_um", "size_um"}, field)
            size = Vec3Q.from_value(raw["size_um"], f"{field}.size_um")
            if min(size.x, size.y, size.z) <= 0:
                raise IRValidationError(f"{field}.size_um components must be positive")
            return cls(
                label=label,
                kind=kind,
                center_um=Vec3Q.from_value(raw["center_um"], f"{field}.center_um"),
                size_um=size,
            )
        if kind == "cylinder":
            _keys(raw, {"label", "kind", "center_um", "radius_um", "height_um", "axis"}, field)
            axis = _text(raw["axis"], f"{field}.axis")
            if axis not in {"x", "y", "z"}:
                raise IRValidationError(f"{field}.axis must be x, y or z")
            return cls(
                label=label,
                kind=kind,
                center_um=Vec3Q.from_value(raw["center_um"], f"{field}.center_um"),
                radius_um=_nat(raw["radius_um"], f"{field}.radius_um", positive=True),
                height_um=_nat(raw["height_um"], f"{field}.height_um", positive=True),
                axis=axis,
            )
        if kind in {"difference", "union"}:
            _keys(raw, {"label", "kind", "children"}, field)
            children_raw = raw["children"]
            if not isinstance(children_raw, list) or len(children_raw) < 2:
                raise IRValidationError(f"{field}.children must contain at least two shapes")
            children = tuple(
                cls.from_mapping(_mapping(item, f"{field}.children[{index}]"), f"{field}.children[{index}]")
                for index, item in enumerate(children_raw)
            )
            return cls(label=label, kind=kind, children=children)
        raise IRValidationError(f"{field}.kind {kind!r} is unsupported")

    def to_dict(self) -> dict[str, object]:
        if self.kind == "box":
            assert self.center_um is not None and self.size_um is not None
            return {
                "label": self.label,
                "kind": self.kind,
                "center_um": self.center_um.to_list(),
                "size_um": self.size_um.to_list(),
            }
        if self.kind == "cylinder":
            assert self.center_um is not None
            return {
                "label": self.label,
                "kind": self.kind,
                "center_um": self.center_um.to_list(),
                "radius_um": self.radius_um,
                "height_um": self.height_um,
                "axis": self.axis,
            }
        return {
            "label": self.label,
            "kind": self.kind,
            "children": [child.to_dict() for child in self.children],
        }


@dataclass(frozen=True)
class DatumSpec:
    datum_id: str
    pose: PoseQ

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any], field: str) -> "DatumSpec":
        _keys(raw, {"datum_id", "pose"}, field)
        return cls(
            datum_id=_text(raw["datum_id"], f"{field}.datum_id"),
            pose=PoseQ.from_mapping(_mapping(raw["pose"], f"{field}.pose"), f"{field}.pose"),
        )


@dataclass(frozen=True)
class PartSpec:
    part_id: str
    label: str
    material_id: str
    source_item_id: str | None
    geometry: ShapeNode
    datums: tuple[DatumSpec, ...]

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any], field: str) -> "PartSpec":
        _keys(raw, {"part_id", "label", "material_id", "source_item_id", "geometry", "datums"}, field)
        source = raw["source_item_id"]
        if source is not None:
            source = _text(source, f"{field}.source_item_id")
        raw_datums = raw["datums"]
        if not isinstance(raw_datums, list):
            raise IRValidationError(f"{field}.datums must be a list")
        datums = tuple(
            DatumSpec.from_mapping(_mapping(item, f"{field}.datums[{index}]"), f"{field}.datums[{index}]")
            for index, item in enumerate(raw_datums)
        )
        if len({datum.datum_id for datum in datums}) != len(datums):
            raise IRValidationError(f"{field}.datums contains duplicate ids")
        return cls(
            part_id=_text(raw["part_id"], f"{field}.part_id"),
            label=_text(raw["label"], f"{field}.label"),
            material_id=_text(raw["material_id"], f"{field}.material_id"),
            source_item_id=source,
            geometry=ShapeNode.from_mapping(_mapping(raw["geometry"], f"{field}.geometry"), f"{field}.geometry"),
            datums=datums,
        )

    def datum(self, datum_id: str) -> DatumSpec:
        for datum in self.datums:
            if datum.datum_id == datum_id:
                return datum
        raise IRValidationError(f"part {self.part_id!r} has no datum {datum_id!r}")


@dataclass(frozen=True)
class OccurrenceSpec:
    occurrence_id: str
    part_id: str
    pose: PoseQ

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any], field: str) -> "OccurrenceSpec":
        _keys(raw, {"occurrence_id", "part_id", "pose"}, field)
        return cls(
            occurrence_id=_text(raw["occurrence_id"], f"{field}.occurrence_id"),
            part_id=_text(raw["part_id"], f"{field}.part_id"),
            pose=PoseQ.from_mapping(_mapping(raw["pose"], f"{field}.pose"), f"{field}.pose"),
        )


@dataclass(frozen=True)
class MateSpec:
    mate_id: str
    relation: str
    fixed_occurrence: str
    fixed_datum: str
    moving_occurrence: str
    moving_datum: str
    tolerance_um: int

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any], field: str) -> "MateSpec":
        _keys(raw, {"mate_id", "relation", "fixed_occurrence", "fixed_datum", "moving_occurrence", "moving_datum", "tolerance_um"}, field)
        relation = _text(raw["relation"], f"{field}.relation")
        if relation != "rigid":
            raise IRValidationError(f"{field}.relation is outside reference fragment")
        return cls(
            mate_id=_text(raw["mate_id"], f"{field}.mate_id"),
            relation=relation,
            fixed_occurrence=_text(raw["fixed_occurrence"], f"{field}.fixed_occurrence"),
            fixed_datum=_text(raw["fixed_datum"], f"{field}.fixed_datum"),
            moving_occurrence=_text(raw["moving_occurrence"], f"{field}.moving_occurrence"),
            moving_datum=_text(raw["moving_datum"], f"{field}.moving_datum"),
            tolerance_um=_nat(raw["tolerance_um"], f"{field}.tolerance_um"),
        )


@dataclass(frozen=True)
class AssemblySpec:
    assembly_id: str
    label: str
    root_occurrence: str
    occurrences: tuple[OccurrenceSpec, ...]
    mates: tuple[MateSpec, ...]

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any], field: str) -> "AssemblySpec":
        _keys(raw, {"assembly_id", "label", "root_occurrence", "occurrences", "mates"}, field)
        occurrences_raw = raw["occurrences"]
        mates_raw = raw["mates"]
        if not isinstance(occurrences_raw, list) or not occurrences_raw:
            raise IRValidationError(f"{field}.occurrences must be non-empty")
        if not isinstance(mates_raw, list):
            raise IRValidationError(f"{field}.mates must be a list")
        occurrences = tuple(
            OccurrenceSpec.from_mapping(_mapping(item, f"{field}.occurrences[{index}]"), f"{field}.occurrences[{index}]")
            for index, item in enumerate(occurrences_raw)
        )
        mates = tuple(
            MateSpec.from_mapping(_mapping(item, f"{field}.mates[{index}]"), f"{field}.mates[{index}]")
            for index, item in enumerate(mates_raw)
        )
        if len({item.occurrence_id for item in occurrences}) != len(occurrences):
            raise IRValidationError(f"{field}.occurrences contains duplicate ids")
        return cls(
            assembly_id=_text(raw["assembly_id"], f"{field}.assembly_id"),
            label=_text(raw["label"], f"{field}.label"),
            root_occurrence=_text(raw["root_occurrence"], f"{field}.root_occurrence"),
            occurrences=occurrences,
            mates=mates,
        )


@dataclass(frozen=True)
class MaterialSpec:
    material_id: str
    density_numerator_mg: int
    density_denominator_um3: int

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any], field: str) -> "MaterialSpec":
        _keys(raw, {"material_id", "density_numerator_mg", "density_denominator_um3"}, field)
        return cls(
            material_id=_text(raw["material_id"], f"{field}.material_id"),
            density_numerator_mg=_nat(raw["density_numerator_mg"], f"{field}.density_numerator_mg", positive=True),
            density_denominator_um3=_nat(raw["density_denominator_um3"], f"{field}.density_denominator_um3", positive=True),
        )


@dataclass(frozen=True)
class InventoryItemSpec:
    item_id: str
    kind: str
    role: str
    material_id: str
    quantity: int
    mass_mg: int
    envelope_um: Vec3Q

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any], field: str) -> "InventoryItemSpec":
        _keys(raw, {"item_id", "kind", "role", "material_id", "quantity", "mass_mg", "envelope_um"}, field)
        kind = _text(raw["kind"], f"{field}.kind")
        if kind not in {"stock", "component"}:
            raise IRValidationError(f"{field}.kind must be stock or component")
        return cls(
            item_id=_text(raw["item_id"], f"{field}.item_id"),
            kind=kind,
            role=_text(raw["role"], f"{field}.role"),
            material_id=_text(raw["material_id"], f"{field}.material_id"),
            quantity=_nat(raw["quantity"], f"{field}.quantity", positive=True),
            mass_mg=_nat(raw["mass_mg"], f"{field}.mass_mg", positive=True),
            envelope_um=_positive_vec3(
                raw["envelope_um"], f"{field}.envelope_um"
            ),
        )


@dataclass(frozen=True)
class MachineSpec:
    machine_id: str
    envelope_um: Vec3Q
    min_feature_um: int
    removal_rate_um3_per_us: int
    setup_time_us: int
    power_w: int
    absolute_setup_error_um: int
    relative_repeatability_um: int
    operations: tuple[str, ...]

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any], field: str) -> "MachineSpec":
        _keys(
            raw,
            {
                "machine_id",
                "envelope_um",
                "min_feature_um",
                "removal_rate_um3_per_us",
                "setup_time_us",
                "power_w",
                "absolute_setup_error_um",
                "relative_repeatability_um",
                "operations",
            },
            field,
        )
        operations = raw["operations"]
        if not isinstance(operations, list) or not operations:
            raise IRValidationError(f"{field}.operations must be non-empty")
        return cls(
            machine_id=_text(raw["machine_id"], f"{field}.machine_id"),
            envelope_um=_positive_vec3(
                raw["envelope_um"], f"{field}.envelope_um"
            ),
            min_feature_um=_nat(raw["min_feature_um"], f"{field}.min_feature_um", positive=True),
            removal_rate_um3_per_us=_nat(raw["removal_rate_um3_per_us"], f"{field}.removal_rate_um3_per_us", positive=True),
            setup_time_us=_nat(raw["setup_time_us"], f"{field}.setup_time_us"),
            power_w=_nat(raw["power_w"], f"{field}.power_w", positive=True),
            absolute_setup_error_um=_nat(
                raw["absolute_setup_error_um"],
                f"{field}.absolute_setup_error_um",
                positive=True,
            ),
            relative_repeatability_um=_nat(
                raw["relative_repeatability_um"],
                f"{field}.relative_repeatability_um",
            ),
            operations=tuple(_text(value, f"{field}.operations") for value in operations),
        )


@dataclass(frozen=True)
class WorldSpec:
    schema_version: str
    world_id: str
    materials: tuple[MaterialSpec, ...]
    inventory: tuple[InventoryItemSpec, ...]
    machines: tuple[MachineSpec, ...]
    probe_repeatability_um: int
    disturbance_bound_um: int
    baseline_capability_error_um: int
    assembly_time_per_part_us: int
    calibration_time_us: int
    cell_power_w: int

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "WorldSpec":
        _keys(raw, {"schema_version", "world_id", "materials", "inventory", "machines", "probe_repeatability_um", "disturbance_bound_um", "baseline_capability_error_um", "assembly_time_per_part_us", "calibration_time_us", "cell_power_w"}, "world")
        if raw["schema_version"] != SCHEMA_VERSION:
            raise IRValidationError("unsupported world schema version")
        materials_raw = raw["materials"]
        inventory_raw = raw["inventory"]
        machines_raw = raw["machines"]
        if not all(isinstance(value, list) and value for value in (materials_raw, inventory_raw, machines_raw)):
            raise IRValidationError("world materials, inventory and machines must be non-empty lists")
        return cls(
            schema_version=SCHEMA_VERSION,
            world_id=_text(raw["world_id"], "world.world_id"),
            materials=tuple(MaterialSpec.from_mapping(_mapping(item, f"materials[{index}]"), f"materials[{index}]") for index, item in enumerate(materials_raw)),
            inventory=tuple(InventoryItemSpec.from_mapping(_mapping(item, f"inventory[{index}]"), f"inventory[{index}]") for index, item in enumerate(inventory_raw)),
            machines=tuple(MachineSpec.from_mapping(_mapping(item, f"machines[{index}]"), f"machines[{index}]") for index, item in enumerate(machines_raw)),
            probe_repeatability_um=_nat(raw["probe_repeatability_um"], "probe_repeatability_um"),
            disturbance_bound_um=_nat(raw["disturbance_bound_um"], "disturbance_bound_um"),
            baseline_capability_error_um=_nat(raw["baseline_capability_error_um"], "baseline_capability_error_um", positive=True),
            assembly_time_per_part_us=_nat(raw["assembly_time_per_part_us"], "assembly_time_per_part_us", positive=True),
            calibration_time_us=_nat(raw["calibration_time_us"], "calibration_time_us", positive=True),
            cell_power_w=_nat(raw["cell_power_w"], "cell_power_w", positive=True),
        )


@dataclass(frozen=True)
class MechanismProgram:
    schema_version: str
    program_id: str
    parent_world_hash: str
    parts: tuple[PartSpec, ...]
    assemblies: tuple[AssemblySpec, ...]
    operations: tuple[dict[str, Any], ...]

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "MechanismProgram":
        _keys(raw, {"schema_version", "program_id", "parent_world_hash", "parts", "assemblies", "operations"}, "program")
        if raw["schema_version"] != SCHEMA_VERSION:
            raise IRValidationError("unsupported program schema version")
        parts_raw, assemblies_raw, operations_raw = raw["parts"], raw["assemblies"], raw["operations"]
        if not isinstance(parts_raw, list) or not parts_raw:
            raise IRValidationError("program.parts must be non-empty")
        if not isinstance(assemblies_raw, list) or not assemblies_raw:
            raise IRValidationError("program.assemblies must be non-empty")
        if not isinstance(operations_raw, list) or not operations_raw:
            raise IRValidationError("program.operations must be non-empty")
        operations = tuple(dict(_mapping(item, f"operations[{index}]")) for index, item in enumerate(operations_raw))
        return cls(
            schema_version=SCHEMA_VERSION,
            program_id=_text(raw["program_id"], "program.program_id"),
            parent_world_hash=_text(raw["parent_world_hash"], "program.parent_world_hash"),
            parts=tuple(PartSpec.from_mapping(_mapping(item, f"parts[{index}]"), f"parts[{index}]") for index, item in enumerate(parts_raw)),
            assemblies=tuple(AssemblySpec.from_mapping(_mapping(item, f"assemblies[{index}]"), f"assemblies[{index}]") for index, item in enumerate(assemblies_raw)),
            operations=operations,
        )


def _shape_to_dict(part: PartSpec) -> dict[str, object]:
    return {
        "part_id": part.part_id,
        "label": part.label,
        "material_id": part.material_id,
        "source_item_id": part.source_item_id,
        "geometry": part.geometry.to_dict(),
        "datums": [
            {"datum_id": datum.datum_id, "pose": datum.pose.to_dict()}
            for datum in part.datums
        ],
    }


def program_to_dict(program: MechanismProgram) -> dict[str, object]:
    return {
        "schema_version": program.schema_version,
        "program_id": program.program_id,
        "parent_world_hash": program.parent_world_hash,
        "parts": [_shape_to_dict(part) for part in program.parts],
        "assemblies": [
            {
                "assembly_id": assembly.assembly_id,
                "label": assembly.label,
                "root_occurrence": assembly.root_occurrence,
                "occurrences": [
                    {
                        "occurrence_id": occurrence.occurrence_id,
                        "part_id": occurrence.part_id,
                        "pose": occurrence.pose.to_dict(),
                    }
                    for occurrence in assembly.occurrences
                ],
                "mates": [asdict(mate) for mate in assembly.mates],
            }
            for assembly in program.assemblies
        ],
        "operations": [dict(operation) for operation in program.operations],
    }


def world_to_dict(world: WorldSpec) -> dict[str, object]:
    return {
        "schema_version": world.schema_version,
        "world_id": world.world_id,
        "materials": [asdict(material) for material in world.materials],
        "inventory": [
            {
                "item_id": item.item_id,
                "kind": item.kind,
                "role": item.role,
                "material_id": item.material_id,
                "quantity": item.quantity,
                "mass_mg": item.mass_mg,
                "envelope_um": item.envelope_um.to_list(),
            }
            for item in world.inventory
        ],
        "machines": [
            {
                "machine_id": machine.machine_id,
                "envelope_um": machine.envelope_um.to_list(),
                "min_feature_um": machine.min_feature_um,
                "removal_rate_um3_per_us": machine.removal_rate_um3_per_us,
                "setup_time_us": machine.setup_time_us,
                "power_w": machine.power_w,
                "absolute_setup_error_um": machine.absolute_setup_error_um,
                "relative_repeatability_um": machine.relative_repeatability_um,
                "operations": list(machine.operations),
            }
            for machine in world.machines
        ],
        "probe_repeatability_um": world.probe_repeatability_um,
        "disturbance_bound_um": world.disturbance_bound_um,
        "baseline_capability_error_um": world.baseline_capability_error_um,
        "assembly_time_per_part_us": world.assembly_time_per_part_us,
        "calibration_time_us": world.calibration_time_us,
        "cell_power_w": world.cell_power_w,
    }
