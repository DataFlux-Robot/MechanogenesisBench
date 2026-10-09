import Mechanogenesis.Kernel.Digest
import Lean.Data.Json.FromToJson

namespace Mechanogenesis

/-!
`DiagnosticEvidence` is the S0 protocol for artifact-aware mechanism analysis.
It does not prove that an LLM's explanation is scientifically true.  It makes
four narrower facts decidable: guidance arms share one registered identity,
the prediction existed before hidden reveal, every cited anchor is grounded
and independently checked, and the predicted winner names a registered arm.
-/

def diagnosticEvidenceSemanticsId : String :=
  "Mechanogenesis.DiagnosticEvidence.v0.1"

def diagnosticAccessLevels : List String :=
  ["endpoint_only", "artifact_aware"]

def diagnosticStages : List String :=
  [
    "mission_framing",
    "world_access",
    "mrs_design",
    "canonical_construction",
    "physical_experiment",
    "causal_evaluation",
    "recursive_update",
    "cross_stage"
  ]

def diagnosticRootMechanisms : List String :=
  [
    "evidence_grounding",
    "separability_access",
    "search_adaptation",
    "causal_attribution",
    "resource_robustness"
  ]

structure DiagnosticAnchor where
  anchorId : String
  artifactPath : String
  jsonPointer : String
  artifactHash : Digest
  valueHash : Digest
  verifierHash : Digest
  grounded : Bool
  independentCheck : Bool
  deriving DecidableEq, Repr, Lean.FromJson, Lean.ToJson

structure DiagnosticArmReceipt where
  armId : String
  guidanceHash : Digest
  requestHash : Digest
  responseHash : Digest
  deriving DecidableEq, Repr, Lean.FromJson, Lean.ToJson

structure DiagnosticCertificate where
  schemaVersion : String
  semanticsId : String
  taskHash : Digest
  parentGeneratorHash : Digest
  harnessHash : Digest
  evaluatorHash : Digest
  budgetHash : Digest
  evidencePackageHash : Digest
  predictionHash : Digest
  outcomeRevealHash : Digest
  accessLevel : String
  predictedBestArm : String
  diagnosticStage : String
  rootMechanism : String
  predictionFrozenAt : Nat
  outcomeRevealedAt : Nat
  arms : List DiagnosticArmReceipt
  anchors : List DiagnosticAnchor
  deriving DecidableEq, Repr, Lean.FromJson, Lean.ToJson

def DiagnosticAnchor.validB (anchor : DiagnosticAnchor) : Bool :=
  !anchor.artifactPath.isEmpty &&
  (!anchor.jsonPointer.isEmpty &&
  (isSha256DigestB anchor.artifactHash &&
  (isSha256DigestB anchor.valueHash &&
  (isSha256DigestB anchor.verifierHash &&
  (anchor.grounded && anchor.independentCheck)))))

def DiagnosticArmReceipt.validB (arm : DiagnosticArmReceipt) : Bool :=
  isSha256DigestB arm.guidanceHash &&
  isSha256DigestB arm.requestHash &&
  isSha256DigestB arm.responseHash

def DiagnosticCertificate.identityDigestsValidB
    (certificate : DiagnosticCertificate) : Bool :=
  [
    certificate.taskHash,
    certificate.parentGeneratorHash,
    certificate.harnessHash,
    certificate.evaluatorHash,
    certificate.budgetHash,
    certificate.evidencePackageHash,
    certificate.predictionHash,
    certificate.outcomeRevealHash
  ].all isSha256DigestB

def DiagnosticCertificate.timelineValidB
    (certificate : DiagnosticCertificate) : Bool :=
  decide (certificate.predictionFrozenAt < certificate.outcomeRevealedAt)

def DiagnosticCertificate.armSetValidB
    (certificate : DiagnosticCertificate) : Bool :=
  decide (2 ≤ certificate.arms.length) &&
  decide ((certificate.arms.map (·.armId)).Nodup) &&
  decide ((certificate.arms.map (·.guidanceHash)).Nodup) &&
  certificate.arms.all DiagnosticArmReceipt.validB &&
  certificate.arms.any (fun arm => arm.armId == certificate.predictedBestArm)

def DiagnosticCertificate.anchorSetValidB
    (certificate : DiagnosticCertificate) : Bool :=
  !certificate.anchors.isEmpty &&
  (decide ((certificate.anchors.map (·.anchorId)).Nodup) &&
  certificate.anchors.all DiagnosticAnchor.validB)

