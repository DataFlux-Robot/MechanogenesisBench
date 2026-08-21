import Mechanogenesis.Kernel.CanonicalIR

namespace Mechanogenesis

def metrologySemanticsId : String :=
  "Mechanogenesis.MetrologyRefinement.v0.1"

def requiredMetrologyAssumptions : List String := [
  "geometry_role_binding",
  "additive_error_budget",
  "calibration_parameter_fidelity"
]

def ceilDivNat (numerator denominator : Nat) : Nat :=
  if denominator == 0 then 0
  else (numerator + denominator - 1) / denominator

structure MetrologyRefinementCertificate where
  schemaVersion : String
  semanticsId : String
  programHash : Digest
  operationIndex : Nat
  operationHash : Digest
  parentWorldHash : Digest
  childWorldHash : Digest
  assemblyId : String
  capabilityId : String
  locatorSpacingUm : Nat
  radialClearanceUm : Nat
  referenceClearanceUm : Nat
  workpieceSpanUm : Nat
  manufacturingRepeatabilityUm : Nat
  probeRepeatabilityUm : Nat
  disturbanceBoundUm : Nat
  sourceProcessErrorUm : Nat
  angularTipErrorUm : Nat
  worstCaseErrorUm : Nat
  absoluteFrameErrorUm : Nat
  evidenceTier : String
  assumptionIds : List String
  deriving DecidableEq, Repr, Lean.FromJson, Lean.ToJson

def computedAngularTipError (certificate : MetrologyRefinementCertificate) : Nat :=
  ceilDivNat
    (2 * certificate.radialClearanceUm * certificate.workpieceSpanUm)
    certificate.locatorSpacingUm

def computedWorstCaseError (certificate : MetrologyRefinementCertificate) : Nat :=
  certificate.radialClearanceUm +
  certificate.referenceClearanceUm +
  certificate.angularTipErrorUm +
  certificate.manufacturingRepeatabilityUm +
  certificate.probeRepeatabilityUm +
  certificate.disturbanceBoundUm

def MetrologyFormulaConditions
    (certificate : MetrologyRefinementCertificate) : Prop :=
  0 < certificate.locatorSpacingUm ∧
  0 < certificate.workpieceSpanUm ∧
  certificate.angularTipErrorUm = computedAngularTipError certificate ∧
  certificate.worstCaseErrorUm = computedWorstCaseError certificate ∧
  certificate.absoluteFrameErrorUm =
    certificate.sourceProcessErrorUm + certificate.worstCaseErrorUm ∧
  uniqueStringsB certificate.assumptionIds = true ∧
  requiredMetrologyAssumptions.all (fun assumptionId =>
    certificate.assumptionIds.contains assumptionId) = true

def metrologyFormulaB (certificate : MetrologyRefinementCertificate) : Bool :=
  certificate.locatorSpacingUm > 0 &&
  certificate.workpieceSpanUm > 0 &&
  certificate.angularTipErrorUm == computedAngularTipError certificate &&
  certificate.worstCaseErrorUm == computedWorstCaseError certificate &&
  certificate.absoluteFrameErrorUm ==
    certificate.sourceProcessErrorUm + certificate.worstCaseErrorUm &&
  uniqueStringsB certificate.assumptionIds &&
  requiredMetrologyAssumptions.all (fun assumptionId =>
    certificate.assumptionIds.contains assumptionId)

def metrologyIdentityB (certificate : MetrologyRefinementCertificate) : Bool :=
  certificate.schemaVersion == "0.1" &&
  certificate.semanticsId == metrologySemanticsId &&
  isSha256DigestB certificate.programHash &&
  isSha256DigestB certificate.operationHash &&
  isSha256DigestB certificate.parentWorldHash &&
  isSha256DigestB certificate.childWorldHash &&
  certificate.assemblyId != "" && certificate.capabilityId != "" &&
  certificate.evidenceTier == "conformance"

def validMetrologyRefinementB
    (certificate : MetrologyRefinementCertificate) : Bool :=
  metrologyIdentityB certificate && metrologyFormulaB certificate

def ValidMetrologyRefinement
    (certificate : MetrologyRefinementCertificate) : Prop :=
  validMetrologyRefinementB certificate = true

def checkMetrologyRefinement
    (certificate : MetrologyRefinementCertificate) : Bool :=
  validMetrologyRefinementB certificate

theorem metrology_formula_checker_sound
    (certificate : MetrologyRefinementCertificate)
    (accepted : metrologyFormulaB certificate = true) :
    MetrologyFormulaConditions certificate := by
  simp [metrologyFormulaB] at accepted
  rcases accepted with
    ⟨⟨⟨⟨⟨⟨spacingPositive, spanPositive⟩, angularExact⟩,
      worstExact⟩, absoluteExact⟩, assumptionsUnique⟩, assumptionsPresent⟩
  simp [MetrologyFormulaConditions]
  exact ⟨spacingPositive, spanPositive, angularExact, worstExact,
    absoluteExact, assumptionsUnique, assumptionsPresent⟩

theorem metrology_refinement_checker_sound
    (certificate : MetrologyRefinementCertificate)
    (accepted : checkMetrologyRefinement certificate = true) :
    ValidMetrologyRefinement certificate ∧
    MetrologyFormulaConditions certificate := by
  have split : metrologyIdentityB certificate = true ∧
      metrologyFormulaB certificate = true := by
    simpa [checkMetrologyRefinement, validMetrologyRefinementB] using accepted
  exact ⟨accepted, metrology_formula_checker_sound certificate split.2⟩

theorem computed_worst_case_contains_disturbance
    (certificate : MetrologyRefinementCertificate) :
    certificate.disturbanceBoundUm ≤ computedWorstCaseError certificate := by
  unfold computedWorstCaseError
  exact Nat.le_add_left certificate.disturbanceBoundUm _

theorem accepted_metrology_bound_contains_disturbance
    (certificate : MetrologyRefinementCertificate)
    (accepted : checkMetrologyRefinement certificate = true) :
    certificate.disturbanceBoundUm ≤ certificate.worstCaseErrorUm := by
  have formulas := (metrology_refinement_checker_sound certificate accepted).2
  rw [formulas.2.2.2.1]
  exact computed_worst_case_contains_disturbance certificate

theorem accepted_metrology_absolute_bound_contains_source_process
    (certificate : MetrologyRefinementCertificate)
    (accepted : checkMetrologyRefinement certificate = true) :
    certificate.sourceProcessErrorUm ≤ certificate.absoluteFrameErrorUm := by
  have formulas := (metrology_refinement_checker_sound certificate accepted).2
  rw [formulas.2.2.2.2.1]
  exact Nat.le_add_right certificate.sourceProcessErrorUm _

end Mechanogenesis
