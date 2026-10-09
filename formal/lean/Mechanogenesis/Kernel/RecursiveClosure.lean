import Mechanogenesis.Kernel.Promotion
import Mechanogenesis.Kernel.Digest
import Lean.Data.Json.FromToJson

namespace Mechanogenesis

/-!
The sovereign semantics for finite Physical RSI evidence.

This module deliberately separates executable protocol checks from physical
identification assumptions.  A `PIPEWitness.Accepted` value establishes the
registered bindings and observed inequalities.  It becomes a causal claim only
through `IdentifiesPIPE`, whose premises must be justified by experiments.
-/

structure SuccessorIdentity where
  generatorHash : Digest
  runtimeHash : Digest
  protocolHash : Digest
  deriving DecidableEq, Repr, Lean.FromJson, Lean.ToJson

structure PhysicalTreatment where
  transitionHash : Digest
  treatmentHash : Digest
  parentWorldHash : Digest
  childWorldHash : Digest
  constructionLoss : Nat
  deriving DecidableEq, Repr, Lean.FromJson, Lean.ToJson

structure ImprovementOperatorSpec where
  specHash : Digest
  verifierHash : Digest
  resetProtocolHash : Digest
  horizon : Nat
  requiredGain : Nat
  deriving DecidableEq, Repr, Lean.FromJson, Lean.ToJson

structure CappedLoss where
  elapsed : Nat
  upperBound : Nat
  deriving DecidableEq, Repr, Lean.FromJson, Lean.ToJson

def CappedLoss.value (loss : CappedLoss) : Nat :=
  min loss.elapsed loss.upperBound

theorem capped_loss_is_total (loss : CappedLoss) :
    loss.value ≤ loss.upperBound := by
  unfold CappedLoss.value
  exact Nat.min_le_right _ _

structure ResourceVector where
  time : Nat
  material : Nat
  energy : Nat
  money : Nat
  compute : Nat
  human : Nat
  safetyViolations : Nat
  deriving DecidableEq, Repr, Lean.FromJson, Lean.ToJson

def ResourceVector.Within (used cap : ResourceVector) : Prop :=
  used.time ≤ cap.time ∧
  used.material ≤ cap.material ∧
  used.energy ≤ cap.energy ∧
  used.money ≤ cap.money ∧
  used.compute ≤ cap.compute ∧
  used.human ≤ cap.human ∧
  used.safetyViolations ≤ cap.safetyViolations

def ResourceVector.withinB (used cap : ResourceVector) : Bool :=
  used.time ≤ cap.time &&
  used.material ≤ cap.material &&
  used.energy ≤ cap.energy &&
  used.money ≤ cap.money &&
  used.compute ≤ cap.compute &&
  used.human ≤ cap.human &&
  used.safetyViolations ≤ cap.safetyViolations

structure ForkObservation where
  successor : SuccessorIdentity
  treatmentHash : Digest
  operatorSpecHash : Digest
  seedHash : Digest
  disturbanceHash : Digest
  evaluatorHash : Digest
  treatmentEnabled : Bool
  loss : CappedLoss
  resources : ResourceVector
  deriving DecidableEq, Repr, Lean.FromJson, Lean.ToJson

def MatchedPhysicalForks
    (withTreatment withoutTreatment : ForkObservation) : Prop :=
  withTreatment.successor = withoutTreatment.successor ∧
  withTreatment.treatmentHash = withoutTreatment.treatmentHash ∧
  withTreatment.operatorSpecHash = withoutTreatment.operatorSpecHash ∧
  withTreatment.seedHash = withoutTreatment.seedHash ∧
  withTreatment.disturbanceHash = withoutTreatment.disturbanceHash ∧
  withTreatment.evaluatorHash = withoutTreatment.evaluatorHash ∧
  withTreatment.treatmentEnabled = true ∧
  withoutTreatment.treatmentEnabled = false

