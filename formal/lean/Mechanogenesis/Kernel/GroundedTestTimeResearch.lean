import Lean.Elab.Tactic.Omega

namespace Mechanogenesis

/-!
`GroundedTestTimeResearch` gives the finite proof boundary for adapting a
research-strategy generator during a task.  It is intentionally not a theorem
that gradient descent, an LLM, or a world model will improve.  Instead it
derives the observations and gates that a claimed improvement must expose.

The key distinction is between a low training loss and evaluator-owned future
utility.  A batch-dependent target is not a function of the task view, and an
unchanged training-loss view can be compatible with opposite query winners.
Grounded promotion therefore uses task-local counterfactual receipts, an
isolated actual-versus-placebo update, a sealed query, a complete uncertainty
budget, and full adaptation cost.
-/

/-! ## Targets must be task-local -/

abbrev TaskOnlyGenerator (Task Label : Type) := Task → Label

/-- If the desired label for one task changes when only the surrounding batch
context changes, no generator that receives only the task can match both
labels.  This is the exact obstruction in a batch-global quota assignment. -/
theorem batch_dependent_target_cannot_be_task_learned
    {Task Batch Label : Type}
    (target : Task → Batch → Label)
    (generator : TaskOnlyGenerator Task Label)
    (task : Task)
    (leftBatch rightBatch : Batch)
    (targetChanges : target task leftBatch ≠ target task rightBatch) :
    ¬ (generator task = target task leftBatch ∧
       generator task = target task rightBatch) := by
  intro fitsBoth
  apply targetChanges
  calc
    target task leftBatch = generator task := fitsBoth.1.symm
    _ = target task rightBatch := fitsBoth.2

/-! ## Training loss does not identify future adaptation value -/

inductive AdaptationDecision where
  | keepParent
  | applyUpdate
  | abstain
  deriving DecidableEq, Repr

structure QueryUtilityWorld where
  parentUtility : Nat
  updatedUtility : Nat
  deriving DecidableEq, Repr

def AdaptationDecision.SoundFor
    (decision : AdaptationDecision)
    (world : QueryUtilityWorld) : Prop :=
  match decision with
  | .keepParent => world.updatedUtility < world.parentUtility
  | .applyUpdate => world.parentUtility < world.updatedUtility
  | .abstain => True

abbrev LossOnlyAdaptationSelector := Nat → Nat → AdaptationDecision

/-- Even exact knowledge of two training losses cannot select the better
future generator without a linking premise: the same loss pair can denote two
query worlds whose strict winners are opposite.  A selector sound in both must
abstain. -/
theorem same_training_losses_opposite_query_worlds_force_abstention
    (selector : LossOnlyAdaptationSelector)
    (parentTrainingLoss updatedTrainingLoss : Nat)
    (lowerUtility higherUtility : Nat)
    (strictGap : lowerUtility < higherUtility)
    (soundWhenParentWins :
      (selector parentTrainingLoss updatedTrainingLoss).SoundFor
        ⟨higherUtility, lowerUtility⟩)
    (soundWhenUpdateWins :
      (selector parentTrainingLoss updatedTrainingLoss).SoundFor
        ⟨lowerUtility, higherUtility⟩) :
    selector parentTrainingLoss updatedTrainingLoss = .abstain := by
  cases decision : selector parentTrainingLoss updatedTrainingLoss with
  | keepParent =>
      simp [AdaptationDecision.SoundFor, decision] at soundWhenUpdateWins
      omega
  | applyUpdate =>
      simp [AdaptationDecision.SoundFor, decision] at soundWhenParentWins
      omega
  | abstain => rfl

/-! A support transcript helps a later query only through structure shared by
the registered episode.  If the identical transcript remains compatible with
opposite query winners, no universally sound strict test-time update exists. -/

abbrev SupportTranscript := Nat
abbrev TranscriptOnlyAdapter := SupportTranscript → AdaptationDecision

