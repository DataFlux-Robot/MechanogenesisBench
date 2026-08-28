import Lean.Elab.Tactic.Omega
import Lean.Data.Json.FromToJson

namespace Mechanogenesis

/-!
`Generalization` turns the benchmark's anti-shortcut requirements into a small
sovereign kernel.  It deliberately does not prove that diverse data makes an
LLM causal or that a physical backend is faithful.  It proves four finite
facts used by the executable algorithm:

1. a same-projection/opposite-target pair refutes every selector restricted to
   that projection;
2. marginal axis coverage alone leaves compositional queries unidentified;
3. an executed counterexample removes a fitting shortcut from the version
   space, and a progress-certified acquisition round strictly increases the
   destroyed count;
4. description-length pressure prefers a lower-complexity rule only after
   evidence has made competing shortcuts non-fitting.
-/

universe u v w

structure LabeledPhysicalCase (Input : Type u) (Label : Type v) where
  input : Input
  target : Label

abbrev Predictor (Input : Type u) (Label : Type v) := Input → Label

def Fits
    {Input : Type u} {Label : Type v}
    (predictor : Predictor Input Label)
    (evidence : List (LabeledPhysicalCase Input Label)) : Prop :=
  ∀ item, item ∈ evidence → predictor item.input = item.target

def InVersionSpace
    {Input : Type u} {Label : Type v}
    (registered : List (Predictor Input Label))
    (evidence : List (LabeledPhysicalCase Input Label))
    (predictor : Predictor Input Label) : Prop :=
  predictor ∈ registered ∧ Fits predictor evidence

def UsesOnlyProjection
    {Input : Type u} {Label : Type v} {View : Type w}
    (project : Input → View)
    (predictor : Predictor Input Label) : Prop :=
  ∀ left right, project left = project right → predictor left = predictor right

/-- A collision witness eliminates the complete class of deterministic
projection-only selectors, not just one enumerated heuristic. -/
theorem projection_collision_refutes_projection_only_predictor
    {Input : Type u} {Label : Type v} {View : Type w}
    (project : Input → View)
    (predictor : Predictor Input Label)
    (left right : LabeledPhysicalCase Input Label)
    (projectionEqual : project left.input = project right.input)
    (targetsDiffer : left.target ≠ right.target)
    (projectionOnly : UsesOnlyProjection project predictor) :
    ¬ (predictor left.input = left.target ∧
       predictor right.input = right.target) := by
  intro correct
  apply targetsDiffer
  calc
    left.target = predictor left.input := correct.1.symm
    _ = predictor right.input := projectionOnly left.input right.input projectionEqual
    _ = right.target := correct.2

/-- Executing a counterexample is a sound CEGIS update: the contradicted
shortcut was in the old version space and is absent after evidence insertion. -/
theorem executed_counterexample_removes_registered_shortcut
    {Input : Type u} {Label : Type v}
    (registered : List (Predictor Input Label))
    (evidence : List (LabeledPhysicalCase Input Label))
    (predictor : Predictor Input Label)
    (item : LabeledPhysicalCase Input Label)
    (oldMember : InVersionSpace registered evidence predictor)
    (contradiction : predictor item.input ≠ item.target) :
    InVersionSpace registered evidence predictor ∧
    ¬ InVersionSpace registered (item :: evidence) predictor := by
  refine ⟨oldMember, ?_⟩
  intro newMember
  exact contradiction (newMember.2 item (by simp))

/-- Adding grounded evidence cannot resurrect a shortcut already excluded by
the previous evidence. -/
theorem evidence_growth_cannot_expand_version_space
    {Input : Type u} {Label : Type v}
    (registered : List (Predictor Input Label))
    (oldEvidence newEvidence : List (LabeledPhysicalCase Input Label))
    (predictor : Predictor Input Label)
    (memberAfter :
      InVersionSpace registered (newEvidence ++ oldEvidence) predictor) :
    InVersionSpace registered oldEvidence predictor := by
  refine ⟨memberAfter.1, ?_⟩
  intro item oldMember
  exact memberAfter.2 item (List.mem_append_right newEvidence oldMember)

