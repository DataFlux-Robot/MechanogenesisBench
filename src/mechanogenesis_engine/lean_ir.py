"""Deterministic codecs for Lean-owned canonical IR and refinement certificates.

The codec is still part of the current trusted computing base. Evaluators
independently regenerate these objects from the submitted program and execution;
Lean owns their acceptance predicates.
"""

from __future__ import annotations

from typing import Any

from mechanogenesis_bench.canonical import digest

from .errors import ExecutionError
from .interpreter import ExecutionResult
from .ir import MechanismProgram, ShapeNode, WorldSpec, program_to_dict, world_to_dict


CANONICAL_IR_SCHEMA_VERSION = "0.1"
CANONICAL_IR_SEMANTICS_ID = "Mechanogenesis.CanonicalIR.v0.1"
METROLOGY_SCHEMA_VERSION = "0.1"
METROLOGY_SEMANTICS_ID = "Mechanogenesis.MetrologyRefinement.v0.1"
REQUIRED_METROLOGY_ASSUMPTIONS = (
    "geometry_role_binding",
    "additive_error_budget",
    "calibration_parameter_fidelity",
)


def _shape_records(
    part_id: str,
    shape: ShapeNode,
    *,
    node_id: str = "n0",
    parent_node_id: str = "",
    child_index: int = 0,
    depth: int = 0,
) -> list[dict[str, object]]:
    center = shape.center_um
    size = shape.size_um
    record: dict[str, object] = {
        "partId": part_id,
        "nodeId": node_id,
        "parentNodeId": parent_node_id,
        "childIndex": child_index,
        "depth": depth,
        "label": shape.label,
        "kind": shape.kind,
        "centerXUm": center.x if center is not None else 0,
        "centerYUm": center.y if center is not None else 0,
        "centerZUm": center.z if center is not None else 0,
        "sizeXUm": size.x if size is not None else 0,
        "sizeYUm": size.y if size is not None else 0,
        "sizeZUm": size.z if size is not None else 0,
        "radiusUm": shape.radius_um or 0,
        "heightUm": shape.height_um or 0,
        "axis": shape.axis or "",
    }
    records = [record]
    for index, child in enumerate(shape.children):
        records.extend(
            _shape_records(
                part_id,
                child,
                node_id=f"{node_id}.{index}",
                parent_node_id=node_id,
                child_index=index,
                depth=depth + 1,
            )
        )
    return records


def _canonical_operation(operation: dict[str, Any], index: int) -> dict[str, object]:
    return {
        "index": index,
        "kind": operation["op"],
        "operationHash": digest(operation),
        "processKind": operation.get("process", ""),
        "processCapabilityId": operation.get("process_capability_id", ""),
        "machineId": operation.get("machine_id", ""),
        "stockItemId": operation.get("stock_item_id", ""),
        "itemId": operation.get("item_id", ""),
        "partId": operation.get("part_id", ""),
        "assemblyId": operation.get("assembly_id", ""),
        "capabilityId": operation.get("capability_id", ""),
        "locatorOccurrences": list(operation.get("locator_occurrences", [])),
        "referenceOccurrence": operation.get("reference_occurrence", ""),
        "workpieceSpanUm": operation.get("workpiece_span_um", 0),
        "sourceCapabilityId": operation.get("source_capability_id", ""),
        "parentProcessCapabilityId": operation.get("parent_process_capability_id", ""),
        "childProcessCapabilityId": operation.get("child_process_capability_id", ""),
        "transferErrorUm": operation.get("transfer_error_um", 0),
    }