theorem support_query_collision_forces_test_time_abstention
    (adapter : TranscriptOnlyAdapter)
    (transcript : SupportTranscript)
    (lowerUtility higherUtility : Nat)
    (strictGap : lowerUtility < higherUtility)
    (soundWhenParentWins :
      (adapter transcript).SoundFor ⟨higherUtility, lowerUtility⟩)
    (soundWhenUpdateWins :
      (adapter transcript).SoundFor ⟨lowerUtility, higherUtility⟩) :
    adapter transcript = .abstain := by
  cases decision : adapter transcript with
  | keepParent =>
      simp [AdaptationDecision.SoundFor, decision] at soundWhenUpdateWins
      omega
  | applyUpdate =>
      simp [AdaptationDecision.SoundFor, decision] at soundWhenParentWins
      omega
  | abstain => rfl

def PreDecisionAccessCostFaithful
    (probeReadingExposed : Bool)
    (registeredProbeCost chargedResearchCost : Nat) : Prop :=
  probeReadingExposed = true → registeredProbeCost ≤ chargedResearchCost

/-- A positive-cost physical observation cannot be exposed before the action
while charging zero research cost.  This catches a subtle prompt/evaluator
leak: evidence timing is part of physical semantics, not prompt decoration. -/
theorem positive_cost_probe_cannot_be_free_predecision_evidence
    (registeredProbeCost : Nat)
    (positiveCost : 0 < registeredProbeCost) :
    ¬ PreDecisionAccessCostFaithful true registeredProbeCost 0 := by
  intro claimed
  have charged := claimed rfl
  omega

/-! ## Grounded promotion threshold -/

structure GroundedAdaptationErrorBudget where
  physicalAccessError : Nat
  worldModelError : Nat
  causalAttributionError : Nat
  queryShiftError : Nat
  executionError : Nat
  deriving DecidableEq, Repr

def GroundedAdaptationErrorBudget.total
    (budget : GroundedAdaptationErrorBudget) : Nat :=
  budget.physicalAccessError + budget.worldModelError +
    budget.causalAttributionError + budget.queryShiftError +
    budget.executionError

structure GroundedUtilityEstimate where
  trueUtility : Nat
  estimatedUtility : Nat
  deriving DecidableEq, Repr

def GroundedUtilityEstimate.Calibrated
    (estimate : GroundedUtilityEstimate)
    (budget : GroundedAdaptationErrorBudget) : Prop :=
  estimate.estimatedUtility ≤ estimate.trueUtility + budget.total ∧
  estimate.trueUtility ≤ estimate.estimatedUtility + budget.total

def groundedPromotionThreshold
    (budget : GroundedAdaptationErrorBudget)
    (adaptationCostUpper : Nat) : Nat :=
  2 * budget.total + adaptationCostUpper

def GroundedNetSeparated
    (parent updated : GroundedUtilityEstimate)
    (budget : GroundedAdaptationErrorBudget)
    (adaptationCostUpper : Nat) : Prop :=
  parent.estimatedUtility +
      groundedPromotionThreshold budget adaptationCostUpper <
    updated.estimatedUtility

/-- A calibrated observed gap above `2ε + cost` certifies strict positive
query net value.  `actualAdaptationCost ≤ adaptationCostUpper` prevents an
unreported training, inference, experiment, or rollback cost from entering
through the conclusion. -/
theorem grounded_net_separation_certifies_positive_query_value
    (parent updated : GroundedUtilityEstimate)
    (budget : GroundedAdaptationErrorBudget)
    (actualAdaptationCost adaptationCostUpper : Nat)
    (parentCalibrated : parent.Calibrated budget)
    (updatedCalibrated : updated.Calibrated budget)
    (costCovered : actualAdaptationCost ≤ adaptationCostUpper)
    (separated :
      GroundedNetSeparated parent updated budget adaptationCostUpper) :
    parent.trueUtility + actualAdaptationCost < updated.trueUtility := by
  rcases parentCalibrated with ⟨_, parentTrueUpper⟩
  rcases updatedCalibrated with ⟨updatedEstimateUpper, _⟩
  unfold GroundedNetSeparated groundedPromotionThreshold at separated
  omega