structure BinaryFactorPoint where
  world : Bool
  intervention : Bool
  deriving DecidableEq, Repr

def parityTarget (point : BinaryFactorPoint) : Bool :=
  xor point.world point.intervention

def constantFalseTarget (_point : BinaryFactorPoint) : Bool := false

/-- Both values of every individual axis occur in training, yet a rule and a
shortcut agree on all training points and disagree on an unseen combination.
This is a machine-checked counterexample to "marginal diversity implies
compositional generalization". -/
theorem marginal_coverage_does_not_identify_compositional_rule :
    let train : List BinaryFactorPoint :=
      [⟨false, false⟩, ⟨true, true⟩]
    let query : BinaryFactorPoint := ⟨false, true⟩
    (∀ value : Bool, ∃ point, point ∈ train ∧ point.world = value) ∧
    (∀ value : Bool, ∃ point, point ∈ train ∧ point.intervention = value) ∧
    (∀ point, point ∈ train →
      parityTarget point = constantFalseTarget point) ∧
    parityTarget query ≠ constantFalseTarget query := by
  decide

def RegularizedObjective
    (empiricalErrors descriptionLength complexityWeight : Nat) : Nat :=
  empiricalErrors + complexityWeight * descriptionLength

/-- Complexity pressure chooses the shorter rule when empirical fit is tied.
The theorem is useful only after counterexamples establish that the shorter
rule is not a surviving shortcut. -/
theorem equal_fit_lower_description_length_has_lower_objective
    (empiricalErrors shorter longer complexityWeight : Nat)
    (shorterRule : shorter < longer)
    (positiveWeight : 0 < complexityWeight) :
    RegularizedObjective empiricalErrors shorter complexityWeight <
      RegularizedObjective empiricalErrors longer complexityWeight := by
  unfold RegularizedObjective
  have scaled : complexityWeight * shorter < complexityWeight * longer := by
    exact Nat.mul_lt_mul_of_pos_left shorterRule positiveWeight
  exact Nat.add_lt_add_left scaled empiricalErrors

/-- Consequently, MDL/weight decay alone can prefer a wrong but shorter
training-set shortcut.  Diversity must first provide a contradiction. -/
theorem complexity_pressure_alone_can_prefer_wrong_shortcut :
    let trainingErrors := 0
    let shortcutLength := 1
    let causalLength := 2
    let complexityWeight := 1
    RegularizedObjective trainingErrors shortcutLength complexityWeight <
      RegularizedObjective trainingErrors causalLength complexityWeight := by
  decide

structure ShortcutSearchState where
  registeredCount : Nat
  remainingCount : Nat
  deriving DecidableEq, Repr

def ShortcutSearchState.Valid (state : ShortcutSearchState) : Prop :=
  state.remainingCount ≤ state.registeredCount

structure CounterexampleGuidedRound where
  before : ShortcutSearchState
  after : ShortcutSearchState
  executedPhysicalWitnessCount : Nat
  fullRoundCost : Nat
  deriving DecidableEq, Repr

def CounterexampleGuidedRound.Progressing
    (round : CounterexampleGuidedRound) : Prop :=
  round.before.Valid ∧
  round.after.registeredCount = round.before.registeredCount ∧
  round.after.remainingCount < round.before.remainingCount ∧
  0 < round.executedPhysicalWitnessCount ∧
  0 < round.fullRoundCost

/-- A certified acquisition round strictly increases the number of destroyed
registered shortcut classes. -/
theorem progressing_round_strictly_increases_destroyed_shortcuts
    (round : CounterexampleGuidedRound)
    (progress : round.Progressing) :
    round.before.registeredCount - round.before.remainingCount <
      round.after.registeredCount - round.after.remainingCount := by
  rcases progress with ⟨beforeValid, sameRegistered, fewer, _, _⟩
  unfold ShortcutSearchState.Valid at beforeValid
  omega

