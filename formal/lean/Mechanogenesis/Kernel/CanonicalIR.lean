import Mechanogenesis.Kernel.Digest
import Lean.Data.Json.FromToJson

namespace Mechanogenesis

def canonicalIrSemanticsId : String :=
  "Mechanogenesis.CanonicalIR.v0.1"

def uniqueStringsB (values : List String) : Bool :=
  values.eraseDups.length == values.length

structure CanonicalMaterial where
  materialId : String
  deriving DecidableEq, Repr, Lean.FromJson, Lean.ToJson

structure CanonicalInventoryItem where
  itemId : String
  kind : String
  materialId : String
  deriving DecidableEq, Repr, Lean.FromJson, Lean.ToJson

structure CanonicalMachine where
  machineId : String
  operationKinds : List String
  deriving DecidableEq, Repr, Lean.FromJson, Lean.ToJson

/-- A flattened shape tree keeps the JSON ABI first-order while retaining
parent/child topology. Unused primitive fields must be zero/empty. -/
structure CanonicalShapeNode where
  partId : String
  nodeId : String
  parentNodeId : String
  childIndex : Nat
  depth : Nat
  label : String
  kind : String
  centerXUm : Int
  centerYUm : Int
  centerZUm : Int
  sizeXUm : Nat
  sizeYUm : Nat
  sizeZUm : Nat
  radiusUm : Nat
  heightUm : Nat
  axis : String
  deriving DecidableEq, Repr, Lean.FromJson, Lean.ToJson

structure CanonicalPart where
  partId : String
  materialId : String
  sourceItemId : String
  rootShapeId : String
  datumIds : List String
  deriving DecidableEq, Repr, Lean.FromJson, Lean.ToJson

structure CanonicalAssembly where
  assemblyId : String
  rootOccurrence : String
  deriving DecidableEq, Repr, Lean.FromJson, Lean.ToJson

structure CanonicalOccurrence where
  assemblyId : String
  occurrenceId : String
  partId : String
  deriving DecidableEq, Repr, Lean.FromJson, Lean.ToJson

structure CanonicalMate where
  assemblyId : String
  mateId : String
  fixedOccurrence : String
  fixedDatum : String
  movingOccurrence : String
  movingDatum : String
  toleranceUm : Nat
  deriving DecidableEq, Repr, Lean.FromJson, Lean.ToJson

/-- All operation fields are present in the canonical ABI. Fields outside the
selected operation kind use their zero value, giving one unambiguous encoding. -/
structure CanonicalOperation where
  index : Nat
  kind : String
  operationHash : Digest
  processKind : String
  processCapabilityId : String
  machineId : String
  stockItemId : String
  itemId : String
  partId : String
  assemblyId : String
  capabilityId : String
  locatorOccurrences : List String
  referenceOccurrence : String
  workpieceSpanUm : Nat
  sourceCapabilityId : String
  parentProcessCapabilityId : String
  childProcessCapabilityId : String
  transferErrorUm : Nat
  deriving DecidableEq, Repr, Lean.FromJson, Lean.ToJson

structure CanonicalProgramManifest where
  schemaVersion : String
  semanticsId : String
  sourceProgramHash : Digest
  worldSpecHash : Digest
  parentWorldHash : Digest
  materials : List CanonicalMaterial
  inventory : List CanonicalInventoryItem
  machines : List CanonicalMachine
  parts : List CanonicalPart
  shapes : List CanonicalShapeNode
  assemblies : List CanonicalAssembly
  occurrences : List CanonicalOccurrence
  mates : List CanonicalMate
  operations : List CanonicalOperation
  deriving DecidableEq, Repr, Lean.FromJson, Lean.ToJson

def materialExistsB (manifest : CanonicalProgramManifest) (materialId : String) : Bool :=
  manifest.materials.any (fun material => material.materialId == materialId)

def inventoryExistsB (manifest : CanonicalProgramManifest) (itemId : String) : Bool :=
  manifest.inventory.any (fun item => item.itemId == itemId)

def inventoryKindB
    (manifest : CanonicalProgramManifest) (itemId kind : String) : Bool :=
  manifest.inventory.any (fun item => item.itemId == itemId && item.kind == kind)