/-- Receipt attribution needs a second isolated comparison.  If the actual
grounded-receipt update is separated from a matched placebo update by `2ε`,
calibration certifies that the actual update has strictly higher query utility.
-/
theorem grounded_receipt_separation_certifies_placebo_advantage
    (placebo actual : GroundedUtilityEstimate)
    (budget : GroundedAdaptationErrorBudget)
    (placeboCalibrated : placebo.Calibrated budget)
    (actualCalibrated : actual.Calibrated budget)
    (separated :
      placebo.estimatedUtility + 2 * budget.total <
        actual.estimatedUtility) :
    placebo.trueUtility < actual.trueUtility := by
  rcases placeboCalibrated with ⟨_, placeboTrueUpper⟩
  rcases actualCalibrated with ⟨actualEstimateUpper, _⟩
  omega

/-! ## Access--intelligence spiral -/

structure ResearchIterationThreshold where
  uncertainty : Nat
  fullUpdateCost : Nat
  deriving DecidableEq, Repr

def ResearchIterationThreshold.total
    (threshold : ResearchIterationThreshold) : Nat :=
  2 * threshold.uncertainty + threshold.fullUpdateCost

def ResearchIterationThreshold.Certifies
    (threshold : ResearchIterationThreshold)
    (parentEstimate updatedEstimate : Nat) : Prop :=
  parentEstimate + threshold.total < updatedEstimate

/-- Better access/model calibration or cheaper adaptation weakly expands the
set of observed gaps that can be certified.  The theorem is conditional: it
does not assume that later iterations automatically improve either quantity.
-/
theorem lower_uncertainty_and_cost_expand_certifiable_support
    (oldState newState : ResearchIterationThreshold)
    (parentEstimate updatedEstimate : Nat)
    (uncertaintyImproves : newState.uncertainty ≤ oldState.uncertainty)
    (costImproves : newState.fullUpdateCost ≤ oldState.fullUpdateCost)
    (oldCertified : oldState.Certifies parentEstimate updatedEstimate) :
    newState.Certifies parentEstimate updatedEstimate := by
  unfold ResearchIterationThreshold.Certifies
    ResearchIterationThreshold.total at *
  omega

/-- An irreducible physical-access ambiguity lower-bounds the promotion
threshold.  Reducing only world-model or optimizer error cannot push the total
threshold below this access floor. -/
theorem physical_access_error_sets_threshold_floor
    (budget : GroundedAdaptationErrorBudget)
    (accessFloor adaptationCostUpper : Nat)
    (floorValid : accessFloor ≤ budget.physicalAccessError) :
    2 * accessFloor + adaptationCostUpper ≤
      groundedPromotionThreshold budget adaptationCostUpper := by
  unfold groundedPromotionThreshold GroundedAdaptationErrorBudget.total
  omega

def AmortizedQueryGain (queryCount perQueryGain : Nat) : Nat :=
  queryCount * perQueryGain

/-- A test-time update may be useful only after enough downstream constructions
share the learned regime.  If its full one-off cost dominates the accumulated
per-query gain, positive recursive value is impossible at that horizon. -/
theorem insufficient_amortization_horizon_blocks_positive_value
    (queryCount perQueryGain fullUpdateCost : Nat)
    (costDominates :
      AmortizedQueryGain queryCount perQueryGain ≤ fullUpdateCost) :
    ¬ (fullUpdateCost < AmortizedQueryGain queryCount perQueryGain) := by
  omega

/-- Conversely, the strict registered break-even inequality is exactly the
finite positive-value witness for an amortized episode. -/
theorem sufficient_amortization_horizon_has_positive_value
    (queryCount perQueryGain fullUpdateCost : Nat)
    (breakEvenPassed :
      fullUpdateCost < AmortizedQueryGain queryCount perQueryGain) :
    fullUpdateCost < AmortizedQueryGain queryCount perQueryGain := by
  exact breakEvenPassed

/-- If one paid support probe costs exactly as much as the probe avoided on one
downstream query, a one-query deployment has zero strict physical gain. -/
theorem one_paid_probe_one_query_has_no_strict_physical_gain
    (probeCost : Nat) :
    ¬ (probeCost < AmortizedQueryGain 1 probeCost) := by
  unfold AmortizedQueryGain
  omega

/-- Under the same registered cost equality, two queries sharing the learned
physical regime are the first integer horizon with strict physical gain.  GPU,
token, calibration, and access errors remain costs in the full certificate. -/
theorem one_paid_probe_two_queries_has_strict_physical_gain
    (probeCost : Nat)
    (positiveProbeCost : 0 < probeCost) :
    probeCost < AmortizedQueryGain 2 probeCost := by
  unfold AmortizedQueryGain
  omega