structure PlannedCollision where
  expectedDestructionPPM : Nat
  executed : Bool
  observedTargetsDiffer : Bool
  deriving DecidableEq, Repr

def PlannedCollision.CertifiesShortcutDestruction
    (plan : PlannedCollision) : Prop :=
  plan.executed = true ∧ plan.observedTargetsDiffer = true

/-- World-model disagreement guides access but is not itself evidence.  Any
shortcut-destruction certificate must expose an executed experiment and an
evaluator-observed target difference, regardless of forecast confidence. -/
theorem certified_collision_requires_execution_and_observation
    (plan : PlannedCollision)
    (certified : plan.CertifiesShortcutDestruction) :
    plan.executed = true ∧ plan.observedTargetsDiffer = true := by
  exact certified

/-- A maximally confident but unexecuted forecast is not a certificate. -/
theorem unexecuted_forecast_cannot_certify_shortcut_destruction :
    let plan : PlannedCollision := {
      expectedDestructionPPM := 1000000
      executed := false
      observedTargetsDiffer := false
    }
    ¬ plan.CertifiesShortcutDestruction := by
  simp [PlannedCollision.CertifiesShortcutDestruction]

structure GroundedSeparatingProbe where
  projectionEqual : Bool
  complementDifferent : Bool
  executed : Bool
  observedTargetsDiffer : Bool
  deriving DecidableEq, Repr

def GroundedSeparatingProbe.StructuralOpportunity
    (probe : GroundedSeparatingProbe) : Prop :=
  probe.projectionEqual = true ∧ probe.complementDifferent = true

def GroundedSeparatingProbe.CertifiesCollision
    (probe : GroundedSeparatingProbe) : Prop :=
  probe.StructuralOpportunity ∧
  probe.executed = true ∧
  probe.observedTargetsDiffer = true

/-- Large complement distance creates a grounded experiment opportunity, but
does not logically force different physical outcomes.  The constant-target
world is the finite counterexample. -/
theorem structural_separation_alone_cannot_certify_collision :
    let probe : GroundedSeparatingProbe := {
      projectionEqual := true
      complementDifferent := true
      executed := true
      observedTargetsDiffer := false
    }
    probe.StructuralOpportunity ∧ ¬ probe.CertifiesCollision := by
  simp [GroundedSeparatingProbe.StructuralOpportunity,
    GroundedSeparatingProbe.CertifiesCollision]

structure FiniteAmbiguitySchedule where
  executedContrastCount : Nat
  sameTargetContrastCount : Nat
  collisionContrastCount : Nat
  certifiedAmbiguityBudget : Nat
  deriving DecidableEq, Repr

def FiniteAmbiguitySchedule.Valid
    (schedule : FiniteAmbiguitySchedule) : Prop :=
  schedule.executedContrastCount =
      schedule.sameTargetContrastCount + schedule.collisionContrastCount ∧
  schedule.sameTargetContrastCount ≤ schedule.certifiedAmbiguityBudget

/-- A concrete separability threshold: if at most `B` structurally distinct
contrasts can preserve the same target, executing `B + 1` contrasts forces an
observed collision.  Without the explicit ambiguity budget, no such guarantee
follows from diversity alone. -/
theorem exceeding_certified_ambiguity_budget_forces_collision
    (schedule : FiniteAmbiguitySchedule)
    (valid : schedule.Valid)
    (beyond : schedule.certifiedAmbiguityBudget <
      schedule.executedContrastCount) :
    0 < schedule.collisionContrastCount := by
  unfold FiniteAmbiguitySchedule.Valid at valid
  omega

/-- Improving the learned selector can reorder probes and reduce expected
cost, but a worst-case deterministic guarantee improves only when the certified
ambiguity budget itself decreases. -/
theorem lower_ambiguity_budget_weakly_lowers_forcing_threshold
    (oldBudget newBudget : Nat)
    (improved : newBudget ≤ oldBudget) :
    newBudget + 1 ≤ oldBudget + 1 := by
  omega

