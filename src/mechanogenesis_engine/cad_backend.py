from __future__ import annotations

from copy import copy
from typing import Any

from .errors import IRValidationError
from .ir import MechanismProgram, PartSpec, PoseQ, ShapeNode


def _mm(value_um: int) -> float:
    return value_um / 1000.0


def _location(pose: PoseQ) -> Any:
    from build123d import Location

    return Location(
        tuple(_mm(value) for value in pose.translation_um.to_list()),
        tuple(value / 1000.0 for value in pose.rotation_mdeg.to_list()),
    )


def _primitive(shape: ShapeNode, *, cutter_overshoot_um: int = 0) -> Any:
    from build123d import Align, Box, Cylinder

    if shape.kind == "box":
        assert shape.size_um is not None and shape.center_um is not None
        result = Box(
            _mm(shape.size_um.x),
            _mm(shape.size_um.y),
            _mm(shape.size_um.z),
            align=(Align.CENTER, Align.CENTER, Align.CENTER),
        )
        result = result.moved(
            _location(
                PoseQ(
                    shape.center_um,
                    type(shape.center_um)(0, 0, 0),
                )
            )
        )
    elif shape.kind == "cylinder":
        assert shape.radius_um is not None and shape.height_um is not None
        assert shape.center_um is not None
        rotation = {"x": (0, 90, 0), "y": (-90, 0, 0), "z": (0, 0, 0)}[
            shape.axis or "z"
        ]
        result = Cylinder(
            _mm(shape.radius_um),
            _mm(shape.height_um + cutter_overshoot_um),
            arc_size=360,
            align=(Align.CENTER, Align.CENTER, Align.CENTER),
            rotation=rotation,
        )
        result = result.moved(
            _location(
                PoseQ(
                    shape.center_um,
                    type(shape.center_um)(0, 0, 0),
                )
            )
        )
    else:
        raise IRValidationError("primitive compiler received a CSG node")
    result.label = shape.label
    return result


def compile_shape(shape: ShapeNode) -> Any:
    if shape.kind in {"box", "cylinder"}:
        return _primitive(shape)
    if shape.kind == "difference":
        base = compile_shape(shape.children[0])
        for cutter in shape.children[1:]:
            tool = (
                _primitive(cutter, cutter_overshoot_um=2_000)
                if cutter.kind in {"box", "cylinder"}
                else compile_shape(cutter)
            )
            base = base - tool
        base.label = shape.label
        return base
    if shape.kind == "union":
        result = compile_shape(shape.children[0])
        for child in shape.children[1:]:
            result = result + compile_shape(child)
        result.label = shape.label
        return result
    raise IRValidationError(f"unsupported CAD shape kind {shape.kind!r}")


def compile_part(part: PartSpec) -> Any:
    shape = compile_shape(part.geometry)
    shape.label = part.label
    return shape


def _part_color(part: PartSpec) -> Any:
    from build123d import Color

    return Color("LIGHTGRAY" if "aluminum" in part.material_id else "STEELBLUE")


def compile_assembly(program: MechanismProgram, assembly_id: str) -> Any:
    from cadpy.assembly import AssemblyHelper

    assemblies = {item.assembly_id: item for item in program.assemblies}
    parts = {item.part_id: item for item in program.parts}
    assembly = assemblies.get(assembly_id)
    if assembly is None:
        raise IRValidationError(f"unknown assembly {assembly_id!r}")
    occurrences = {item.occurrence_id: item for item in assembly.occurrences}
    if assembly.root_occurrence not in occurrences:
        raise IRValidationError("assembly root occurrence is missing")

    helper = AssemblyHelper(assembly.label)
    placed: dict[str, Any] = {}
    root = occurrences[assembly.root_occurrence]
    root_shape = compile_part(parts[root.part_id]).moved(_location(root.pose))
    placed[root.occurrence_id] = helper.add(
        root_shape, root.occurrence_id, color=_part_color(parts[root.part_id])
    )

    pending = list(assembly.mates)
    while pending:
        progressed = False
        for mate in list(pending):
            if mate.fixed_occurrence not in placed:
                continue
            moving_occurrence = occurrences[mate.moving_occurrence]
            moving_shape = copy(compile_part(parts[moving_occurrence.part_id]))
            moving_shape = helper.add(
                moving_shape,
                moving_occurrence.occurrence_id,
                color=_part_color(parts[moving_occurrence.part_id]),
            )
            fixed_occurrence = occurrences[mate.fixed_occurrence]
            fixed_datum = parts[fixed_occurrence.part_id].datum(mate.fixed_datum)
            moving_datum = parts[moving_occurrence.part_id].datum(mate.moving_datum)
            fixed_target = helper.rigid_frame(
                placed[mate.fixed_occurrence],
                f"{mate.mate_id}_fixed",
                _location(fixed_datum.pose),
            )
            moving_target = helper.rigid_frame(
                moving_shape,
                f"{mate.mate_id}_moving",
                _location(moving_datum.pose),
            )
            helper.connect(
                fixed_target,
                moving_target,
                relation="rigid",
                label=mate.mate_id,
            )
            placed[mate.moving_occurrence] = moving_shape
            pending.remove(mate)
            progressed = True
        if not progressed:
            raise IRValidationError("assembly mate graph is disconnected or cyclic")
    if set(placed) != set(occurrences):
        raise IRValidationError("not every occurrence was emitted by the CAD backend")
    return helper.build()