/-! ## Training-process checkpoints

The final benchmark query cannot be used for early stopping.  Meta-training
therefore uses a disjoint held-out validation population.  A checkpoint is not
accepted because token loss fell; it is accepted only when calibrated
validation utility covers the full transition cost.  The individual metrics
below are retained because they diagnose which error-budget component failed.
-/

structure GroundedTrainingMetrics where
  supervisedTokenLossMicros : Nat
  policyRankingErrorCount : Nat
  policyMarginMicros : Nat
  executableFailureCount : Nat
  accessTargetViolationCount : Nat
  freeEvidenceCostViolationCount : Nat
  worldModelError : Nat
  calibrationRadius : Nat
  matchedPlaceboGap : Nat
  supportQueryTransferGain : Nat
  heldoutValidationUtilityEstimate : Nat
  cumulativeUpdateCost : Nat
  deriving DecidableEq, Repr

def PolicyMarginSeparated
    (targetLoss competitorLoss requiredMargin : Nat) : Prop :=
  targetLoss + requiredMargin < competitorLoss

/-- Even a zero target token loss does not identify a unique policy: a
competitor can have the same loss.  Therefore token SFT loss cannot substitute
for evaluator-owned policy ranking or a positive decision margin. -/
theorem zero_target_token_loss_does_not_force_policy_identification :
    ∃ targetLoss competitorLoss : Nat,
      targetLoss = 0 ∧ ¬ (targetLoss < competitorLoss) := by
  exact ⟨0, 0, rfl, by omega⟩

/-- A registered positive ranking margin does identify the target against the
scored competitor.  This is the condition optimized by the contrastive
meta-policy objective after token-only SFT fails. -/
theorem positive_policy_margin_certifies_target_preference
    (targetLoss competitorLoss requiredMargin : Nat)
    (separated :
      PolicyMarginSeparated targetLoss competitorLoss requiredMargin) :
    targetLoss < competitorLoss := by
  unfold PolicyMarginSeparated at separated
  omega

structure LearnedEvidenceCut where
  largestObservedLow : Nat
  smallestObservedHigh : Nat
  cut : Nat
  deriving DecidableEq, Repr

def LearnedEvidenceCut.separatesTrainingGap
    (model : LearnedEvidenceCut) : Prop :=
  model.largestObservedLow < model.cut ∧
  model.cut ≤ model.smallestObservedHigh

/-- A nonempty evaluator-owned intervention gap constructs an explicit
evidence separator without assuming a handwritten physical threshold. -/
theorem observed_intervention_gap_constructs_separator
    (largestObservedLow smallestObservedHigh : Nat)
    (gap : largestObservedLow < smallestObservedHigh) :
    (LearnedEvidenceCut.mk largestObservedLow smallestObservedHigh
      smallestObservedHigh).separatesTrainingGap := by
  constructor
  · exact gap
  · exact Nat.le_refl _

/-- The learned cut transfers to any new receipt that remains on the certified
side of the gap.  This exposes the exact assumption that later calibration
must test under sensor error and distribution shift. -/
theorem learned_evidence_cut_classifies_bounded_receipts
    (model : LearnedEvidenceCut)
    (lowReceipt highReceipt : Nat)
    (modelValid : model.separatesTrainingGap)
    (lowBound : lowReceipt ≤ model.largestObservedLow)
    (highBound : model.smallestObservedHigh ≤ highReceipt) :
    lowReceipt < model.cut ∧ model.cut ≤ highReceipt := by
  rcases modelValid with ⟨lowGap, highGap⟩
  omega

def CertifiedLowEvidence (reading cut errorBound : Nat) : Prop :=
  reading + errorBound < cut

def CertifiedHighEvidence (reading cut errorBound : Nat) : Prop :=
  cut + errorBound ≤ reading

/-- The low and high certified regions of a positive-width evidence band are
disjoint.  A controller cannot soundly issue both physical states. -/
theorem certified_evidence_regions_are_disjoint
    (reading cut errorBound : Nat) :
    ¬ (CertifiedLowEvidence reading cut errorBound ∧
      CertifiedHighEvidence reading cut errorBound) := by
  unfold CertifiedLowEvidence CertifiedHighEvidence
  omega

