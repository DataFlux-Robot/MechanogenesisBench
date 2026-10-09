import Mechanogenesis.Kernel.Digest
import Lean.Data.Json.FromToJson

namespace Mechanogenesis

/-!
Evidence--Action Closure (EAC) is a sovereign protocol condition for research
trajectories.  It does not assert that an LLM, judge, simulator, or physical
model is correct.  It makes a narrower property decidable: evaluator-owned
critical evidence cannot coexist with promotion unless the evidence is
grounded, independently checked, and linked to either a tested action revision
or withdrawal of the contradicted claim.

This separates four notions that endpoint benchmarks commonly conflate:
evidence availability, evidence validity, evidence-caused action, and hidden
scientific-contract preservation.
-/

def evidenceActionSemanticsId : String :=
  "Mechanogenesis.EvidenceActionClosure.v0.1"

structure EvidenceActionReceipt where
  evidenceHash : Digest
  sourceHash : Digest
  claimHash : Digest
  priorActionHash : Digest
  resultingActionHash : Digest
  verifierHash : Digest
  critical : Bool
  contradictsClaim : Bool
  grounded : Bool
  independentCheck : Bool
  revisionDeclared : Bool
  retested : Bool
  claimWithdrawn : Bool
  deriving DecidableEq, Repr, Lean.FromJson, Lean.ToJson

structure EvidenceActionCertificate where
  schemaVersion : String
  semanticsId : String
  trajectoryHash : Digest
  finalClaimHash : Digest
  evaluatorHash : Digest
  promotionRequested : Bool
  receipts : List EvidenceActionReceipt
  deriving DecidableEq, Repr, Lean.FromJson, Lean.ToJson

def EvidenceActionReceipt.DigestsValid
    (receipt : EvidenceActionReceipt) : Prop :=
  [
    receipt.evidenceHash,
    receipt.sourceHash,
    receipt.claimHash,
    receipt.priorActionHash,
    receipt.resultingActionHash,
    receipt.verifierHash
  ].all isSha256DigestB = true

def EvidenceActionReceipt.digestsValidB
    (receipt : EvidenceActionReceipt) : Bool :=
  [
    receipt.evidenceHash,
    receipt.sourceHash,
    receipt.claimHash,
    receipt.priorActionHash,
    receipt.resultingActionHash,
    receipt.verifierHash
  ].all isSha256DigestB

def EvidenceActionCertificate.DigestsValid
    (certificate : EvidenceActionCertificate) : Prop :=
  [
    certificate.trajectoryHash,
    certificate.finalClaimHash,
    certificate.evaluatorHash
  ].all isSha256DigestB = true

def EvidenceActionCertificate.digestsValidB
    (certificate : EvidenceActionCertificate) : Bool :=
  [
    certificate.trajectoryHash,
    certificate.finalClaimHash,
    certificate.evaluatorHash
  ].all isSha256DigestB

def EvidenceActionReceipt.CriticalContradiction
    (receipt : EvidenceActionReceipt) : Prop :=
  receipt.critical = true ∧ receipt.contradictsClaim = true

def EvidenceActionReceipt.GroundedByIndependentVerifier
    (receipt : EvidenceActionReceipt) : Prop :=
  receipt.grounded = true ∧ receipt.independentCheck = true

def EvidenceActionReceipt.ResolvedFor
    (receipt : EvidenceActionReceipt) (finalClaimHash : Digest) : Prop :=
  (
    receipt.revisionDeclared = true ∧
    receipt.priorActionHash ≠ receipt.resultingActionHash ∧
    receipt.retested = true
  ) ∨
  (
    receipt.claimWithdrawn = true ∧
    receipt.claimHash ≠ finalClaimHash
  )

def EvidenceActionReceipt.resolvedForB
    (receipt : EvidenceActionReceipt) (finalClaimHash : Digest) : Bool :=
  (
    receipt.revisionDeclared &&
    receipt.priorActionHash != receipt.resultingActionHash &&
    receipt.retested
  ) ||
  (
    receipt.claimWithdrawn &&
    receipt.claimHash != finalClaimHash
  )

def EvidenceActionReceipt.validForB
    (receipt : EvidenceActionReceipt)
    (certificate : EvidenceActionCertificate) : Bool :=
  receipt.digestsValidB &&
  (!receipt.critical || (receipt.grounded && receipt.independentCheck)) &&
  (
    !certificate.promotionRequested ||
    !receipt.critical ||
    !receipt.contradictsClaim ||
    receipt.resolvedForB certificate.finalClaimHash
  )

def EvidenceActionCertificate.protocolValidB
    (certificate : EvidenceActionCertificate) : Bool :=
  certificate.schemaVersion == "0.1" &&
  certificate.semanticsId == evidenceActionSemanticsId &&
  certificate.digestsValidB &&
  !certificate.receipts.isEmpty &&
  certificate.receipts.any (fun receipt => receipt.critical) &&
  certificate.receipts.all (fun receipt => receipt.validForB certificate)

/--
Protocol validity is deliberately finite and decidable.  A certificate cannot
be vacuous: it contains at least one evaluator-designated critical receipt.
Every critical receipt must be grounded and independently checked.  Promotion
adds the stronger closure obligation that every critical contradiction has
changed and re-tested the action, or removed the contradicted claim.
-/
def EvidenceActionCertificate.ProtocolValid
    (certificate : EvidenceActionCertificate) : Prop :=
  certificate.protocolValidB = true

def checkEvidenceActionClosure
    (certificate : EvidenceActionCertificate) : Bool :=
  certificate.protocolValidB