def matchedPhysicalForksB
    (withTreatment withoutTreatment : ForkObservation) : Bool :=
  withTreatment.successor == withoutTreatment.successor &&
  withTreatment.treatmentHash == withoutTreatment.treatmentHash &&
  withTreatment.operatorSpecHash == withoutTreatment.operatorSpecHash &&
  withTreatment.seedHash == withoutTreatment.seedHash &&
  withTreatment.disturbanceHash == withoutTreatment.disturbanceHash &&
  withTreatment.evaluatorHash == withoutTreatment.evaluatorHash &&
  withTreatment.treatmentEnabled &&
  !withoutTreatment.treatmentEnabled

def ObservedPostTransitionEffect
    (withTreatment withoutTreatment : ForkObservation)
    (margin : Nat) : Prop :=
  0 < margin ∧
  withTreatment.loss.value + margin ≤ withoutTreatment.loss.value

def observedPostTransitionEffectB
    (withTreatment withoutTreatment : ForkObservation)
    (margin : Nat) : Bool :=
  0 < margin &&
  withTreatment.loss.value + margin ≤ withoutTreatment.loss.value

structure AncestorPathObservation where
  ancestorHash : Digest
  successor : SuccessorIdentity
  treatmentHash : Digest
  operatorSpecHash : Digest
  horizon : Nat
  physicalContributionLoss : Nat
  sequentialOperatorLoss : Nat
  resources : ResourceVector
  deriving DecidableEq, Repr, Lean.FromJson, Lean.ToJson

def AncestorPathObservation.totalLoss (path : AncestorPathObservation) : Nat :=
  path.physicalContributionLoss + path.sequentialOperatorLoss

def MatchedAncestorPaths
    (withTreatment withoutTreatment : AncestorPathObservation) : Prop :=
  withTreatment.ancestorHash = withoutTreatment.ancestorHash ∧
  withTreatment.successor = withoutTreatment.successor ∧
  withTreatment.treatmentHash = withoutTreatment.treatmentHash ∧
  withTreatment.operatorSpecHash = withoutTreatment.operatorSpecHash ∧
  withTreatment.horizon = withoutTreatment.horizon ∧
  0 < withTreatment.horizon

def matchedAncestorPathsB
    (withTreatment withoutTreatment : AncestorPathObservation) : Bool :=
  withTreatment.ancestorHash == withoutTreatment.ancestorHash &&
  withTreatment.successor == withoutTreatment.successor &&
  withTreatment.treatmentHash == withoutTreatment.treatmentHash &&
  withTreatment.operatorSpecHash == withoutTreatment.operatorSpecHash &&
  withTreatment.horizon == withoutTreatment.horizon &&
  0 < withTreatment.horizon

def ObservedAncestorLift
    (withTreatment withoutTreatment : AncestorPathObservation)
    (margin : Nat) : Prop :=
  0 < margin ∧
  withTreatment.totalLoss + margin ≤ withoutTreatment.totalLoss

def observedAncestorLiftB
    (withTreatment withoutTreatment : AncestorPathObservation)
    (margin : Nat) : Bool :=
  0 < margin &&
  withTreatment.totalLoss + margin ≤ withoutTreatment.totalLoss

structure RealizedOperator where
  operatorHash : Digest
  certificateHash : Digest
  verifierHash : Digest
  treatmentHandleHash : Digest
  deriving DecidableEq, Repr, Lean.FromJson, Lean.ToJson

structure PIPEWitness where
  treatment : PhysicalTreatment
  operatorSpec : ImprovementOperatorSpec
  withTreatmentFork : ForkObservation
  withoutTreatmentFork : ForkObservation
  withTreatmentPath : AncestorPathObservation
  withoutTreatmentPath : AncestorPathObservation
  realizedOperator : RealizedOperator
  postTransitionMargin : Nat
  ancestorLiftMargin : Nat
  resourceCap : ResourceVector
  deriving DecidableEq, Repr, Lean.FromJson, Lean.ToJson

def PIPEWitness.digestsValidB (witness : PIPEWitness) : Bool :=
  [
    witness.treatment.transitionHash,
    witness.treatment.treatmentHash,
    witness.treatment.parentWorldHash,
    witness.treatment.childWorldHash,
    witness.operatorSpec.specHash,
    witness.operatorSpec.verifierHash,
    witness.operatorSpec.resetProtocolHash,
    witness.withTreatmentFork.successor.generatorHash,
    witness.withTreatmentFork.successor.runtimeHash,
    witness.withTreatmentFork.successor.protocolHash,
    witness.withTreatmentFork.seedHash,
    witness.withTreatmentFork.disturbanceHash,
    witness.withTreatmentFork.evaluatorHash,
    witness.withTreatmentPath.ancestorHash,
    witness.realizedOperator.operatorHash,
    witness.realizedOperator.certificateHash,
    witness.realizedOperator.treatmentHandleHash
  ].all isSha256DigestB