/-- A reading exactly at the learned cut is outside both certified regions
whenever the registered measurement error is positive.  The executable
controller must therefore abstain/fall back to a new probe. -/
theorem cut_reading_forces_evidence_abstention
    (cut errorBound : Nat)
    (positiveError : 0 < errorBound) :
    ¬ CertifiedLowEvidence cut cut errorBound ∧
    ¬ CertifiedHighEvidence cut cut errorBound := by
  unfold CertifiedLowEvidence CertifiedHighEvidence
  omega

def FreezeBeforeReveal (freezeOrdinal revealOrdinal : Nat) : Prop :=
  freezeOrdinal < revealOrdinal

/-- A sealed evaluation receipt is admissible only when the adapter/model
freeze event strictly precedes secret-seed reveal. -/
theorem accepted_sealed_evaluation_exposes_freeze_before_reveal
    (freezeOrdinal revealOrdinal : Nat)
    (accepted : FreezeBeforeReveal freezeOrdinal revealOrdinal) :
    freezeOrdinal < revealOrdinal := by
  exact accepted

/-- With one support probe replacing one probe per downstream query, four
distinct queries recover exactly three probe costs. -/
theorem one_paid_probe_four_queries_recovers_three_probe_costs
    (probeCost : Nat) :
    probeCost + 3 * probeCost = AmortizedQueryGain 4 probeCost := by
  unfold AmortizedQueryGain
  omega

theorem one_paid_probe_four_queries_has_strict_physical_gain
    (probeCost : Nat)
    (positiveProbeCost : 0 < probeCost) :
    probeCost < AmortizedQueryGain 4 probeCost := by
  unfold AmortizedQueryGain
  omega

structure TrainingCheckpointEstimate where
  trueValidationUtility : Nat
  estimatedValidationUtility : Nat
  errorRadius : Nat
  deriving DecidableEq, Repr

def TrainingCheckpointEstimate.Calibrated
    (checkpoint : TrainingCheckpointEstimate) : Prop :=
  checkpoint.estimatedValidationUtility ≤
      checkpoint.trueValidationUtility + checkpoint.errorRadius ∧
  checkpoint.trueValidationUtility ≤
      checkpoint.estimatedValidationUtility + checkpoint.errorRadius

def ValidationCheckpointSeparated
    (parent candidate : TrainingCheckpointEstimate)
    (transitionCostUpper : Nat) : Prop :=
  parent.estimatedValidationUtility + parent.errorRadius +
      transitionCostUpper + candidate.errorRadius <
    candidate.estimatedValidationUtility

/-- This is the training-time analogue of the final promotion theorem.  It
licenses retaining a candidate checkpoint on a reusable validation split, not
claiming final-query improvement. -/
theorem validation_checkpoint_separation_certifies_net_improvement
    (parent candidate : TrainingCheckpointEstimate)
    (actualTransitionCost transitionCostUpper : Nat)
    (parentCalibrated : parent.Calibrated)
    (candidateCalibrated : candidate.Calibrated)
    (costCovered : actualTransitionCost ≤ transitionCostUpper)
    (separated :
      ValidationCheckpointSeparated parent candidate transitionCostUpper) :
    parent.trueValidationUtility + actualTransitionCost <
      candidate.trueValidationUtility := by
  rcases parentCalibrated with ⟨_, parentTrueUpper⟩
  rcases candidateCalibrated with ⟨candidateEstimateUpper, _⟩
  unfold ValidationCheckpointSeparated at separated
  omega

structure TrainingStepReceipt where
  parentCheckpointBound : Bool
  childCheckpointBound : Bool
  supportSplitBound : Bool
  validationSplitBound : Bool
  supportValidationDisjoint : Bool
  finalQueryUnread : Bool
  evaluatorOwnedSupervision : Bool
  targetIsFunctionOfDeclaredAccess : Bool
  preDecisionAccessIntegrity : Bool
  beliefDistributionCommitted : Bool
  supportQueryRegimeBound : Bool
  optimizerAndSeedBound : Bool
  actualPlaceboUpdatesMatched : Bool
  allTokensExperimentsAndGpuCosted : Bool
  updateStepCount : Nat
  supportTaskCount : Nat
  validationTaskCount : Nat
  metrics : GroundedTrainingMetrics
  deriving DecidableEq, Repr

