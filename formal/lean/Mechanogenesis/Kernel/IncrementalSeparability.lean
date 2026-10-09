import Lean.Elab.Tactic.Omega

namespace Mechanogenesis

/-!
`IncrementalSeparability` formalizes the decision boundary used by S0.1.

The file deliberately does not assert that a longer trace, an LLM explanation,
or an additional sensor is useful.  It proves a conditional finite statement:
grounded artifact estimates preserve a cost-adjusted true ordering only after
their observed gap exceeds twice the complete registered uncertainty budget.
When one public view is compatible with opposite hidden winners, no universally
sound strict selector exists; abstention is necessary.
-/

structure SeparabilityBudget where
  measurementError : Nat
  attributionError : Nat
  evaluatorShiftError : Nat
  recursiveCostError : Nat
  deriving DecidableEq, Repr

def SeparabilityBudget.total (budget : SeparabilityBudget) : Nat :=
  budget.measurementError + budget.attributionError +
    budget.evaluatorShiftError + budget.recursiveCostError

structure NetUtilityEstimate where
  trueNetUtility : Nat
  estimatedNetUtility : Nat
  deriving DecidableEq, Repr

def NetUtilityEstimate.Calibrated
    (estimate : NetUtilityEstimate)
    (budget : SeparabilityBudget) : Prop :=
  estimate.estimatedNetUtility ≤ estimate.trueNetUtility + budget.total ∧
  estimate.trueNetUtility ≤ estimate.estimatedNetUtility + budget.total

def IncrementallySeparated
    (better worse : NetUtilityEstimate)
    (budget : SeparabilityBudget) : Prop :=
  worse.estimatedNetUtility + 2 * budget.total <
    better.estimatedNetUtility

/--
The executable `2ε_total` rule.  The conclusion is about true cost-adjusted
utility, not merely an observed artifact score.  Every term in `ε_total` is an
explicit assumption: measurement, causal attribution, evaluator transfer and
recursive-cost estimation.
-/
theorem incremental_separability_preserves_true_net_order
    (better worse : NetUtilityEstimate)
    (budget : SeparabilityBudget)
    (betterCalibrated : better.Calibrated budget)
    (worseCalibrated : worse.Calibrated budget)
    (separated : IncrementallySeparated better worse budget) :
    worse.trueNetUtility < better.trueNetUtility := by
  rcases betterCalibrated with ⟨betterEstimateUpper, _⟩
  rcases worseCalibrated with ⟨_, worseTrueUpper⟩
  unfold IncrementallySeparated at separated
  omega

structure ArtifactView where
  leftEstimate : Nat
  rightEstimate : Nat
  deriving DecidableEq, Repr

structure HiddenNetWorld where
  leftTrueNet : Nat
  rightTrueNet : Nat
  deriving DecidableEq, Repr

def ArtifactView.Compatible
    (view : ArtifactView)
    (errorBound : Nat)
    (world : HiddenNetWorld) : Prop :=
  view.leftEstimate ≤ world.leftTrueNet + errorBound ∧
  world.leftTrueNet ≤ view.leftEstimate + errorBound ∧
  view.rightEstimate ≤ world.rightTrueNet + errorBound ∧
  world.rightTrueNet ≤ view.rightEstimate + errorBound

inductive SelectiveDecision where
  | promoteLeft
  | promoteRight
  | abstain
  deriving DecidableEq, Repr

def SelectiveDecision.SoundFor
    (decision : SelectiveDecision)
    (world : HiddenNetWorld) : Prop :=
  match decision with
  | .promoteLeft => world.rightTrueNet < world.leftTrueNet
  | .promoteRight => world.leftTrueNet < world.rightTrueNet
  | .abstain => True

/-- One unresolved artifact view can be compatible with two physical worlds
whose strict winners are opposite.  This is the finite separability obstruction
behind the benchmark's abstention rule. -/
theorem overlapping_artifact_view_has_opposite_compatible_worlds :
    let view : ArtifactView := ⟨1, 1⟩
    let leftWorld : HiddenNetWorld := ⟨2, 1⟩
    let rightWorld : HiddenNetWorld := ⟨1, 2⟩
    view.Compatible 1 leftWorld ∧
      view.Compatible 1 rightWorld ∧
      leftWorld.rightTrueNet < leftWorld.leftTrueNet ∧
      rightWorld.leftTrueNet < rightWorld.rightTrueNet := by
  dsimp [ArtifactView.Compatible]
  omega

/-- A deterministic decision that is sound for every world compatible with the
same unresolved view must abstain.  Adding an artifact therefore relaxes the
impossibility only when it actually separates the rival worlds; information
volume alone is insufficient. -/
theorem overlapping_artifact_view_forces_abstention
    (decision : SelectiveDecision)
    (leftSound : decision.SoundFor ⟨2, 1⟩)
    (rightSound : decision.SoundFor ⟨1, 2⟩) :
    decision = .abstain := by
  cases decision with
  | promoteLeft =>
      simp [SelectiveDecision.SoundFor] at rightSound
  | promoteRight =>
      simp [SelectiveDecision.SoundFor] at leftSound
  | abstain => rfl