def PIPEWitness.DigestsValid (witness : PIPEWitness) : Prop :=
  witness.digestsValidB = true

def PIPEWitness.SyntacticAdmissible (witness : PIPEWitness) : Prop :=
  witness.DigestsValid ∧
  2 ≤ witness.operatorSpec.horizon ∧
  0 < witness.operatorSpec.requiredGain ∧
  witness.operatorSpec.horizon = witness.withTreatmentPath.horizon ∧
  witness.treatment.treatmentHash = witness.withTreatmentFork.treatmentHash ∧
  witness.treatment.treatmentHash = witness.withTreatmentPath.treatmentHash ∧
  witness.operatorSpec.specHash = witness.withTreatmentFork.operatorSpecHash ∧
  witness.operatorSpec.specHash = witness.withTreatmentPath.operatorSpecHash ∧
  witness.realizedOperator.verifierHash = witness.operatorSpec.verifierHash ∧
  MatchedPhysicalForks witness.withTreatmentFork witness.withoutTreatmentFork ∧
  MatchedAncestorPaths witness.withTreatmentPath witness.withoutTreatmentPath

def PIPEWitness.syntacticAdmissibleB (witness : PIPEWitness) : Bool :=
  witness.digestsValidB &&
  2 ≤ witness.operatorSpec.horizon &&
  0 < witness.operatorSpec.requiredGain &&
  witness.operatorSpec.horizon == witness.withTreatmentPath.horizon &&
  witness.treatment.treatmentHash == witness.withTreatmentFork.treatmentHash &&
  witness.treatment.treatmentHash == witness.withTreatmentPath.treatmentHash &&
  witness.operatorSpec.specHash == witness.withTreatmentFork.operatorSpecHash &&
  witness.operatorSpec.specHash == witness.withTreatmentPath.operatorSpecHash &&
  witness.realizedOperator.verifierHash == witness.operatorSpec.verifierHash &&
  matchedPhysicalForksB witness.withTreatmentFork witness.withoutTreatmentFork &&
  matchedAncestorPathsB witness.withTreatmentPath witness.withoutTreatmentPath

def PIPEWitness.ObservedEffects (witness : PIPEWitness) : Prop :=
  ObservedPostTransitionEffect
    witness.withTreatmentFork witness.withoutTreatmentFork
    witness.postTransitionMargin ∧
  ObservedAncestorLift
    witness.withTreatmentPath witness.withoutTreatmentPath
    witness.ancestorLiftMargin ∧
  witness.withTreatmentFork.resources.Within witness.resourceCap ∧
  witness.withTreatmentPath.resources.Within witness.resourceCap

def PIPEWitness.observedEffectsB (witness : PIPEWitness) : Bool :=
  observedPostTransitionEffectB
    witness.withTreatmentFork witness.withoutTreatmentFork
    witness.postTransitionMargin &&
  observedAncestorLiftB
    witness.withTreatmentPath witness.withoutTreatmentPath
    witness.ancestorLiftMargin &&
  witness.withTreatmentFork.resources.withinB witness.resourceCap &&
  witness.withTreatmentPath.resources.withinB witness.resourceCap

/-- Executable acceptance is intentionally weaker than a real-world causal
claim.  The latter additionally requires `IdentificationAssumptions`. -/
def PIPEWitness.Accepted (witness : PIPEWitness) : Prop :=
  witness.SyntacticAdmissible ∧ witness.ObservedEffects

def checkPIPEProtocol (witness : PIPEWitness) : Bool :=
  witness.syntacticAdmissibleB && witness.observedEffectsB

def ValidPIPEProtocol (witness : PIPEWitness) : Prop :=
  checkPIPEProtocol witness = true