def DiagnosticCertificate.metadataValidB
    (certificate : DiagnosticCertificate) : Bool :=
  certificate.schemaVersion == "0.1" &&
  certificate.semanticsId == diagnosticEvidenceSemanticsId &&
  diagnosticAccessLevels.contains certificate.accessLevel &&
  diagnosticStages.contains certificate.diagnosticStage &&
  diagnosticRootMechanisms.contains certificate.rootMechanism

def DiagnosticCertificate.protocolValidB
    (certificate : DiagnosticCertificate) : Bool :=
  certificate.metadataValidB &&
  (certificate.identityDigestsValidB &&
  (certificate.timelineValidB &&
  (certificate.armSetValidB && certificate.anchorSetValidB)))

def DiagnosticCertificate.ProtocolValid
    (certificate : DiagnosticCertificate) : Prop :=
  certificate.protocolValidB = true

def checkDiagnosticEvidence (certificate : DiagnosticCertificate) : Bool :=
  certificate.protocolValidB

theorem diagnostic_evidence_checker_sound
    (certificate : DiagnosticCertificate)
    (checked : checkDiagnosticEvidence certificate = true) :
    certificate.ProtocolValid := by
  exact checked

theorem accepted_diagnostic_prediction_precedes_hidden_reveal
    (certificate : DiagnosticCertificate)
    (checked : checkDiagnosticEvidence certificate = true) :
    certificate.predictionFrozenAt < certificate.outcomeRevealedAt := by
  have identityAndRest := (Bool.and_eq_true_iff.mp checked).2
  have timelineAndRest := (Bool.and_eq_true_iff.mp identityAndRest).2
  have timelineTrue := (Bool.and_eq_true_iff.mp timelineAndRest).1
  simpa [DiagnosticCertificate.timelineValidB] using timelineTrue

theorem accepted_diagnostic_has_grounded_independent_anchors
    (certificate : DiagnosticCertificate)
    (anchor : DiagnosticAnchor)
    (member : anchor ∈ certificate.anchors)
    (checked : checkDiagnosticEvidence certificate = true) :
    anchor.grounded = true ∧ anchor.independentCheck = true := by
  have identityAndRest := (Bool.and_eq_true_iff.mp checked).2
  have timelineAndRest := (Bool.and_eq_true_iff.mp identityAndRest).2
  have armsAndAnchors := (Bool.and_eq_true_iff.mp timelineAndRest).2
  have anchorSetTrue := (Bool.and_eq_true_iff.mp armsAndAnchors).2
  have nodupAndAll := (Bool.and_eq_true_iff.mp anchorSetTrue).2
  have allTrue := (Bool.and_eq_true_iff.mp nodupAndAll).2
  have validAnchor : anchor.validB = true :=
    (List.all_eq_true.mp allTrue) anchor member
  have pointerAndRest := (Bool.and_eq_true_iff.mp validAnchor).2
  have artifactAndRest := (Bool.and_eq_true_iff.mp pointerAndRest).2
  have valueAndRest := (Bool.and_eq_true_iff.mp artifactAndRest).2
  have verifierAndRest := (Bool.and_eq_true_iff.mp valueAndRest).2
  have groundedAndIndependent := (Bool.and_eq_true_iff.mp verifierAndRest).2
  exact Bool.and_eq_true_iff.mp groundedAndIndependent

/- Endpoint-equivalent public behavior can hide opposite physical winners.
This is why a diagnostic benchmark needs sealed interventions rather than a
more articulate endpoint judge. -/
structure PublicHiddenOutcome where
  publicScore : Nat
  hiddenUtility : Nat
  deriving DecidableEq, Repr

theorem public_endpoint_does_not_identify_hidden_winner :
    ∃ left right : PublicHiddenOutcome,
      left.publicScore = right.publicScore ∧
      left.hiddenUtility < right.hiddenUtility := by
  exact ⟨⟨100, 1⟩, ⟨100, 2⟩, rfl, by decide⟩

/- Protocol acceptance is not an oracle for explanation truth.  The evaluator
must score the registered prediction against later hidden outcomes. -/
structure DiagnosticClaimCeiling where
  protocolAccepted : Bool
  explanationTrue : Bool
  deriving DecidableEq, Repr

theorem protocol_acceptance_does_not_imply_explanation_truth :
    ∃ result : DiagnosticClaimCeiling,
      result.protocolAccepted = true ∧ result.explanationTrue = false := by
  exact ⟨⟨true, false⟩, rfl, rfl⟩

end Mechanogenesis
