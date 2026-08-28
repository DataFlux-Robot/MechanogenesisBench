import Lean.Elab.Tactic.Omega

namespace Mechanogenesis

/-!
`TrajectoryAssets` specifies the evidence boundary between an interactive
research run and automatically generated training data.  It does not assert
that an evaluator or simulator is physically faithful.  It proves which
lineage, timing, accounting and comparison facts a compiler must expose before
an interaction may become SFT, preference, RL, world-model or calibration
supervision.
-/

inductive OutcomeStatus where
  | accepted
  | rejected
  | failed
  deriving DecidableEq, Repr

structure TraceAssetCertificate where
  eventHashChainValid : Bool
  targetHiddenBeforeDecision : Bool
  candidateSetFrozenBeforeSelection : Bool
  selectedActionInFrozenSet : Bool
  selectionCount : Nat
  startedCount : Nat
  observedCount : Nat
  acceptedObservedCount : Nat
  versionUpdateCount : Nat
  executionBeforeObservation : Bool
  evaluatorReceiptBound : Bool
  canonicalWorldBound : Bool
  valueAccountingValid : Bool
  deriving DecidableEq, Repr

def TraceAssetCertificate.Requirements
    (certificate : TraceAssetCertificate) : Prop :=
  certificate.eventHashChainValid = true ∧
  certificate.targetHiddenBeforeDecision = true ∧
  certificate.candidateSetFrozenBeforeSelection = true ∧
  certificate.selectedActionInFrozenSet = true ∧
  0 < certificate.observedCount ∧
  certificate.selectionCount = certificate.startedCount ∧
  certificate.startedCount = certificate.observedCount ∧
  certificate.acceptedObservedCount = certificate.versionUpdateCount ∧
  certificate.executionBeforeObservation = true ∧
  certificate.evaluatorReceiptBound = true ∧
  certificate.canonicalWorldBound = true ∧
  certificate.valueAccountingValid = true

instance traceAssetRequirementsDecidable (certificate : TraceAssetCertificate) :
    Decidable certificate.Requirements := by
  unfold TraceAssetCertificate.Requirements
  infer_instance

def TraceAssetCertificate.validB
    (certificate : TraceAssetCertificate) : Bool :=
  decide certificate.Requirements

/-- A compiler acceptance is not a generic "successful interaction" flag: it
exposes target hiding, frozen action support, an executed observation chain,
evaluator/world binding and exact accepted-update accounting. -/
theorem accepted_trace_asset_certificate_exposes_requirements
    (certificate : TraceAssetCertificate)
    (accepted : certificate.validB = true) :
    certificate.Requirements := by
  unfold TraceAssetCertificate.validB at accepted
  exact of_decide_eq_true accepted

/-- A transcript containing no executed observation can never be promoted to
a training-ready trace, regardless of how good its textual reasoning looks. -/
theorem observation_free_interaction_is_not_training_ready
    (certificate : TraceAssetCertificate)
    (empty : certificate.observedCount = 0) :
    certificate.validB = false := by
  unfold TraceAssetCertificate.validB
  apply decide_eq_false
  intro requirements
  unfold TraceAssetCertificate.Requirements at requirements
  omega

structure SftCandidate where
  status : OutcomeStatus
  executed : Bool
  observed : Bool
  evaluatorReceiptBound : Bool
  canonicalWorldBound : Bool
  versionUpdateAccounted : Bool
  destroyedShortcutCount : Nat
  grossValue : Nat
  fullCost : Nat
  deriving DecidableEq, Repr

def SftCandidate.Eligible (candidate : SftCandidate) : Prop :=
  candidate.status = .accepted ∧
  candidate.executed = true ∧
  candidate.observed = true ∧
  candidate.evaluatorReceiptBound = true ∧
  candidate.canonicalWorldBound = true ∧
  candidate.versionUpdateAccounted = true ∧
  0 < candidate.destroyedShortcutCount ∧
  candidate.fullCost < candidate.grossValue

/-- SFT receives only an executed, evaluator-bound, positive-destruction action
whose gross value repays its full recorded cost. -/
theorem sft_eligibility_implies_grounded_positive_net_value
    (candidate : SftCandidate)
    (eligible : candidate.Eligible) :
    candidate.executed = true ∧
    candidate.observed = true ∧
    0 < candidate.destroyedShortcutCount ∧
    candidate.fullCost < candidate.grossValue := by
  exact ⟨eligible.2.1, eligible.2.2.1, eligible.2.2.2.2.2.2.1,
    eligible.2.2.2.2.2.2.2⟩

/-- Merely forecasting positive destruction is insufficient for SFT. -/
theorem unexecuted_forecast_is_not_sft_eligible
    (candidate : SftCandidate)
    (unexecuted : candidate.executed = false) :
    ¬ candidate.Eligible := by
  intro eligible
  simp [SftCandidate.Eligible, unexecuted] at eligible

structure PreferenceCandidate where
  winnerStateId : Nat
  loserStateId : Nat
  winnerCandidateSetId : Nat
  loserCandidateSetId : Nat
  winnerExecuted : Bool
  loserExecuted : Bool
  winnerObserved : Bool
  loserObserved : Bool
  commonEvaluatorBound : Bool
  winnerNetValue : Nat
  loserNetValue : Nat
  deriving DecidableEq, Repr