def TrainingStepReceipt.validB (receipt : TrainingStepReceipt) : Bool :=
  receipt.parentCheckpointBound &&
  receipt.childCheckpointBound &&
  receipt.supportSplitBound &&
  receipt.validationSplitBound &&
  receipt.supportValidationDisjoint &&
  receipt.finalQueryUnread &&
  receipt.evaluatorOwnedSupervision &&
  receipt.targetIsFunctionOfDeclaredAccess &&
  receipt.preDecisionAccessIntegrity &&
  receipt.beliefDistributionCommitted &&
  receipt.supportQueryRegimeBound &&
  receipt.optimizerAndSeedBound &&
  receipt.actualPlaceboUpdatesMatched &&
  receipt.allTokensExperimentsAndGpuCosted &&
  decide (0 < receipt.updateStepCount) &&
  decide (0 < receipt.supportTaskCount) &&
  decide (0 < receipt.validationTaskCount)

/-- The observed token loss is deliberately exposed but absent from the
acceptance predicate.  It is a diagnostic of optimization, not evidence of
future research utility. -/
theorem accepted_training_step_exposes_process_not_loss_claim
    (receipt : TrainingStepReceipt)
    (accepted : receipt.validB = true) :
    receipt.parentCheckpointBound = true ∧
    receipt.childCheckpointBound = true ∧
    receipt.supportSplitBound = true ∧
    receipt.validationSplitBound = true ∧
    receipt.supportValidationDisjoint = true ∧
    receipt.finalQueryUnread = true ∧
    receipt.evaluatorOwnedSupervision = true ∧
    receipt.targetIsFunctionOfDeclaredAccess = true ∧
    receipt.preDecisionAccessIntegrity = true ∧
    receipt.beliefDistributionCommitted = true ∧
    receipt.supportQueryRegimeBound = true ∧
    receipt.optimizerAndSeedBound = true ∧
    receipt.actualPlaceboUpdatesMatched = true ∧
    receipt.allTokensExperimentsAndGpuCosted = true ∧
    0 < receipt.updateStepCount ∧
    0 < receipt.supportTaskCount ∧
    0 < receipt.validationTaskCount := by
  unfold TrainingStepReceipt.validB at accepted
  simp only [Bool.and_eq_true, decide_eq_true_eq] at accepted
  simpa only [and_assoc] using accepted

/-! ## Executable contracts -/

structure GroundedTrainingContract where
  taskCount : Nat
  armCount : Nat
  targetIsFunctionOfDeclaredAccess : Bool
  globalQuotaFree : Bool
  beliefDistributionCommitted : Bool
  completeCounterfactualTable : Bool
  allArmsBoundToSameTask : Bool
  evaluatorOwnedOutcomes : Bool
  exactExecutableStrategies : Bool
  preDecisionAccessIntegrity : Bool
  supportQueryRegimeBound : Bool
  supportQueryDisjoint : Bool
  queryUnreadDuringUpdate : Bool
  deriving DecidableEq, Repr

def GroundedTrainingContract.validB
    (contract : GroundedTrainingContract) : Bool :=
  decide (0 < contract.taskCount) &&
  decide (1 < contract.armCount) &&
  contract.targetIsFunctionOfDeclaredAccess &&
  contract.globalQuotaFree &&
  contract.beliefDistributionCommitted &&
  contract.completeCounterfactualTable &&
  contract.allArmsBoundToSameTask &&
  contract.evaluatorOwnedOutcomes &&
  contract.exactExecutableStrategies &&
  contract.preDecisionAccessIntegrity &&
  contract.supportQueryRegimeBound &&
  contract.supportQueryDisjoint &&
  contract.queryUnreadDuringUpdate