def inventoryMaterialB
    (manifest : CanonicalProgramManifest)
    (itemId materialId : String) : Bool :=
  manifest.inventory.any (fun item =>
    item.itemId == itemId && item.materialId == materialId)

def machineExistsB (manifest : CanonicalProgramManifest) (machineId : String) : Bool :=
  manifest.machines.any (fun machine => machine.machineId == machineId)

def machineSupportsB
    (manifest : CanonicalProgramManifest) (machineId operationKind : String) : Bool :=
  manifest.machines.any (fun machine =>
    machine.machineId == machineId && machine.operationKinds.contains operationKind)

def partExistsB (manifest : CanonicalProgramManifest) (partId : String) : Bool :=
  manifest.parts.any (fun part => part.partId == partId)

def assemblyExistsB (manifest : CanonicalProgramManifest) (assemblyId : String) : Bool :=
  manifest.assemblies.any (fun assembly => assembly.assemblyId == assemblyId)

def occurrenceExistsB
    (manifest : CanonicalProgramManifest)
    (assemblyId occurrenceId : String) : Bool :=
  manifest.occurrences.any (fun occurrence =>
    occurrence.assemblyId == assemblyId && occurrence.occurrenceId == occurrenceId)

def shapeExistsB
    (manifest : CanonicalProgramManifest) (partId nodeId : String) : Bool :=
  manifest.shapes.any (fun node => node.partId == partId && node.nodeId == nodeId)

def shapeChildren
    (manifest : CanonicalProgramManifest) (node : CanonicalShapeNode) : List CanonicalShapeNode :=
  manifest.shapes.filter (fun child =>
    child.partId == node.partId && child.parentNodeId == node.nodeId)

def shapeChildrenCanonicallyIndexedB
    (manifest : CanonicalProgramManifest) (node : CanonicalShapeNode) : Bool :=
  let children := shapeChildren manifest node
  children.map (fun child => child.childIndex) == List.range children.length

def assemblyOccurrences
    (manifest : CanonicalProgramManifest) (assemblyId : String) : List CanonicalOccurrence :=
  manifest.occurrences.filter (fun occurrence => occurrence.assemblyId == assemblyId)

def assemblyMates
    (manifest : CanonicalProgramManifest) (assemblyId : String) : List CanonicalMate :=
  manifest.mates.filter (fun mate => mate.assemblyId == assemblyId)

def occurrenceDatumExistsB
    (manifest : CanonicalProgramManifest)
    (assemblyId occurrenceId datumId : String) : Bool :=
  manifest.occurrences.any (fun occurrence =>
    occurrence.assemblyId == assemblyId && occurrence.occurrenceId == occurrenceId &&
    manifest.parts.any (fun part =>
      part.partId == occurrence.partId && part.datumIds.contains datumId))

def canonicalShapeValidB
    (manifest : CanonicalProgramManifest) (node : CanonicalShapeNode) : Bool :=
  node.partId != "" && node.nodeId != "" && node.label != "" &&
  partExistsB manifest node.partId &&
  (if node.parentNodeId == "" then
    node.childIndex == 0 && node.depth == 0 && manifest.parts.any (fun part =>
      part.partId == node.partId && part.rootShapeId == node.nodeId)
  else
    node.depth > 0 && manifest.shapes.any (fun parent =>
      parent.partId == node.partId && parent.nodeId == node.parentNodeId &&
      node.depth == parent.depth + 1)) &&
  match node.kind with
  | "box" =>
      node.sizeXUm > 0 && node.sizeYUm > 0 && node.sizeZUm > 0 &&
      node.radiusUm == 0 && node.heightUm == 0 && node.axis == "" &&
      (shapeChildren manifest node).isEmpty
  | "cylinder" =>
      node.radiusUm > 0 && node.heightUm > 0 &&
      ["x", "y", "z"].contains node.axis &&
      node.sizeXUm == 0 && node.sizeYUm == 0 && node.sizeZUm == 0 &&
      (shapeChildren manifest node).isEmpty
  | "difference" =>
      node.sizeXUm == 0 && node.sizeYUm == 0 && node.sizeZUm == 0 &&
      node.radiusUm == 0 && node.heightUm == 0 && node.axis == "" &&
      (shapeChildren manifest node).length ≥ 2 &&
      shapeChildrenCanonicallyIndexedB manifest node
  | "union" =>
      node.sizeXUm == 0 && node.sizeYUm == 0 && node.sizeZUm == 0 &&
      node.radiusUm == 0 && node.heightUm == 0 && node.axis == "" &&
      (shapeChildren manifest node).length ≥ 2 &&
      shapeChildrenCanonicallyIndexedB manifest node
  | _ => false

