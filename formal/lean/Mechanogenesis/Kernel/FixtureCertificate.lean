import Mechanogenesis.Kernel.Promotion
import Lean.Data.Json.FromToJson

namespace Mechanogenesis

def sovereignSemanticsId : String :=
  "Mechanogenesis.SovereignKernel.v0.1"

def requiredFixtureAssumptions : List String := [
  "fixed_point_arithmetic",
  "hash_identity",
  "reference_model_fidelity"
]

structure CertificateAssumption where
  assumptionId : String
  kind : String
  statementHash : Digest
  scopeHash : Digest
  deriving DecidableEq, Repr, Lean.FromJson, Lean.ToJson

structure SovereignCertificate where
  schemaVersion : String
  semanticsId : String
  backendId : String
  trustClass : String
  evidenceTier : String
  strategyHash : Digest
  candidateSupportSize : Nat
  attemptedCandidates : Nat
  input : TransitionInput
  output : TransitionOutput
  assumptions : List CertificateAssumption
  receipts : List TransitionReceipt
  deriving DecidableEq, Repr, Lean.FromJson, Lean.ToJson

/-- Executable evaluator decision bound to the same parent/child world pair as
the transition certificate. Error fields are conservative positive upper
bounds, so a smaller child value is an improvement. -/
structure CertificatePromotionDecision where
  schemaVersion : String
  semanticsId : String
  artifactHash : Digest
  parentWorldHash : Digest
  childWorldHash : Digest
  parentErrorUpper : Nat
  childErrorUpper : Nat
  requiredImprovement : Nat
  netValue : Nat
  robustnessPassed : Bool
  evidenceTier : String
  deriving DecidableEq, Repr, Lean.FromJson, Lean.ToJson

structure SovereignPromotionEnvelope where
  certificate : SovereignCertificate
  decision : CertificatePromotionDecision
  deriving DecidableEq, Repr, Lean.FromJson, Lean.ToJson

def isSha256DigestB (value : String) : Bool :=
  value.startsWith "sha256:" &&
  value.length == 71 &&
  (value.toList.drop 7).all (fun character =>
    "0123456789abcdef".toList.contains character)

def IsSha256Digest (value : String) : Prop :=
  isSha256DigestB value = true

def KnownAssumptionKind (kind : String) : Prop :=
  kind ∈ [
    "physical_model",
    "calibration",
    "environment",
    "cryptographic_identity",
    "numerical_approximation"
  ]

def ValidCertificateAssumption (assumption : CertificateAssumption) : Prop :=
  assumption.assumptionId ≠ "" ∧
  KnownAssumptionKind assumption.kind ∧
  IsSha256Digest assumption.statementHash ∧
  IsSha256Digest assumption.scopeHash

def validCertificateAssumptionB (assumption : CertificateAssumption) : Bool :=
  assumption.assumptionId != "" &&
  [
    "physical_model",
    "calibration",
    "environment",
    "cryptographic_identity",
    "numerical_approximation"
  ].contains assumption.kind &&
  isSha256DigestB assumption.statementHash &&
  isSha256DigestB assumption.scopeHash

def CertificateAccountsFor
    (assumptions : List CertificateAssumption)
    (required : List String) : Prop :=
  required.all (fun assumptionId =>
    assumptions.any (fun assumption => assumption.assumptionId == assumptionId)) = true

def certificateAccountsForB
    (assumptions : List CertificateAssumption)
    (required : List String) : Bool :=
  required.all (fun assumptionId =>
    assumptions.any (fun assumption => assumption.assumptionId == assumptionId))

def ReceiptDigestsValid (receipt : TransitionReceipt) : Prop :=
  IsSha256Digest receipt.operationHash ∧
  IsSha256Digest receipt.parentWorldHash ∧
  IsSha256Digest receipt.childWorldHash

def receiptDigestsValidB (receipt : TransitionReceipt) : Bool :=
  isSha256DigestB receipt.operationHash &&
  isSha256DigestB receipt.parentWorldHash &&
  isSha256DigestB receipt.childWorldHash &&
  receipt.balances.isEmpty == false &&
  receipt.balances.all (fun balance => balance.material != "")

/-- This proposition is the sovereign meaning of a certificate-checked
fixture transition. The Python backend may produce the JSON, but it cannot
change this acceptance predicate. -/
def validSovereignCertificateB (certificate : SovereignCertificate) : Bool :=
  certificate.schemaVersion == "0.1" &&
  certificate.semanticsId == sovereignSemanticsId &&
  certificate.backendId != "" &&
  certificate.trustClass == "certificate_checked" &&
  certificate.evidenceTier == "conformance" &&
  isSha256DigestB certificate.strategyHash &&
  certificate.candidateSupportSize > 0 &&
  certificate.attemptedCandidates > 0 &&
  certificate.attemptedCandidates <= certificate.candidateSupportSize &&
  isSha256DigestB certificate.input.worldSpecHash &&
  isSha256DigestB certificate.input.parentWorldHash &&
  isSha256DigestB certificate.input.programHash &&
  isSha256DigestB certificate.output.childWorldHash &&
  certificate.assumptions.all validCertificateAssumptionB &&
  (certificate.assumptions.map (fun assumption => assumption.assumptionId)).eraseDups.length ==
    certificate.assumptions.length &&
  certificateAccountsForB certificate.assumptions requiredFixtureAssumptions &&
  certificate.receipts.all receiptDigestsValidB &&
  validTransitionAccountingB certificate.input certificate.output certificate.receipts