structure ForecastedExperimentValue where
  trueNetValue : Nat
  estimatedNetValue : Nat
  simultaneousError : Nat
  fullExperimentCost : Nat
  deriving DecidableEq, Repr

def ForecastedExperimentValue.Calibrated
    (forecast : ForecastedExperimentValue) : Prop :=
  forecast.estimatedNetValue ≤ forecast.trueNetValue + forecast.simultaneousError ∧
  forecast.trueNetValue ≤ forecast.estimatedNetValue + forecast.simultaneousError

def ForecastedExperimentValue.CertifiedPositive
    (forecast : ForecastedExperimentValue) : Prop :=
  forecast.fullExperimentCost + forecast.simultaneousError <
    forecast.estimatedNetValue

/-- The algorithm may execute a forecast for positive value only when its
lower confidence bound repays the full experiment cost. -/
theorem calibrated_forecast_gate_certifies_positive_experiment_value
    (forecast : ForecastedExperimentValue)
    (calibrated : forecast.Calibrated)
    (accepted : forecast.CertifiedPositive) :
    forecast.fullExperimentCost < forecast.trueNetValue := by
  unfold ForecastedExperimentValue.Calibrated at calibrated
  unfold ForecastedExperimentValue.CertifiedPositive at accepted
  omega

structure GeneralizationCertificate where
  trainSplitId : Nat
  sealedSplitId : Nat
  exactFactorTupleOverlapCount : Nat
  registeredAxisCount : Nat
  sealedFactorValueCount : Nat
  factorValuesSeenInTrainCount : Nat
  unseenInteractionCount : Nat
  registeredShortcutCount : Nat
  destroyedShortcutCount : Nat
  sealedCaseCount : Nat
  predictionCount : Nat
  sealedCorrectCount : Nat
  worstGroupCaseCount : Nat
  worstGroupCorrectCount : Nat
  minimumAccuracyPPM : Nat
  minimumWorstGroupAccuracyPPM : Nat
  canonicalPassCount : Nat
  leanPassCount : Nat
  replayPassCount : Nat
  independentBackendPassCount : Nat
  independentNumericSeedCount : Nat
  physicalRequired : Bool
  physicalPassCount : Nat
  sealedReadBeforeFreeze : Bool
  recursiveClaim : Bool
  generatorUpdateCount : Nat
  parentFutureEstimate : Nat
  placeboFutureEstimate : Nat
  actualFutureEstimate : Nat
  simultaneousError : Nat
  fullUpdateCost : Nat
  deriving DecidableEq, Repr, Lean.FromJson, Lean.ToJson

def GeneralizationCertificate.SplitRequirements
    (certificate : GeneralizationCertificate) : Prop :=
  certificate.trainSplitId ≠ certificate.sealedSplitId ∧
  certificate.exactFactorTupleOverlapCount = 0 ∧
  certificate.sealedReadBeforeFreeze = false

def GeneralizationCertificate.DiversityRequirements
    (certificate : GeneralizationCertificate) : Prop :=
  5 ≤ certificate.registeredAxisCount ∧
  0 < certificate.sealedFactorValueCount ∧
  certificate.factorValuesSeenInTrainCount = certificate.sealedFactorValueCount ∧
  0 < certificate.unseenInteractionCount ∧
  0 < certificate.registeredShortcutCount ∧
  certificate.destroyedShortcutCount = certificate.registeredShortcutCount

def GeneralizationCertificate.PerformanceRequirements
    (certificate : GeneralizationCertificate) : Prop :=
  0 < certificate.sealedCaseCount ∧
  certificate.predictionCount = certificate.sealedCaseCount ∧
  certificate.sealedCorrectCount * 1000000 ≥
    certificate.minimumAccuracyPPM * certificate.sealedCaseCount ∧
  0 < certificate.worstGroupCaseCount ∧
  certificate.worstGroupCorrectCount * 1000000 ≥
    certificate.minimumWorstGroupAccuracyPPM * certificate.worstGroupCaseCount