def canonicalPartValidB
    (manifest : CanonicalProgramManifest) (part : CanonicalPart) : Bool :=
  part.partId != "" && part.materialId != "" && part.rootShapeId != "" &&
  materialExistsB manifest part.materialId &&
  (part.sourceItemId == "" ||
    inventoryMaterialB manifest part.sourceItemId part.materialId) &&
  shapeExistsB manifest part.partId part.rootShapeId &&
  uniqueStringsB part.datumIds && part.datumIds.all (fun datumId => datumId != "")

def partUsesSourceItemB
    (manifest : CanonicalProgramManifest) (partId itemId : String) : Bool :=
  manifest.parts.any (fun part =>
    part.partId == partId && part.sourceItemId == itemId)

def partMachinedFromStockB
    (manifest : CanonicalProgramManifest) (partId stockItemId : String) : Bool :=
  manifest.parts.any (fun part =>
    part.partId == partId && part.sourceItemId == "" &&
    inventoryMaterialB manifest stockItemId part.materialId)

def canonicalOccurrenceValidB
    (manifest : CanonicalProgramManifest) (occurrence : CanonicalOccurrence) : Bool :=
  occurrence.assemblyId != "" && occurrence.occurrenceId != "" &&
  assemblyExistsB manifest occurrence.assemblyId &&
  partExistsB manifest occurrence.partId

def canonicalAssemblyValidB
    (manifest : CanonicalProgramManifest) (assembly : CanonicalAssembly) : Bool :=
  assembly.assemblyId != "" && assembly.rootOccurrence != "" &&
  occurrenceExistsB manifest assembly.assemblyId assembly.rootOccurrence &&
  (assemblyOccurrences manifest assembly.assemblyId).all (fun occurrence =>
    if occurrence.occurrenceId == assembly.rootOccurrence then
      !(assemblyMates manifest assembly.assemblyId).any (fun mate =>
        mate.movingOccurrence == occurrence.occurrenceId)
    else
      (assemblyMates manifest assembly.assemblyId).any (fun mate =>
        mate.movingOccurrence == occurrence.occurrenceId)) &&
  uniqueStringsB ((assemblyMates manifest assembly.assemblyId).map (fun mate =>
    mate.movingOccurrence))

def canonicalMateValidB
    (manifest : CanonicalProgramManifest) (mate : CanonicalMate) : Bool :=
  mate.assemblyId != "" && mate.mateId != "" &&
  occurrenceExistsB manifest mate.assemblyId mate.fixedOccurrence &&
  occurrenceExistsB manifest mate.assemblyId mate.movingOccurrence &&
  mate.fixedOccurrence != mate.movingOccurrence &&
  occurrenceDatumExistsB manifest mate.assemblyId
    mate.fixedOccurrence mate.fixedDatum &&
  occurrenceDatumExistsB manifest mate.assemblyId
    mate.movingOccurrence mate.movingDatum

def knownCanonicalOperationKinds : List String := [
  "machine_part", "consume_component", "assemble", "calibrate", "qualify_process"
]

def CanonicalOperationKindKnown (operation : CanonicalOperation) : Prop :=
  knownCanonicalOperationKinds.contains operation.kind = true

