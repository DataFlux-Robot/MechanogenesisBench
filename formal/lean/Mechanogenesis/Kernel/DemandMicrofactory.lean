import Mechanogenesis.Kernel.Digest
import Lean.Data.Json.FromToJson

namespace Mechanogenesis

/-!
Finite certificate for the demand-driven microfactory simulation track.

This checker proves the identities and inequalities actually computed by the
registered evaluator.  It deliberately preserves the evidence boundary:
synthetic demand evidence cannot certify human-endorsed surprise.
-/

structure MicrofactoryOperatorCertificate where
  bundleHash : Digest
  mechanicalPositionErrorUm : Nat
  pcbEscapeRatePpm : Nat
  batteryCalibrationErrorMv : Nat
  deriving DecidableEq, Repr, Lean.FromJson, Lean.ToJson

structure MicrofactoryGenerationCertificate where
  generation : Nat
  planHash : Digest
  productHash : Digest
  executionHash : Digest
  constructionTraceHash : Digest
  inputOperator : MicrofactoryOperatorCertificate
  outputOperator : MicrofactoryOperatorCertificate
  demandCalibrationErrorPpm : Nat
  maximumDemandCalibrationErrorPpm : Nat
  minimumProductUtilityMicro : Nat
  requiredProductUtilityMicro : Nat
  robustnessPasses : Nat
  robustnessTrials : Nat
  minimumRobustnessPpm : Nat
  syntheticDemandEvidence : Bool
  humanEndorsedPositiveSurprise : Bool
  deriving DecidableEq, Repr, Lean.FromJson, Lean.ToJson

structure DemandMicrofactoryCertificate where
  schemaVersion : String
  taskPackageDigest : Digest
  evaluatorDigest : Digest
  generation0 : MicrofactoryGenerationCertificate
  generation1 : MicrofactoryGenerationCertificate
  demandUpdateGainPpm : Nat
  requiredDemandUpdateGainPpm : Nat
  inheritanceAdvantagePpm : Nat
  requiredInheritanceAdvantagePpm : Nat
  deriving DecidableEq, Repr, Lean.FromJson, Lean.ToJson

def MicrofactoryOperatorCertificate.strictlyImprovesB
    (child parent : MicrofactoryOperatorCertificate) : Bool :=
  child.bundleHash != parent.bundleHash &&
  child.mechanicalPositionErrorUm < parent.mechanicalPositionErrorUm &&
  child.pcbEscapeRatePpm < parent.pcbEscapeRatePpm &&
  child.batteryCalibrationErrorMv < parent.batteryCalibrationErrorMv

def MicrofactoryGenerationCertificate.validB
    (generation : MicrofactoryGenerationCertificate) : Bool :=
  isSha256DigestB generation.planHash &&
  isSha256DigestB generation.productHash &&
  isSha256DigestB generation.executionHash &&
  isSha256DigestB generation.constructionTraceHash &&
  isSha256DigestB generation.inputOperator.bundleHash &&
  isSha256DigestB generation.outputOperator.bundleHash &&
  generation.outputOperator.strictlyImprovesB generation.inputOperator &&
  generation.demandCalibrationErrorPpm <=
    generation.maximumDemandCalibrationErrorPpm &&
  generation.requiredProductUtilityMicro <=
    generation.minimumProductUtilityMicro &&
  generation.robustnessTrials > 0 &&
  generation.robustnessPasses <= generation.robustnessTrials &&
  generation.minimumRobustnessPpm * generation.robustnessTrials <=
    generation.robustnessPasses * 1000000 &&
  !(generation.syntheticDemandEvidence &&
    generation.humanEndorsedPositiveSurprise)

def DemandMicrofactoryCertificate.validB
    (certificate : DemandMicrofactoryCertificate) : Bool :=
  isSha256DigestB certificate.taskPackageDigest &&
  isSha256DigestB certificate.evaluatorDigest &&
  certificate.schemaVersion == "demand-microfactory-certificate/v1" &&
  certificate.generation0.generation == 0 &&
  certificate.generation1.generation == 1 &&
  certificate.generation0.validB &&
  certificate.generation1.validB &&
  certificate.generation0.outputOperator.bundleHash ==
    certificate.generation1.inputOperator.bundleHash &&
  certificate.requiredDemandUpdateGainPpm <= certificate.demandUpdateGainPpm &&
  certificate.requiredInheritanceAdvantagePpm <=
    certificate.inheritanceAdvantagePpm

def checkDemandMicrofactory
    (certificate : DemandMicrofactoryCertificate) : Bool :=
  certificate.validB

theorem demand_microfactory_checker_sound
    (certificate : DemandMicrofactoryCertificate)
    (checked : checkDemandMicrofactory certificate = true) :
    certificate.validB = true := by
  exact checked

theorem checked_microfactory_has_exact_operator_inheritance
    (certificate : DemandMicrofactoryCertificate)
    (checked : checkDemandMicrofactory certificate = true) :
    certificate.generation0.outputOperator.bundleHash =
      certificate.generation1.inputOperator.bundleHash := by
  simp only [checkDemandMicrofactory, DemandMicrofactoryCertificate.validB,
    Bool.and_eq_true] at checked
  simpa using checked.1.1.2

theorem checked_synthetic_generation0_cannot_claim_human_endorsement
    (certificate : DemandMicrofactoryCertificate)
    (checked : checkDemandMicrofactory certificate = true)
    (synthetic : certificate.generation0.syntheticDemandEvidence = true) :
    certificate.generation0.humanEndorsedPositiveSurprise = false := by
  simp only [checkDemandMicrofactory, DemandMicrofactoryCertificate.validB,
    Bool.and_eq_true] at checked
  have generationValid := checked.1.1.1.1.2
  simp only [MicrofactoryGenerationCertificate.validB,
    Bool.and_eq_true] at generationValid
  have guard := generationValid.2
  simpa [synthetic] using guard

theorem checked_synthetic_generation1_cannot_claim_human_endorsement
    (certificate : DemandMicrofactoryCertificate)
    (checked : checkDemandMicrofactory certificate = true)
    (synthetic : certificate.generation1.syntheticDemandEvidence = true) :
    certificate.generation1.humanEndorsedPositiveSurprise = false := by
  simp only [checkDemandMicrofactory, DemandMicrofactoryCertificate.validB,
    Bool.and_eq_true] at checked
  have generationValid := checked.1.1.1.2
  simp only [MicrofactoryGenerationCertificate.validB,
    Bool.and_eq_true] at generationValid
  have guard := generationValid.2
  simpa [synthetic] using guard

end Mechanogenesis