abbrev ArtifactSelector := ArtifactView → SelectiveDecision

/-- General form of the identifiability obstruction.  The worlds and view are
not fixed examples: whenever one serialized view is compatible with two worlds
whose strict winners are opposite, any selector sound in both must abstain at
that view.  Compatibility records why the same input can denote both worlds;
soundness supplies the promotion obligation. -/
theorem opposite_compatible_worlds_force_abstention
    (view : ArtifactView)
    (errorBound : Nat)
    (leftWorld rightWorld : HiddenNetWorld)
    (selector : ArtifactSelector)
    (_leftCompatible : view.Compatible errorBound leftWorld)
    (_rightCompatible : view.Compatible errorBound rightWorld)
    (leftWins : leftWorld.rightTrueNet < leftWorld.leftTrueNet)
    (rightWins : rightWorld.leftTrueNet < rightWorld.rightTrueNet)
    (soundLeft : (selector view).SoundFor leftWorld)
    (soundRight : (selector view).SoundFor rightWorld) :
    selector view = .abstain := by
  cases decision : selector view with
  | promoteLeft =>
      simp [SelectiveDecision.SoundFor, decision] at soundRight
      omega
  | promoteRight =>
      simp [SelectiveDecision.SoundFor, decision] at soundLeft
      omega
  | abstain => rfl

/-- Equivalently, a strict non-abstaining selector cannot be sound on both
members of an opposite-winner collision class. -/
theorem no_sound_nonabstaining_selector_on_collision
    (view : ArtifactView)
    (errorBound : Nat)
    (leftWorld rightWorld : HiddenNetWorld)
    (selector : ArtifactSelector)
    (leftCompatible : view.Compatible errorBound leftWorld)
    (rightCompatible : view.Compatible errorBound rightWorld)
    (leftWins : leftWorld.rightTrueNet < leftWorld.leftTrueNet)
    (rightWins : rightWorld.leftTrueNet < rightWorld.rightTrueNet) :
    ¬ ((selector view).SoundFor leftWorld ∧
       (selector view).SoundFor rightWorld ∧
       selector view ≠ .abstain) := by
  intro claimed
  rcases claimed with ⟨soundLeft, soundRight, nonabstaining⟩
  exact nonabstaining (opposite_compatible_worlds_force_abstention
    view errorBound leftWorld rightWorld selector leftCompatible rightCompatible
    leftWins rightWins soundLeft soundRight)

structure SplitConformalReceipt where
  fitSetId : Nat
  calibrationSetId : Nat
  calibrationTaskCount : Nat
  alphaPPM : Nat
  simultaneousArmScore : Bool
  deriving DecidableEq, Repr

def SplitConformalReceipt.validB (receipt : SplitConformalReceipt) : Bool :=
  decide (receipt.fitSetId ≠ receipt.calibrationSetId) &&
  decide (0 < receipt.calibrationTaskCount) &&
  decide (0 < receipt.alphaPPM) &&
  decide (receipt.alphaPPM < 1000000) &&
  receipt.simultaneousArmScore

theorem accepted_split_conformal_receipt_exposes_runtime_requirements
    (receipt : SplitConformalReceipt)
    (checked : receipt.validB = true) :
    receipt.fitSetId ≠ receipt.calibrationSetId ∧
    0 < receipt.calibrationTaskCount ∧
    0 < receipt.alphaPPM ∧
    receipt.alphaPPM < 1000000 ∧
    receipt.simultaneousArmScore = true := by
  unfold SplitConformalReceipt.validB at checked
  simp only [Bool.and_eq_true, decide_eq_true_eq] at checked
  rcases checked with ⟨⟨⟨⟨fitDistinct, countPositive⟩, alphaPositive⟩,
    alphaBounded⟩, simultaneous⟩
  exact ⟨fitDistinct, countPositive, alphaPositive, alphaBounded, simultaneous⟩

/-- The statistical layer proposes an error radius.  Lean deliberately proves
only the deterministic conditional: on a future task where the simultaneous
arm-error event holds, the same `2ε` gate certifies true order.  Exchangeability
and the probability of this event belong to the experiment contract. -/
theorem conformal_event_and_separation_certifies_true_order
    (receipt : SplitConformalReceipt)
    (better worse : NetUtilityEstimate)
    (budget : SeparabilityBudget)
    (_receiptValid : receipt.validB = true)
    (betterCovered : better.Calibrated budget)
    (worseCovered : worse.Calibrated budget)
    (separated : IncrementallySeparated better worse budget) :
    worse.trueNetUtility < better.trueNetUtility := by
  exact incremental_separability_preserves_true_net_order
    better worse budget betterCovered worseCovered separated

structure RecursiveCost where
  probeCost : Nat
  generatorUpdateCost : Nat
  losingForkEvaluationCost : Nat
  deploymentCost : Nat
  deriving DecidableEq, Repr