def ValidSovereignCertificate (certificate : SovereignCertificate) : Prop :=
  validSovereignCertificateB certificate = true

def checkSovereignCertificate (certificate : SovereignCertificate) : Bool :=
  validSovereignCertificateB certificate

def validCertificatePromotionB
    (certificate : SovereignCertificate)
    (decision : CertificatePromotionDecision) : Bool :=
  decision.schemaVersion == "0.1" &&
  decision.semanticsId == sovereignSemanticsId &&
  isSha256DigestB decision.artifactHash &&
  decision.parentWorldHash == certificate.input.parentWorldHash &&
  decision.childWorldHash == certificate.output.childWorldHash &&
  decision.requiredImprovement > 0 &&
  decision.childErrorUpper + decision.requiredImprovement ≤
    decision.parentErrorUpper &&
  decision.netValue > 0 &&
  decision.robustnessPassed &&
  decision.evidenceTier == certificate.evidenceTier

def checkSovereignPromotion (envelope : SovereignPromotionEnvelope) : Bool :=
  checkSovereignCertificate envelope.certificate &&
  validCertificatePromotionB envelope.certificate envelope.decision

def certificatePromotionAsDecision
    (decision : CertificatePromotionDecision) : PromotionDecision :=
  {
    parentWorldHash := decision.parentWorldHash
    childWorldHash := decision.childWorldHash
    claim := {
      parentErrorUpper := decision.parentErrorUpper
      childErrorUpper := decision.childErrorUpper
      requiredMargin := decision.requiredImprovement
      netValue := decision.netValue
      claimedTier := .conformance
      ceilingTier := .conformance
    }
  }

theorem sovereign_checker_sound
    (certificate : SovereignCertificate)
    (accepted : checkSovereignCertificate certificate = true) :
    ValidSovereignCertificate certificate := by
  exact accepted

theorem sovereign_checker_implies_transition_accounting
    (certificate : SovereignCertificate)
    (accepted : checkSovereignCertificate certificate = true) :
    ValidTransitionAccounting
      certificate.input certificate.output certificate.receipts := by
  simp [checkSovereignCertificate, validSovereignCertificateB] at accepted
  exact accepted.2

theorem sovereign_checker_implies_explicit_assumptions
    (certificate : SovereignCertificate)
    (accepted : checkSovereignCertificate certificate = true) :
    CertificateAccountsFor certificate.assumptions requiredFixtureAssumptions := by
  simp [checkSovereignCertificate, validSovereignCertificateB,
    CertificateAccountsFor, certificateAccountsForB] at accepted ⊢
  exact accepted.1.1.2

theorem sovereign_promotion_checker_sound
    (envelope : SovereignPromotionEnvelope)
    (accepted : checkSovereignPromotion envelope = true) :
    checkSovereignCertificate envelope.certificate = true ∧
    (certificatePromotionAsDecision envelope.decision).AcceptedFor
      envelope.certificate.input envelope.certificate.output ∧
    envelope.decision.robustnessPassed = true ∧
    envelope.decision.evidenceTier = envelope.certificate.evidenceTier := by
  simp [checkSovereignPromotion, validCertificatePromotionB,
    certificatePromotionAsDecision, PromotionDecision.AcceptedFor,
    PromotionDecision.BoundTo, PromotionClaim.Accepted,
    EvidenceTier.noStrongerThan, EvidenceTier.rank] at accepted ⊢
  rcases accepted with ⟨certificateAccepted,
    ⟨⟨⟨⟨⟨⟨⟨⟨⟨_, _⟩, _⟩, parentBound⟩, childBound⟩,
      improvementPositive⟩, errorBound⟩, netValuePositive⟩,
      robustnessPassed⟩, evidenceBound⟩⟩
  exact ⟨certificateAccepted,
    ⟨⟨parentBound, childBound⟩,
      improvementPositive, errorBound, netValuePositive⟩,
    robustnessPassed, evidenceBound⟩

/-- Central sovereign-kernel theorem: once a backend certificate and promotion
gate are both accepted, the promoted transition is lineage/accounting valid,
its required assumptions remain explicit, and its bounded error improves
strictly. Physical fidelity remains conditional on those assumptions. -/
theorem checked_certificate_allows_only_accounted_strict_promotion
    (envelope : SovereignPromotionEnvelope)
    (accepted : checkSovereignPromotion envelope = true) :
    ValidTransitionAccounting
      envelope.certificate.input envelope.certificate.output
      envelope.certificate.receipts ∧
    CertificateAccountsFor
      envelope.certificate.assumptions requiredFixtureAssumptions ∧
    (certificatePromotionAsDecision envelope.decision).BoundTo
      envelope.certificate.input envelope.certificate.output ∧
    envelope.decision.childErrorUpper < envelope.decision.parentErrorUpper ∧
    0 < envelope.decision.netValue ∧
    envelope.decision.robustnessPassed = true ∧
    envelope.decision.evidenceTier = envelope.certificate.evidenceTier := by
  have checked := sovereign_promotion_checker_sound envelope accepted
  have transitionValid := sovereign_checker_implies_transition_accounting
    envelope.certificate checked.1
  have assumptionsAccounted := sovereign_checker_implies_explicit_assumptions
    envelope.certificate checked.1
  exact ⟨transitionValid, assumptionsAccounted, checked.2.1.1,
    bound_promotion_implies_strict_error_improvement
      (certificatePromotionAsDecision envelope.decision)
      envelope.certificate.input envelope.certificate.output checked.2.1,
    checked.2.1.2.2.2.1, checked.2.2.1, checked.2.2.2⟩

end Mechanogenesis