def GeneralizationCertificate.EngineeringRequirements
    (certificate : GeneralizationCertificate) : Prop :=
  certificate.canonicalPassCount = certificate.sealedCaseCount ∧
  certificate.leanPassCount = certificate.sealedCaseCount ∧
  certificate.replayPassCount = certificate.sealedCaseCount ∧
  0 < certificate.independentBackendPassCount ∧
  3 ≤ certificate.independentNumericSeedCount ∧
  (certificate.physicalRequired = true → 0 < certificate.physicalPassCount)

def GeneralizationCertificate.RecursiveRequirements
    (certificate : GeneralizationCertificate) : Prop :=
  (certificate.recursiveClaim = true →
    0 < certificate.generatorUpdateCount ∧
    certificate.parentFutureEstimate +
        2 * certificate.simultaneousError + certificate.fullUpdateCost <
      certificate.actualFutureEstimate ∧
    certificate.placeboFutureEstimate + 2 * certificate.simultaneousError <
      certificate.actualFutureEstimate)

def GeneralizationCertificate.Requirements
    (certificate : GeneralizationCertificate) : Prop :=
  certificate.SplitRequirements ∧
  certificate.DiversityRequirements ∧
  certificate.PerformanceRequirements ∧
  certificate.EngineeringRequirements ∧
  certificate.RecursiveRequirements

instance (certificate : GeneralizationCertificate) :
    Decidable certificate.SplitRequirements := by
  unfold GeneralizationCertificate.SplitRequirements
  infer_instance

instance (certificate : GeneralizationCertificate) :
    Decidable certificate.DiversityRequirements := by
  unfold GeneralizationCertificate.DiversityRequirements
  infer_instance

instance (certificate : GeneralizationCertificate) :
    Decidable certificate.PerformanceRequirements := by
  unfold GeneralizationCertificate.PerformanceRequirements
  infer_instance

instance (certificate : GeneralizationCertificate) :
    Decidable certificate.EngineeringRequirements := by
  unfold GeneralizationCertificate.EngineeringRequirements
  infer_instance

instance (certificate : GeneralizationCertificate) :
    Decidable certificate.RecursiveRequirements := by
  unfold GeneralizationCertificate.RecursiveRequirements
  infer_instance

instance (certificate : GeneralizationCertificate) :
    Decidable certificate.Requirements := by
  unfold GeneralizationCertificate.Requirements
  infer_instance

set_option maxRecDepth 10000 in
def GeneralizationCertificate.validB
    (certificate : GeneralizationCertificate) : Bool :=
  decide certificate.Requirements

/-- Acceptance exposes the entire finite benchmark contract.  In particular,
perfect sealed accuracy cannot compensate for a surviving registered shortcut,
split leakage, missing interaction novelty, or missing engineering evidence. -/
theorem accepted_generalization_certificate_exposes_requirements
    (certificate : GeneralizationCertificate)
    (accepted : certificate.validB = true) :
    certificate.Requirements := by
  unfold GeneralizationCertificate.validB at accepted
  exact of_decide_eq_true accepted

/-- On the Recursive Learner track, the same certificate additionally exposes
an isolated future-value update that beats both parent and matched placebo
after the full uncertainty/cost threshold. -/
theorem accepted_recursive_generalization_has_net_future_value
    (certificate : GeneralizationCertificate)
    (accepted : certificate.validB = true)
    (recursiveClaim : certificate.recursiveClaim = true) :
    0 < certificate.generatorUpdateCount ∧
    certificate.parentFutureEstimate +
        2 * certificate.simultaneousError + certificate.fullUpdateCost <
      certificate.actualFutureEstimate ∧
    certificate.placeboFutureEstimate + 2 * certificate.simultaneousError <
      certificate.actualFutureEstimate := by
  have requirements :=
    accepted_generalization_certificate_exposes_requirements certificate accepted
  exact requirements.2.2.2.2 recursiveClaim

end Mechanogenesis