def RecursiveCost.total (cost : RecursiveCost) : Nat :=
  cost.probeCost + cost.generatorUpdateCost +
    cost.losingForkEvaluationCost + cost.deploymentCost

def PositiveRecursiveValue (grossFutureGain : Nat) (cost : RecursiveCost) : Prop :=
  cost.total < grossFutureGain

theorem full_recursive_cost_blocks_nonpositive_candidate
    (grossFutureGain : Nat)
    (cost : RecursiveCost)
    (costDominates : grossFutureGain ≤ cost.total) :
    ¬ PositiveRecursiveValue grossFutureGain cost := by
  unfold PositiveRecursiveValue
  omega

structure IncrementalSeparabilityCertificate where
  groundingEvidenceCount : Nat
  independentCheckCount : Nat
  attributionContrastCount : Nat
  creditProcessHadFinalAccess : Bool
  decisionAttestedBeforeReveal : Bool
  exactStrategyExecution : Bool
  behavioralTieAbstention : Bool
  allGeneratedForksCharged : Bool
  allCreditAndFinalInferenceCharged : Bool
  worseEstimate : Nat
  betterEstimate : Nat
  errorBudget : SeparabilityBudget
  claimedTotalErrorBound : Nat
  grossFutureGain : Nat
  recursiveCost : RecursiveCost
  claimedFullRecursiveCost : Nat
  deriving DecidableEq, Repr

def IncrementalSeparabilityCertificate.validB
    (certificate : IncrementalSeparabilityCertificate) : Bool :=
  decide (0 < certificate.groundingEvidenceCount) &&
  decide (0 < certificate.independentCheckCount) &&
  decide (0 < certificate.attributionContrastCount) &&
  decide (certificate.creditProcessHadFinalAccess = false) &&
  certificate.decisionAttestedBeforeReveal &&
  certificate.exactStrategyExecution &&
  certificate.behavioralTieAbstention &&
  certificate.allGeneratedForksCharged &&
  certificate.allCreditAndFinalInferenceCharged &&
  decide (certificate.claimedTotalErrorBound = certificate.errorBudget.total) &&
  decide (certificate.claimedFullRecursiveCost = certificate.recursiveCost.total) &&
  decide (
    certificate.worseEstimate + 2 * certificate.claimedTotalErrorBound <
      certificate.betterEstimate) &&
  decide (certificate.claimedFullRecursiveCost < certificate.grossFutureGain)

def IncrementalSeparabilityCertificate.ProtocolValid
    (certificate : IncrementalSeparabilityCertificate) : Prop :=
  certificate.validB = true

def checkIncrementalSeparability
    (certificate : IncrementalSeparabilityCertificate) : Bool :=
  certificate.validB

theorem incremental_separability_checker_sound
    (certificate : IncrementalSeparabilityCertificate)
    (checked : checkIncrementalSeparability certificate = true) :
    certificate.ProtocolValid := by
  exact checked

/-- Checker acceptance exposes the algorithm's complete finite promotion gate.
It cannot silently omit grounding, independent checking, attribution, the
two-error threshold, or positive net value. -/
theorem accepted_incremental_certificate_exposes_promotion_requirements
    (certificate : IncrementalSeparabilityCertificate)
    (checked : checkIncrementalSeparability certificate = true) :
    0 < certificate.groundingEvidenceCount ∧
    0 < certificate.independentCheckCount ∧
    0 < certificate.attributionContrastCount ∧
    certificate.creditProcessHadFinalAccess = false ∧
    certificate.decisionAttestedBeforeReveal = true ∧
    certificate.exactStrategyExecution = true ∧
    certificate.behavioralTieAbstention = true ∧
    certificate.allGeneratedForksCharged = true ∧
    certificate.allCreditAndFinalInferenceCharged = true ∧
    certificate.claimedTotalErrorBound = certificate.errorBudget.total ∧
    certificate.claimedFullRecursiveCost = certificate.recursiveCost.total ∧
    certificate.worseEstimate + 2 * certificate.claimedTotalErrorBound <
      certificate.betterEstimate ∧
    certificate.claimedFullRecursiveCost < certificate.grossFutureGain := by
  unfold checkIncrementalSeparability at checked
  unfold IncrementalSeparabilityCertificate.validB at checked
  simp only [Bool.and_eq_true, decide_eq_true_eq] at checked
  rcases checked with
    ⟨⟨⟨⟨⟨⟨⟨⟨⟨⟨⟨⟨grounded, independent⟩, attributed⟩,
      noFinalAccess⟩, attested⟩, exactExecution⟩, tieAbstention⟩,
      forksCharged⟩, inferenceCharged⟩, errorAccounted⟩,
      costAccounted⟩, separated⟩, positive⟩
  exact ⟨grounded, independent, attributed, noFinalAccess, attested,
    exactExecution, tieAbstention, forksCharged, inferenceCharged,
    errorAccounted, costAccounted, separated, positive⟩

end Mechanogenesis