theorem accepted_grounded_training_contract_exposes_requirements
    (contract : GroundedTrainingContract)
    (accepted : contract.validB = true) :
    0 < contract.taskCount ∧
    1 < contract.armCount ∧
    contract.targetIsFunctionOfDeclaredAccess = true ∧
    contract.globalQuotaFree = true ∧
    contract.beliefDistributionCommitted = true ∧
    contract.completeCounterfactualTable = true ∧
    contract.allArmsBoundToSameTask = true ∧
    contract.evaluatorOwnedOutcomes = true ∧
    contract.exactExecutableStrategies = true ∧
    contract.preDecisionAccessIntegrity = true ∧
    contract.supportQueryRegimeBound = true ∧
    contract.supportQueryDisjoint = true ∧
    contract.queryUnreadDuringUpdate = true := by
  unfold GroundedTrainingContract.validB at accepted
  simp only [Bool.and_eq_true, decide_eq_true_eq] at accepted
  simpa only [and_assoc] using accepted

structure GroundedPromotionCertificate where
  evaluatorOwnedSupportReceipts : Bool
  actualPlaceboForksMatched : Bool
  preDecisionAccessIntegrity : Bool
  supportQueryRegimeBound : Bool
  queryHiddenDuringUpdate : Bool
  baseStateFrozenDuringEpisode : Bool
  fastStateRollbackable : Bool
  exactExecutableStrategies : Bool
  allExplorationAndInferenceCosted : Bool
  simultaneousUtilityCalibration : Bool
  parentEstimate : Nat
  placeboEstimate : Nat
  actualUpdateEstimate : Nat
  errorBudget : GroundedAdaptationErrorBudget
  claimedTotalError : Nat
  adaptationCostUpper : Nat
  deriving DecidableEq, Repr

def GroundedPromotionCertificate.validB
    (certificate : GroundedPromotionCertificate) : Bool :=
  certificate.evaluatorOwnedSupportReceipts &&
  certificate.actualPlaceboForksMatched &&
  certificate.preDecisionAccessIntegrity &&
  certificate.supportQueryRegimeBound &&
  certificate.queryHiddenDuringUpdate &&
  certificate.baseStateFrozenDuringEpisode &&
  certificate.fastStateRollbackable &&
  certificate.exactExecutableStrategies &&
  certificate.allExplorationAndInferenceCosted &&
  certificate.simultaneousUtilityCalibration &&
  decide (certificate.claimedTotalError = certificate.errorBudget.total) &&
  decide (
    certificate.parentEstimate + 2 * certificate.claimedTotalError +
        certificate.adaptationCostUpper <
      certificate.actualUpdateEstimate) &&
  decide (
    certificate.placeboEstimate + 2 * certificate.claimedTotalError <
      certificate.actualUpdateEstimate)

def checkGroundedPromotion
    (certificate : GroundedPromotionCertificate) : Bool :=
  certificate.validB

/-- Acceptance exposes both outcome gates: positive net value versus the
frozen parent and causal separation versus a compute-matched placebo.  It also
exposes the protocol facts needed to interpret those comparisons. -/
theorem accepted_grounded_promotion_exposes_complete_gate
    (certificate : GroundedPromotionCertificate)
    (accepted : checkGroundedPromotion certificate = true) :
    certificate.evaluatorOwnedSupportReceipts = true ∧
    certificate.actualPlaceboForksMatched = true ∧
    certificate.preDecisionAccessIntegrity = true ∧
    certificate.supportQueryRegimeBound = true ∧
    certificate.queryHiddenDuringUpdate = true ∧
    certificate.baseStateFrozenDuringEpisode = true ∧
    certificate.fastStateRollbackable = true ∧
    certificate.exactExecutableStrategies = true ∧
    certificate.allExplorationAndInferenceCosted = true ∧
    certificate.simultaneousUtilityCalibration = true ∧
    certificate.claimedTotalError = certificate.errorBudget.total ∧
    certificate.parentEstimate + 2 * certificate.claimedTotalError +
        certificate.adaptationCostUpper <
      certificate.actualUpdateEstimate ∧
    certificate.placeboEstimate + 2 * certificate.claimedTotalError <
      certificate.actualUpdateEstimate := by
  unfold checkGroundedPromotion GroundedPromotionCertificate.validB at accepted
  simp only [Bool.and_eq_true, decide_eq_true_eq] at accepted
  simpa only [and_assoc] using accepted

end Mechanogenesis