theorem pipe_protocol_checker_sound
    (witness : PIPEWitness)
    (accepted : checkPIPEProtocol witness = true) :
    witness.Accepted := by
  simp [checkPIPEProtocol, PIPEWitness.syntacticAdmissibleB,
    PIPEWitness.observedEffectsB, PIPEWitness.Accepted,
    PIPEWitness.SyntacticAdmissible, PIPEWitness.ObservedEffects,
    PIPEWitness.DigestsValid,
    matchedPhysicalForksB, MatchedPhysicalForks,
    matchedAncestorPathsB, MatchedAncestorPaths,
    observedPostTransitionEffectB, ObservedPostTransitionEffect,
    observedAncestorLiftB, ObservedAncestorLift,
    ResourceVector.withinB, ResourceVector.Within] at accepted ⊢
  simpa only [and_assoc] using accepted

structure IdentificationAssumptions (witness : PIPEWitness) where
  consistency : Prop
  treatmentIntegrity : Prop
  resetEquivalence : Prop
  noInterference : Prop
  operatorVerifierValid : Prop
  purgeComplete : Prop

def IdentificationAssumptions.Hold
    {witness : PIPEWitness}
    (assumptions : IdentificationAssumptions witness) : Prop :=
  assumptions.consistency ∧ assumptions.treatmentIntegrity ∧
  assumptions.resetEquivalence ∧ assumptions.noInterference ∧
  assumptions.operatorVerifierValid ∧ assumptions.purgeComplete

def IdentifiesPIPE
    (witness : PIPEWitness)
    (assumptions : IdentificationAssumptions witness) : Prop :=
  witness.Accepted ∧ assumptions.Hold

theorem accepted_pipe_binds_informational_inheritance
    (witness : PIPEWitness)
    (accepted : witness.Accepted) :
    witness.withTreatmentFork.successor =
      witness.withoutTreatmentFork.successor ∧
    witness.withTreatmentPath.successor =
      witness.withoutTreatmentPath.successor := by
  rcases accepted.1 with
    ⟨_, _, _, _, _, _, _, _, _, matchedForks, matchedPaths⟩
  exact ⟨matchedForks.1, matchedPaths.2.1⟩

theorem identified_pipe_exposes_assumptions
    (witness : PIPEWitness)
    (assumptions : IdentificationAssumptions witness)
    (identified : IdentifiesPIPE witness assumptions) :
    assumptions.consistency ∧ assumptions.treatmentIntegrity ∧
    assumptions.resetEquivalence ∧ assumptions.noInterference ∧
    assumptions.operatorVerifierValid ∧ assumptions.purgeComplete := by
  exact identified.2

/-! ### Countermodels -/

structure EndpointCausalModel where
  parentScore : Nat
  childScore : Nat
  treatmentOnLoss : Nat
  treatmentOffLoss : Nat
  deriving DecidableEq, Repr

def SameEndpoints (left right : EndpointCausalModel) : Prop :=
  left.parentScore = right.parentScore ∧
  left.childScore = right.childScore

def HasPositivePhysicalEffect (model : EndpointCausalModel) : Prop :=
  model.treatmentOnLoss < model.treatmentOffLoss

def endpointPositiveModel : EndpointCausalModel :=
  ⟨10, 5, 4, 7⟩

def endpointZeroModel : EndpointCausalModel :=
  ⟨10, 5, 4, 4⟩

theorem endpoint_scores_do_not_identify_physical_effect :
    SameEndpoints endpointPositiveModel endpointZeroModel ∧
    HasPositivePhysicalEffect endpointPositiveModel ∧
    ¬ HasPositivePhysicalEffect endpointZeroModel := by
  simp [SameEndpoints, HasPositivePhysicalEffect,
    endpointPositiveModel, endpointZeroModel]

structure ExposureModel where
  exposed : Bool
  treatmentOnLoss : Nat
  treatmentOffLoss : Nat
  deriving DecidableEq, Repr

def ExposureHasEffect (model : ExposureModel) : Prop :=
  model.treatmentOnLoss < model.treatmentOffLoss

def exposedPositiveModel : ExposureModel := ⟨true, 2, 5⟩
def exposedZeroModel : ExposureModel := ⟨true, 2, 2⟩