def canonicalOperationValidB
    (manifest : CanonicalProgramManifest) (operation : CanonicalOperation) : Bool :=
  isSha256DigestB operation.operationHash &&
  knownCanonicalOperationKinds.contains operation.kind &&
  match operation.kind with
  | "machine_part" =>
      operation.processKind != "" &&
      operation.processCapabilityId != "" &&
      machineSupportsB manifest operation.machineId operation.processKind &&
      inventoryKindB manifest operation.stockItemId "stock" &&
      partExistsB manifest operation.partId &&
      partMachinedFromStockB manifest operation.partId operation.stockItemId &&
      operation.itemId == "" && operation.assemblyId == "" &&
      operation.capabilityId == "" && operation.locatorOccurrences.isEmpty &&
      operation.referenceOccurrence == "" && operation.workpieceSpanUm == 0 &&
      operation.sourceCapabilityId == "" &&
      operation.parentProcessCapabilityId == "" &&
      operation.childProcessCapabilityId == "" && operation.transferErrorUm == 0
  | "consume_component" =>
      inventoryKindB manifest operation.itemId "component" &&
      partExistsB manifest operation.partId &&
      partUsesSourceItemB manifest operation.partId operation.itemId &&
      operation.processKind == "" && operation.processCapabilityId == "" &&
      operation.machineId == "" && operation.stockItemId == "" &&
      operation.assemblyId == "" && operation.capabilityId == "" &&
      operation.locatorOccurrences.isEmpty && operation.referenceOccurrence == "" &&
      operation.workpieceSpanUm == 0 && operation.sourceCapabilityId == "" &&
      operation.parentProcessCapabilityId == "" &&
      operation.childProcessCapabilityId == "" && operation.transferErrorUm == 0
  | "assemble" =>
      assemblyExistsB manifest operation.assemblyId &&
      operation.processKind == "" && operation.processCapabilityId == "" &&
      operation.machineId == "" && operation.stockItemId == "" &&
      operation.itemId == "" && operation.partId == "" &&
      operation.capabilityId == "" && operation.locatorOccurrences.isEmpty &&
      operation.referenceOccurrence == "" && operation.workpieceSpanUm == 0 &&
      operation.sourceCapabilityId == "" &&
      operation.parentProcessCapabilityId == "" &&
      operation.childProcessCapabilityId == "" && operation.transferErrorUm == 0
  | "calibrate" =>
      assemblyExistsB manifest operation.assemblyId && operation.capabilityId != "" &&
      operation.locatorOccurrences.length == 2 &&
      uniqueStringsB operation.locatorOccurrences &&
      operation.locatorOccurrences.all (fun occurrenceId =>
        occurrenceExistsB manifest operation.assemblyId occurrenceId) &&
      occurrenceExistsB manifest operation.assemblyId operation.referenceOccurrence &&
      !operation.locatorOccurrences.contains operation.referenceOccurrence &&
      operation.workpieceSpanUm > 0 && operation.processKind == "" &&
      operation.processCapabilityId == "" && operation.machineId == "" &&
      operation.stockItemId == "" && operation.itemId == "" &&
      operation.partId == "" && operation.sourceCapabilityId == "" &&
      operation.parentProcessCapabilityId == "" &&
      operation.childProcessCapabilityId == "" && operation.transferErrorUm == 0
  | "qualify_process" =>
      machineExistsB manifest operation.machineId &&
      assemblyExistsB manifest operation.assemblyId &&
      operation.sourceCapabilityId != "" &&
      operation.parentProcessCapabilityId != "" &&
      operation.childProcessCapabilityId != "" &&
      operation.transferErrorUm > 0 && operation.processKind == "" &&
      operation.processCapabilityId == "" && operation.stockItemId == "" &&
      operation.itemId == "" && operation.partId == "" &&
      operation.capabilityId == "" && operation.locatorOccurrences.isEmpty &&
      operation.referenceOccurrence == "" && operation.workpieceSpanUm == 0
  | _ => false

def canonicalOperationsIndexedFromB : Nat → List CanonicalOperation → Bool
  | _, [] => true
  | expected, operation :: rest =>
      operation.index == expected && canonicalOperationsIndexedFromB (expected + 1) rest

def allCanonicalOperationKindsKnownB (operations : List CanonicalOperation) : Bool :=
  operations.all (fun operation => knownCanonicalOperationKinds.contains operation.kind)