theorem evidence_action_checker_sound
    (certificate : EvidenceActionCertificate)
    (checked : checkEvidenceActionClosure certificate = true) :
    certificate.ProtocolValid := by
  exact checked

/-- A critical contradiction that is neither action-resolved nor withdrawn
blocks promotion.  This is the formal version of "the agent noticed the fatal
flaw and shipped anyway". -/
theorem unresolved_critical_contradiction_blocks_promotion
    (certificate : EvidenceActionCertificate)
    (receipt : EvidenceActionReceipt)
    (member : receipt ∈ certificate.receipts)
    (critical : receipt.CriticalContradiction)
    (unresolved : ¬ receipt.ResolvedFor certificate.finalClaimHash) :
    ¬ (certificate.ProtocolValid ∧
      certificate.promotionRequested = true) := by
  intro accepted
  have checked : certificate.protocolValidB = true := accepted.1
  unfold EvidenceActionCertificate.protocolValidB at checked
  have allValid := (Bool.and_eq_true_iff.mp checked).2
  have validReceipt : receipt.validForB certificate = true :=
    (List.all_eq_true.mp allValid) receipt member
  have resolved : receipt.ResolvedFor certificate.finalClaimHash := by
    rcases critical with ⟨criticalTrue, contradictsTrue⟩
    have resolvedTrue :
        receipt.resolvedForB certificate.finalClaimHash = true := by
      have reduced := validReceipt
      simp [EvidenceActionReceipt.validForB, accepted.2,
        criticalTrue, contradictsTrue] at reduced
      exact reduced.2
    simpa [EvidenceActionReceipt.ResolvedFor,
      EvidenceActionReceipt.resolvedForB,
      and_assoc] using resolvedTrue
  exact unresolved resolved

/-- Endpoint equality does not identify process validity: two trajectories can
receive the same score while only one closes the evidence--action loop. -/
structure EndpointResearchTrace where
  endpointScore : Nat
  evidenceActionClosed : Bool
  deriving DecidableEq, Repr

def EndpointResearchTrace.ScientificallyClosed
    (trace : EndpointResearchTrace) : Prop :=
  trace.evidenceActionClosed = true

theorem endpoint_score_cannot_identify_evidence_action_closure :
    let openLoop : EndpointResearchTrace := ⟨100, false⟩
    let closedLoop : EndpointResearchTrace := ⟨100, true⟩
    openLoop.endpointScore = closedLoop.endpointScore ∧
      ¬ openLoop.ScientificallyClosed ∧ closedLoop.ScientificallyClosed := by
  dsimp [EndpointResearchTrace.ScientificallyClosed]
  exact ⟨rfl, by decide, rfl⟩

/-- Public success does not entail preservation of a hidden scientific
contract.  Hidden intervention checks are a separate proof obligation. -/
structure ScientificContractOutcome where
  publicPass : Bool
  hiddenContractPass : Bool
  deriving DecidableEq, Repr

theorem public_success_does_not_imply_hidden_contract :
    ∃ outcome : ScientificContractOutcome,
      outcome.publicPass = true ∧ outcome.hiddenContractPass = false := by
  exact ⟨⟨true, false⟩, rfl, rfl⟩

/-- Evidence inclusion has no unconditional monotonicity law.  It may improve
or reduce utility; grounding and causal paired evaluation are necessary. -/
structure GuidanceEffect where
  utilityWithoutEvidence : Nat
  utilityWithEvidence : Nat
  deriving DecidableEq, Repr

theorem evidence_inclusion_is_not_unconditionally_monotone :
    (∃ harmful : GuidanceEffect,
      harmful.utilityWithEvidence < harmful.utilityWithoutEvidence) ∧
    (∃ helpful : GuidanceEffect,
      helpful.utilityWithoutEvidence < helpful.utilityWithEvidence) := by
  exact ⟨⟨⟨2, 1⟩, by decide⟩, ⟨⟨1, 2⟩, by decide⟩⟩

structure GuidanceForkIdentity where
  parentGeneratorHash : Digest
  taskHash : Digest
  harnessHash : Digest
  evaluatorHash : Digest
  budgetHash : Digest
  deriving DecidableEq, Repr

structure GuidanceForkObservation where
  identity : GuidanceForkIdentity
  evidenceEnabled : Bool
  futureUtility : Nat
  deriving DecidableEq, Repr

def MatchedGuidanceForks
    (withEvidence withoutEvidence : GuidanceForkObservation) : Prop :=
  withEvidence.identity = withoutEvidence.identity ∧
  withEvidence.evidenceEnabled = true ∧
  withoutEvidence.evidenceEnabled = false

def ObservedGuidanceGain
    (withEvidence withoutEvidence : GuidanceForkObservation) : Prop :=
  withoutEvidence.futureUtility < withEvidence.futureUtility

/-- A raw score gain with unmatched generator/task/harness/evaluator/budget
identity cannot by itself establish a guidance effect. -/
theorem observed_guidance_gain_does_not_imply_matched_attribution
    (leftIdentity rightIdentity : GuidanceForkIdentity)
    (different : leftIdentity ≠ rightIdentity) :
    let withEvidence : GuidanceForkObservation := ⟨leftIdentity, true, 2⟩
    let withoutEvidence : GuidanceForkObservation := ⟨rightIdentity, false, 1⟩
    ObservedGuidanceGain withEvidence withoutEvidence ∧
      ¬ MatchedGuidanceForks withEvidence withoutEvidence := by
  dsimp [ObservedGuidanceGain, MatchedGuidanceForks]
  exact ⟨by decide, fun matched => different matched.1⟩

end Mechanogenesis