def canonical_program_manifest(
    world: WorldSpec, program: MechanismProgram
) -> dict[str, object]:
    """Lower the Python surface object into the Lean canonical manifest ABI."""
    program_mapping = program_to_dict(program)
    shapes = [
        record
        for part in program.parts
        for record in _shape_records(part.part_id, part.geometry)
    ]
    return {
        "schemaVersion": CANONICAL_IR_SCHEMA_VERSION,
        "semanticsId": CANONICAL_IR_SEMANTICS_ID,
        "sourceProgramHash": digest(program_mapping),
        "worldSpecHash": digest(world_to_dict(world)),
        "parentWorldHash": program.parent_world_hash,
        "materials": [
            {"materialId": material.material_id} for material in world.materials
        ],
        "inventory": [
            {
                "itemId": item.item_id,
                "kind": item.kind,
                "materialId": item.material_id,
            }
            for item in world.inventory
        ],
        "machines": [
            {
                "machineId": machine.machine_id,
                "operationKinds": list(machine.operations),
            }
            for machine in world.machines
        ],
        "parts": [
            {
                "partId": part.part_id,
                "materialId": part.material_id,
                "sourceItemId": part.source_item_id or "",
                "rootShapeId": "n0",
                "datumIds": [datum.datum_id for datum in part.datums],
            }
            for part in program.parts
        ],
        "shapes": shapes,
        "assemblies": [
            {
                "assemblyId": assembly.assembly_id,
                "rootOccurrence": assembly.root_occurrence,
            }
            for assembly in program.assemblies
        ],
        "occurrences": [
            {
                "assemblyId": assembly.assembly_id,
                "occurrenceId": occurrence.occurrence_id,
                "partId": occurrence.part_id,
            }
            for assembly in program.assemblies
            for occurrence in assembly.occurrences
        ],
        "mates": [
            {
                "assemblyId": assembly.assembly_id,
                "mateId": mate.mate_id,
                "fixedOccurrence": mate.fixed_occurrence,
                "fixedDatum": mate.fixed_datum,
                "movingOccurrence": mate.moving_occurrence,
                "movingDatum": mate.moving_datum,
                "toleranceUm": mate.tolerance_um,
            }
            for assembly in program.assemblies
            for mate in assembly.mates
        ],
        "operations": [
            _canonical_operation(operation, index)
            for index, operation in enumerate(program.operations)
        ],
    }


def metrology_refinement_certificates(
    world: WorldSpec,
    program: MechanismProgram,
    execution: ExecutionResult,
) -> tuple[dict[str, object], ...]:
    """Extract proof-checkable metrology formula receipts from one execution."""
    program_hash = digest(program_to_dict(program))
    certificates: list[dict[str, object]] = []
    capabilities = execution.final_state.get("capabilities")
    if not isinstance(capabilities, dict):
        raise ExecutionError("execution has no canonical capability state")
    if len(execution.receipts) != len(program.operations):
        raise ExecutionError("operation and receipt counts disagree")
    for index, operation in enumerate(program.operations):
        if operation.get("op") != "calibrate":
            continue
        receipt = execution.receipts[index]
        capability_id = operation.get("capability_id")
        capability = capabilities.get(capability_id)
        if not isinstance(capability_id, str) or not isinstance(capability, dict):
            raise ExecutionError("calibration capability is absent")
        certificates.append(
            {
                "schemaVersion": METROLOGY_SCHEMA_VERSION,
                "semanticsId": METROLOGY_SEMANTICS_ID,
                "programHash": program_hash,
                "operationIndex": index,
                "operationHash": receipt.operation_hash,
                "parentWorldHash": receipt.parent_world_hash,
                "childWorldHash": receipt.child_world_hash,
                "assemblyId": operation["assembly_id"],
                "capabilityId": capability_id,
                "locatorSpacingUm": capability["locator_spacing_um"],
                "radialClearanceUm": capability["radial_clearance_um"],
                "referenceClearanceUm": capability["reference_clearance_um"],
                "workpieceSpanUm": operation["workpiece_span_um"],
                "manufacturingRepeatabilityUm": capability[
                    "manufacturing_repeatability_um"
                ],
                "probeRepeatabilityUm": world.probe_repeatability_um,
                "disturbanceBoundUm": world.disturbance_bound_um,
                "sourceProcessErrorUm": capability["source_process_error_um"],
                "angularTipErrorUm": capability["angular_tip_error_um"],
                "worstCaseErrorUm": capability["worst_case_error_um"],
                "absoluteFrameErrorUm": capability["absolute_frame_error_um"],
                "evidenceTier": "conformance",
                "assumptionIds": list(REQUIRED_METROLOGY_ASSUMPTIONS),
            }
        )
    if not certificates:
        raise ExecutionError("program emits no metrology refinement certificate")
    return tuple(certificates)