def PreferenceCandidate.Eligible (candidate : PreferenceCandidate) : Prop :=
  candidate.winnerStateId = candidate.loserStateId ∧
  candidate.winnerCandidateSetId = candidate.loserCandidateSetId ∧
  candidate.winnerExecuted = true ∧
  candidate.loserExecuted = true ∧
  candidate.winnerObserved = true ∧
  candidate.loserObserved = true ∧
  candidate.commonEvaluatorBound = true ∧
  candidate.loserNetValue < candidate.winnerNetValue

/-- Preference data is a within-parent causal fork, not a comparison of two
unmatched successful endpoints. -/
theorem preference_eligibility_exposes_same_parent_executed_fork
    (candidate : PreferenceCandidate)
    (eligible : candidate.Eligible) :
    candidate.winnerStateId = candidate.loserStateId ∧
    candidate.winnerCandidateSetId = candidate.loserCandidateSetId ∧
    candidate.winnerExecuted = true ∧
    candidate.loserExecuted = true ∧
    candidate.loserNetValue < candidate.winnerNetValue := by
  exact ⟨eligible.1, eligible.2.1, eligible.2.2.1, eligible.2.2.2.1,
    eligible.2.2.2.2.2.2.2⟩

structure RlCandidate where
  status : OutcomeStatus
  executed : Bool
  observed : Bool
  evaluatorReceiptBound : Bool
  canonicalWorldBound : Bool
  valueAccountingValid : Bool
  deriving DecidableEq, Repr

def RlCandidate.Eligible (candidate : RlCandidate) : Prop :=
  candidate.executed = true ∧
  candidate.observed = true ∧
  candidate.evaluatorReceiptBound = true ∧
  candidate.canonicalWorldBound = true ∧
  candidate.valueAccountingValid = true

/-- Failures remain valid execution supervision for RL when their execution,
observation and accounting receipts are grounded. -/
theorem grounded_failure_can_be_rl_eligible :
    let candidate : RlCandidate := {
      status := .failed
      executed := true
      observed := true
      evaluatorReceiptBound := true
      canonicalWorldBound := true
      valueAccountingValid := true
    }
    candidate.Eligible := by
  simp [RlCandidate.Eligible]

structure DestructionForecast where
  predicted : Nat
  realized : Nat
  deriving DecidableEq, Repr

def natDistance (left right : Nat) : Nat :=
  (left - right) + (right - left)

def StateMaximumCalibrated
  (forecasts : List DestructionForecast) (simultaneousError : Nat) : Prop :=
  ∀ forecast, forecast ∈ forecasts →
    natDistance forecast.predicted forecast.realized ≤ simultaneousError

/-- Calibrating the maximum error over an entire candidate state covers the
action selected after ranking; no independence assumption over actions is
needed for this deterministic implication. -/
theorem state_maximum_calibration_covers_selected_action
    (forecasts : List DestructionForecast)
    (simultaneousError : Nat)
    (selected : DestructionForecast)
    (calibrated : StateMaximumCalibrated forecasts simultaneousError)
    (member : selected ∈ forecasts) :
    natDistance selected.predicted selected.realized ≤ simultaneousError := by
  exact calibrated selected member

/-- Calibration of one action does not cover another action chosen from the
same state.  This finite witness is the max-selection-bias failure that forces
state-level simultaneous calibration. -/
theorem one_action_calibration_does_not_cover_selected_action :
    let calibratedAction : DestructionForecast := { predicted := 1, realized := 1 }
    let selectedAction : DestructionForecast := { predicted := 3, realized := 0 }
    natDistance calibratedAction.predicted calibratedAction.realized ≤ 0 ∧
    ¬ natDistance selectedAction.predicted selectedAction.realized ≤ 0 := by
  decide

structure CalibrationTransportState where
  publicView : Nat
  realizedError : Nat
  deriving DecidableEq, Repr

/-- Even exact equality of a finite public applicability view does not by
itself transport a calibration bound: two compatible hidden worlds can assign
different realized errors to the same view. -/
theorem identical_public_view_does_not_transport_calibration_bound :
    let source : CalibrationTransportState := {
      publicView := 7
      realizedError := 1
    }
    let shifted : CalibrationTransportState := {
      publicView := 7
      realizedError := 4
    }
    source.publicView = shifted.publicView ∧
    source.realizedError ≤ 1 ∧
    ¬ shifted.realizedError ≤ 1 := by
  decide

/-- A transported bound requires an explicit bridge from source error to test
error.  The deployment threshold must pay both the source calibration error
and the certified shift budget. -/
theorem calibration_transport_bridge_expands_runtime_bound
    (sourceError testError sourceBound shiftBudget : Nat)
    (sourceCalibrated : sourceError ≤ sourceBound)
    (transportBridge : testError ≤ sourceError + shiftBudget) :
    testError ≤ sourceBound + shiftBudget := by
  omega

end Mechanogenesis