def canonicalProgramCoreB (manifest : CanonicalProgramManifest) : Bool :=
  manifest.schemaVersion == "0.1" &&
  manifest.semanticsId == canonicalIrSemanticsId &&
  isSha256DigestB manifest.sourceProgramHash &&
  isSha256DigestB manifest.worldSpecHash &&
  isSha256DigestB manifest.parentWorldHash &&
  manifest.materials.isEmpty == false && manifest.inventory.isEmpty == false &&
  manifest.machines.isEmpty == false && manifest.parts.isEmpty == false &&
  manifest.shapes.isEmpty == false && manifest.assemblies.isEmpty == false &&
  manifest.occurrences.isEmpty == false &&
  uniqueStringsB (manifest.materials.map (fun material => material.materialId)) &&
  uniqueStringsB (manifest.inventory.map (fun item => item.itemId)) &&
  uniqueStringsB (manifest.machines.map (fun machine => machine.machineId)) &&
  uniqueStringsB (manifest.parts.map (fun part => part.partId)) &&
  uniqueStringsB (manifest.shapes.map (fun shape => shape.partId ++ ":" ++ shape.nodeId)) &&
  uniqueStringsB (manifest.shapes.map (fun shape =>
    shape.partId ++ ":" ++ shape.parentNodeId ++ ":" ++ toString shape.childIndex)) &&
  uniqueStringsB (manifest.assemblies.map (fun assembly => assembly.assemblyId)) &&
  uniqueStringsB (manifest.occurrences.map (fun occurrence =>
    occurrence.assemblyId ++ ":" ++ occurrence.occurrenceId)) &&
  uniqueStringsB (manifest.mates.map (fun mate => mate.assemblyId ++ ":" ++ mate.mateId)) &&
  manifest.materials.all (fun material => material.materialId != "") &&
  manifest.inventory.all (fun item =>
    item.itemId != "" && ["stock", "component"].contains item.kind &&
    materialExistsB manifest item.materialId) &&
  manifest.machines.all (fun machine =>
    machine.machineId != "" && machine.operationKinds.isEmpty == false &&
    uniqueStringsB machine.operationKinds) &&
  manifest.parts.all (canonicalPartValidB manifest) &&
  manifest.shapes.all (canonicalShapeValidB manifest) &&
  manifest.occurrences.all (canonicalOccurrenceValidB manifest) &&
  manifest.assemblies.all (canonicalAssemblyValidB manifest) &&
  manifest.mates.all (canonicalMateValidB manifest) &&
  canonicalOperationsIndexedFromB 0 manifest.operations &&
  uniqueStringsB ((manifest.operations.filter (fun operation =>
    operation.kind == "calibrate")).map (fun operation => operation.capabilityId)) &&
  manifest.operations.all (canonicalOperationValidB manifest)

def validCanonicalProgramB (manifest : CanonicalProgramManifest) : Bool :=
  (manifest.operations.isEmpty == false &&
    allCanonicalOperationKindsKnownB manifest.operations) &&
  canonicalProgramCoreB manifest

def ValidCanonicalProgram (manifest : CanonicalProgramManifest) : Prop :=
  validCanonicalProgramB manifest = true

def checkCanonicalProgram (manifest : CanonicalProgramManifest) : Bool :=
  validCanonicalProgramB manifest

theorem canonical_ir_checker_sound
    (manifest : CanonicalProgramManifest)
    (accepted : checkCanonicalProgram manifest = true) :
    ValidCanonicalProgram manifest := by
  exact accepted

theorem accepted_canonical_program_has_operations
    (manifest : CanonicalProgramManifest)
    (accepted : ValidCanonicalProgram manifest) :
    manifest.operations ≠ [] := by
  simp [ValidCanonicalProgram, validCanonicalProgramB] at accepted
  exact accepted.1.1

theorem accepted_canonical_program_closes_operation_language
    (manifest : CanonicalProgramManifest)
    (accepted : ValidCanonicalProgram manifest) :
    manifest.operations.all (fun operation =>
      knownCanonicalOperationKinds.contains operation.kind) = true := by
  simp [ValidCanonicalProgram, validCanonicalProgramB,
    allCanonicalOperationKindsKnownB] at accepted
  simpa using accepted.1.2

end Mechanogenesis