theorem exposure_receipt_does_not_identify_effect :
    exposedPositiveModel.exposed = exposedZeroModel.exposed ∧
    ExposureHasEffect exposedPositiveModel ∧
    ¬ ExposureHasEffect exposedZeroModel := by
  simp [ExposureHasEffect, exposedPositiveModel, exposedZeroModel]

structure FrontLoadingModel where
  preRevealLoss : Nat
  postRevealLoss : Nat
  deriving DecidableEq, Repr

def FrontLoadingModel.ancestorLoss (model : FrontLoadingModel) : Nat :=
  model.preRevealLoss + model.postRevealLoss

def frontLoadedTreatment : FrontLoadingModel := ⟨9, 1⟩
def noFrontLoadingControl : FrontLoadingModel := ⟨0, 10⟩

theorem post_reveal_gain_does_not_imply_ancestor_lift :
    frontLoadedTreatment.postRevealLoss < noFrontLoadingControl.postRevealLoss ∧
    frontLoadedTreatment.ancestorLoss = noFrontLoadingControl.ancestorLoss := by
  decide

structure SoftwareSubsidyModel where
  treatmentPathLoss : Nat
  oldGeneratorControlLoss : Nat
  frozenGeneratorControlLoss : Nat
  deriving DecidableEq, Repr

def subsidizedPhysicalTreatment : SoftwareSubsidyModel :=
  ⟨149, 200, 100⟩

theorem software_can_hide_negative_physical_net_value_without_binding :
    subsidizedPhysicalTreatment.treatmentPathLoss <
      subsidizedPhysicalTreatment.oldGeneratorControlLoss ∧
    subsidizedPhysicalTreatment.frozenGeneratorControlLoss <
      subsidizedPhysicalTreatment.treatmentPathLoss := by
  decide

/-! ### Observed-to-potential measurement bridge -/

structure PotentialOutcomePair where
  treatmentOnLoss : Nat
  treatmentOffLoss : Nat
  deriving DecidableEq, Repr

structure ObservedOutcomePair where
  treatmentOnLoss : Nat
  treatmentOffLoss : Nat
  deriving DecidableEq, Repr

def RealizesPotentialOutcomes
    (observed : ObservedOutcomePair)
    (potential : PotentialOutcomePair) : Prop :=
  observed.treatmentOnLoss = potential.treatmentOnLoss ∧
  observed.treatmentOffLoss = potential.treatmentOffLoss

theorem observed_strict_effect_transfers_to_registered_potential_outcomes
    (observed : ObservedOutcomePair)
    (potential : PotentialOutcomePair)
    (margin : Nat)
    (realizes : RealizesPotentialOutcomes observed potential)
    (strictObserved : observed.treatmentOnLoss + margin ≤ observed.treatmentOffLoss) :
    potential.treatmentOnLoss + margin ≤ potential.treatmentOffLoss := by
  rw [← realizes.1, ← realizes.2]
  exact strictObserved

/-! ### Exact finite closure -/

structure PIPECertificate where
  treatmentHash : Digest
  realizedOperatorHash : Digest
  witnessHash : Digest
  deriving DecidableEq, Repr

def PIPECertificate.Linked
    (earlier later : PIPECertificate) : Prop :=
  earlier.realizedOperatorHash = later.treatmentHash

def LinkedPIPEChain : List PIPECertificate → Prop
  | [] => True
  | [_] => True
  | earlier :: later :: rest =>
      earlier.Linked later ∧ LinkedPIPEChain (later :: rest)

structure PRSICertificate (depth : Nat) where
  witnesses : List PIPECertificate
  exactDepth : witnesses.length = depth
  recurrenceObserved : 2 ≤ depth
  linked : LinkedPIPEChain witnesses

theorem prsi_certificate_has_exact_observed_depth
    {depth : Nat}
    (certificate : PRSICertificate depth) :
    certificate.witnesses.length = depth := by
  exact certificate.exactDepth

theorem one_edge_cannot_receive_prsi_label
    (certificate : PRSICertificate 1) : False := by
  have impossible : ¬ (2 ≤ 1) := by decide
  exact impossible certificate.recurrenceObserved

end Mechanogenesis
