import Mechanogenesis.Kernel.MetrologyRefinement
import Lean.Elab.Tactic.Omega

namespace Mechanogenesis

def comparatorSemanticsId : String :=
  "Mechanogenesis.ComparatorRefinement.v0.1"

def requiredComparatorAssumptions : List String := [
  "geometry_role_binding",
  "additive_error_budget",
  "calibration_parameter_fidelity",
  "symmetric_common_mode_cancellation_bound"
]

structure ComparatorRefinementCertificate where
  schemaVersion : String
  semanticsId : String
  programHash : Digest
  operationIndex : Nat
  operationHash : Digest
  parentWorldHash : Digest
  childWorldHash : Digest
  assemblyId : String
  capabilityId : String
  topology : String
  referenceCount : Nat
  referenceBaselineUm : Nat
  supportClearanceUm : Nat
  probeClearanceUm : Nat
  measurementSpanUm : Nat
  manufacturingRepeatabilityUm : Nat
  probeRepeatabilityUm : Nat
  disturbanceBoundUm : Nat
  sourceProcessErrorUm : Nat
  geometryErrorUm : Nat
  matchingErrorUm : Nat
  commonModeResidualUm : Nat
  worstCaseErrorUm : Nat
  absoluteFrameErrorUm : Nat
  evidenceTier : String
  assumptionIds : List String
  deriving DecidableEq, Repr, Lean.FromJson, Lean.ToJson

def comparatorTopologyValidB
    (certificate : ComparatorRefinementCertificate) : Bool :=
  (certificate.topology == "direct_reference" &&
    certificate.referenceCount == 1) ||
  (certificate.topology == "differential_bridge" &&
    certificate.referenceCount == 2)

def computedComparatorGeometryError
    (certificate : ComparatorRefinementCertificate) : Nat :=
  if certificate.topology == "direct_reference" then
    ceilDivNat
      ((certificate.supportClearanceUm + certificate.probeClearanceUm) *
        certificate.measurementSpanUm)
      certificate.referenceBaselineUm
  else if certificate.topology == "differential_bridge" then
    ceilDivNat
      (2 * certificate.supportClearanceUm * certificate.measurementSpanUm)
      certificate.referenceBaselineUm
  else 0

def computedComparatorMatchingError
    (certificate : ComparatorRefinementCertificate) : Nat :=
  if certificate.topology == "direct_reference" then 0
  else if certificate.topology == "differential_bridge" then
    2 * certificate.supportClearanceUm +
      2 * certificate.manufacturingRepeatabilityUm
  else 0

def computedCommonModeResidual
    (certificate : ComparatorRefinementCertificate) : Nat :=
  if certificate.topology == "direct_reference" then
    certificate.disturbanceBoundUm
  else if certificate.topology == "differential_bridge" then
    ceilDivNat certificate.disturbanceBoundUm 4
  else 0

def computedComparatorWorstCase
    (certificate : ComparatorRefinementCertificate) : Nat :=
  certificate.supportClearanceUm +
  certificate.probeClearanceUm +
  certificate.geometryErrorUm +
  certificate.matchingErrorUm +
  certificate.manufacturingRepeatabilityUm +
  certificate.probeRepeatabilityUm +
  certificate.commonModeResidualUm

def ComparatorFormulaConditions
    (certificate : ComparatorRefinementCertificate) : Prop :=
  comparatorTopologyValidB certificate = true ∧
  0 < certificate.referenceBaselineUm ∧
  0 < certificate.measurementSpanUm ∧
  certificate.geometryErrorUm = computedComparatorGeometryError certificate ∧
  certificate.matchingErrorUm = computedComparatorMatchingError certificate ∧
  certificate.commonModeResidualUm = computedCommonModeResidual certificate ∧
  certificate.worstCaseErrorUm = computedComparatorWorstCase certificate ∧
  certificate.absoluteFrameErrorUm =
    certificate.sourceProcessErrorUm + certificate.worstCaseErrorUm ∧
  uniqueStringsB certificate.assumptionIds = true ∧
  requiredComparatorAssumptions.all (fun assumptionId =>
    certificate.assumptionIds.contains assumptionId) = true

def comparatorFormulaB
    (certificate : ComparatorRefinementCertificate) : Bool :=
  comparatorTopologyValidB certificate &&
  certificate.referenceBaselineUm > 0 &&
  certificate.measurementSpanUm > 0 &&
  certificate.geometryErrorUm == computedComparatorGeometryError certificate &&
  certificate.matchingErrorUm == computedComparatorMatchingError certificate &&
  certificate.commonModeResidualUm == computedCommonModeResidual certificate &&
  certificate.worstCaseErrorUm == computedComparatorWorstCase certificate &&
  certificate.absoluteFrameErrorUm ==
    certificate.sourceProcessErrorUm + certificate.worstCaseErrorUm &&
  uniqueStringsB certificate.assumptionIds &&
  requiredComparatorAssumptions.all (fun assumptionId =>
    certificate.assumptionIds.contains assumptionId)

def comparatorIdentityB
    (certificate : ComparatorRefinementCertificate) : Bool :=
  certificate.schemaVersion == "0.1" &&
  certificate.semanticsId == comparatorSemanticsId &&
  isSha256DigestB certificate.programHash &&
  isSha256DigestB certificate.operationHash &&
  isSha256DigestB certificate.parentWorldHash &&
  isSha256DigestB certificate.childWorldHash &&
  certificate.assemblyId != "" && certificate.capabilityId != "" &&
  certificate.evidenceTier == "conformance"

def validComparatorRefinementB
    (certificate : ComparatorRefinementCertificate) : Bool :=
  comparatorIdentityB certificate && comparatorFormulaB certificate

def ValidComparatorRefinement
    (certificate : ComparatorRefinementCertificate) : Prop :=
  validComparatorRefinementB certificate = true

def checkComparatorRefinement
    (certificate : ComparatorRefinementCertificate) : Bool :=
  validComparatorRefinementB certificate

theorem comparator_formula_checker_sound
    (certificate : ComparatorRefinementCertificate)
    (accepted : comparatorFormulaB certificate = true) :
    ComparatorFormulaConditions certificate := by
  simp [comparatorFormulaB] at accepted
  rcases accepted with
    ⟨⟨⟨⟨⟨⟨⟨⟨⟨topology, baseline⟩, span⟩, geometry⟩, matching⟩,
      residual⟩, worstCase⟩, absoluteFrame⟩, uniqueAssumptions⟩,
      requiredAssumptions⟩
  simp [ComparatorFormulaConditions]
  exact ⟨topology, baseline, span, geometry, matching, residual, worstCase,
    absoluteFrame, uniqueAssumptions, requiredAssumptions⟩

theorem comparator_refinement_checker_sound
    (certificate : ComparatorRefinementCertificate)
    (accepted : checkComparatorRefinement certificate = true) :
    ValidComparatorRefinement certificate ∧
    ComparatorFormulaConditions certificate := by
  have split : comparatorIdentityB certificate = true ∧
      comparatorFormulaB certificate = true := by
    simpa [checkComparatorRefinement, validComparatorRefinementB] using accepted
  exact ⟨accepted, comparator_formula_checker_sound certificate split.2⟩

theorem accepted_comparator_bound_contains_probe_repeatability
    (certificate : ComparatorRefinementCertificate)
    (accepted : checkComparatorRefinement certificate = true) :
    certificate.probeRepeatabilityUm ≤ certificate.worstCaseErrorUm := by
  have formulas := (comparator_refinement_checker_sound certificate accepted).2
  rw [formulas.2.2.2.2.2.2.1]
  unfold computedComparatorWorstCase
  omega

/-! The registered v0 workcell has a 100 um direct fixed cost and a 160 um
differential fixed cost.  These theorems expose the exact disturbance crossover
created by the physical formula: direct is strictly better through 79 um, the
two designs tie at 80 and 81 um because of integer ceiling, and differential is
strictly better from 82 um onward.  The constants are calibration facts for the
v0 task family, not universal laws of comparator design. -/

def registeredDirectComparatorError (disturbanceUm : Nat) : Nat :=
  100 + disturbanceUm

def registeredDifferentialComparatorError (disturbanceUm : Nat) : Nat :=
  160 + ceilDivNat disturbanceUm 4

theorem registered_direct_wins_before_crossover
    (disturbanceUm : Nat) (below : disturbanceUm ≤ 79) :
    registeredDirectComparatorError disturbanceUm <
      registeredDifferentialComparatorError disturbanceUm := by
  simp [registeredDirectComparatorError, registeredDifferentialComparatorError,
    ceilDivNat]
  omega

theorem registered_crossover_has_two_integer_ties :
    registeredDirectComparatorError 80 =
        registeredDifferentialComparatorError 80 ∧
      registeredDirectComparatorError 81 =
        registeredDifferentialComparatorError 81 := by
  decide

theorem registered_differential_wins_after_crossover
    (disturbanceUm : Nat) (above : 82 ≤ disturbanceUm) :
    registeredDifferentialComparatorError disturbanceUm <
      registeredDirectComparatorError disturbanceUm := by
  simp [registeredDirectComparatorError, registeredDifferentialComparatorError,
    ceilDivNat]
  omega

end Mechanogenesis
