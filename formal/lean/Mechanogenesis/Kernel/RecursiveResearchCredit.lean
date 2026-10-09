import Mechanogenesis.Kernel.Digest
import Lean.Elab.Tactic.Omega

namespace Mechanogenesis

/-!
Machine-checked boundary for Recursive Research Credit (RRC).

The module does not assume that an LLM, reward model or simulator is correct.
It separates two claims:

1. current-task reward alone cannot identify future generator utility without
   a linking assumption; and
2. a fork-based future-credit ordering is reliable only above an explicit
   discrimination margin and under matched attribution identities.
-/

inductive ForkChoice where
  | left
  | right
  deriving DecidableEq, Repr

structure FutureUtilityWorld where
  leftUtility : Nat
  rightUtility : Nat
  deriving DecidableEq, Repr

def ChoosesStrictFutureWinner
    (choice : ForkChoice) (world : FutureUtilityWorld) : Prop :=
  match choice with
  | .left => world.rightUtility < world.leftUtility
  | .right => world.leftUtility < world.rightUtility

/- A reward-only selector receives only the two current rewards. -/
abbrev RewardOnlySelector := Nat → Nat → ForkChoice

/--
No reward-only selector can be correct in both future worlds when the worlds
have the same observed current-reward vector but swap which fork improves the
future generator.  The two candidate rewards in that vector may differ.  This
is an identification impossibility, not an optimization failure.
-/
theorem current_reward_cannot_identify_future_winner
    (selector : RewardOnlySelector)
    (leftCurrentReward rightCurrentReward : Nat)
    (lowerFutureUtility higherFutureUtility : Nat)
    (gap : lowerFutureUtility < higherFutureUtility) :
    ¬ (
      ChoosesStrictFutureWinner
        (selector leftCurrentReward rightCurrentReward)
        {
          leftUtility := higherFutureUtility
          rightUtility := lowerFutureUtility
        } ∧
      ChoosesStrictFutureWinner
        (selector leftCurrentReward rightCurrentReward)
        {
          leftUtility := lowerFutureUtility
          rightUtility := higherFutureUtility
        }
    ) := by
  generalize selector leftCurrentReward rightCurrentReward = choice
  cases choice <;> simp [ChoosesStrictFutureWinner] <;> omega

structure GeneratorForkIdentity where
  parentStateHash : Digest
  splitHash : Digest
  evaluatorHash : Digest
  runtimeHash : Digest
  deriving DecidableEq, Repr

def AttributionMatched
    (left right : GeneratorForkIdentity) : Prop :=
  left.parentStateHash = right.parentStateHash ∧
  left.splitHash = right.splitHash ∧
  left.evaluatorHash = right.evaluatorHash ∧
  left.runtimeHash = right.runtimeHash

structure CreditEstimate where
  trueFutureUtility : Nat
  estimatedFutureUtility : Nat
  errorBound : Nat
  deriving DecidableEq, Repr

def CreditEstimate.Calibrated (estimate : CreditEstimate) : Prop :=
  estimate.estimatedFutureUtility ≤
      estimate.trueFutureUtility + estimate.errorBound ∧
  estimate.trueFutureUtility ≤
      estimate.estimatedFutureUtility + estimate.errorBound

/--
The two-epsilon discrimination threshold.  If both estimates are calibrated
within the same error bound and the true utility gap is strictly greater than
twice that bound, estimated RRC must preserve the true ordering.
-/
theorem rrc_discrimination_threshold
    (better worse : CreditEstimate)
    (sameError : better.errorBound = worse.errorBound)
    (betterCalibrated : better.Calibrated)
    (worseCalibrated : worse.Calibrated)
    (separated :
      worse.trueFutureUtility + 2 * better.errorBound <
        better.trueFutureUtility) :
    worse.estimatedFutureUtility < better.estimatedFutureUtility := by
  rcases betterCalibrated with ⟨_, betterLower⟩
  rcases worseCalibrated with ⟨worseUpper, _⟩
  omega

def PositiveNetValue (futureGain updateCost : Nat) : Prop :=
  updateCost < futureGain

/-- Paying at least the entire future gain cannot be certified as positive
recursive value, even if the candidate's raw future utility is higher. -/
theorem nonpositive_net_value_blocks_recursive_improvement
    (futureGain updateCost : Nat)
    (costDominates : futureGain ≤ updateCost) :
    ¬ PositiveNetValue futureGain updateCost := by
  unfold PositiveNetValue
  omega

structure RecursiveImprovementConditions
    (parent candidate : GeneratorForkIdentity)
    (futureGain updateCost : Nat)
    (ReachableSupport ReliableDiscrimination : Prop) : Prop where
  supportWitness : ReachableSupport
  causalAttribution : AttributionMatched parent candidate
  discriminationWitness : ReliableDiscrimination
  positiveNetValue : PositiveNetValue futureGain updateCost

/-- The four S1 gates are explicit proof obligations; none is inferred from a
high endpoint reward. -/
theorem certified_rrc_exposes_all_phase_conditions
    {parent candidate : GeneratorForkIdentity}
    {futureGain updateCost : Nat}
    {ReachableSupport ReliableDiscrimination : Prop}
    (certified :
      RecursiveImprovementConditions
        parent candidate futureGain updateCost
        ReachableSupport ReliableDiscrimination) :
    ReachableSupport ∧
    AttributionMatched parent candidate ∧
    ReliableDiscrimination ∧
    PositiveNetValue futureGain updateCost := by
  exact ⟨
    certified.supportWitness,
    certified.causalAttribution,
    certified.discriminationWitness,
    certified.positiveNetValue
  ⟩

/-! Aggregate future reward can hide catastrophic specialization.  The two
profiles below pass the same total number of tasks, but only the balanced
profile has nonzero support in every registered task family. -/

structure TwoFamilyPassProfile where
  fixturePasses : Nat
  comparatorPasses : Nat
  deriving DecidableEq, Repr

def TwoFamilyPassProfile.aggregatePasses
    (profile : TwoFamilyPassProfile) : Nat :=
  profile.fixturePasses + profile.comparatorPasses

def TwoFamilyPassProfile.worstFamilyPasses
    (profile : TwoFamilyPassProfile) : Nat :=
  min profile.fixturePasses profile.comparatorPasses

theorem aggregate_future_score_cannot_identify_family_floor :
    let collapsed : TwoFamilyPassProfile := ⟨2, 0⟩
    let balanced : TwoFamilyPassProfile := ⟨1, 1⟩
    collapsed.aggregatePasses = balanced.aggregatePasses ∧
      collapsed.worstFamilyPasses < balanced.worstFamilyPasses := by
  decide

theorem positive_worst_family_score_excludes_family_collapse
    (profile : TwoFamilyPassProfile)
    (positiveFloor : 0 < profile.worstFamilyPasses) :
    0 < profile.fixturePasses ∧ 0 < profile.comparatorPasses := by
  unfold TwoFamilyPassProfile.worstFamilyPasses at positiveFloor
  have leftBound := Nat.min_le_left
    profile.fixturePasses profile.comparatorPasses
  have rightBound := Nat.min_le_right
    profile.fixturePasses profile.comparatorPasses
  omega

/-! A family floor is a robustness objective, but its plug-in estimate is not
automatically a reliable decision rule.  One unlucky family sample can reverse
the true ordering.  The repair is to expose family-wise calibration as a proof
obligation and require a strict two-error separation margin. -/

theorem empirical_family_floor_can_reverse_true_order :
    let trueBetter : TwoFamilyPassProfile := ⟨3, 3⟩
    let trueWorse : TwoFamilyPassProfile := ⟨1, 1⟩
    let empiricalBetter : TwoFamilyPassProfile := ⟨3, 0⟩
    let empiricalWorse : TwoFamilyPassProfile := ⟨1, 1⟩
    trueWorse.worstFamilyPasses < trueBetter.worstFamilyPasses ∧
      empiricalBetter.worstFamilyPasses < empiricalWorse.worstFamilyPasses := by
  decide

structure TwoFamilyCreditEstimate where
  fixture : CreditEstimate
  comparator : CreditEstimate
  deriving DecidableEq, Repr

def TwoFamilyCreditEstimate.Calibrated
    (estimate : TwoFamilyCreditEstimate) : Prop :=
  estimate.fixture.Calibrated ∧
    estimate.comparator.Calibrated ∧
    estimate.fixture.errorBound = estimate.comparator.errorBound

def TwoFamilyCreditEstimate.floorCredit
    (estimate : TwoFamilyCreditEstimate) : CreditEstimate where
  trueFutureUtility := min
    estimate.fixture.trueFutureUtility
    estimate.comparator.trueFutureUtility
  estimatedFutureUtility := min
    estimate.fixture.estimatedFutureUtility
    estimate.comparator.estimatedFutureUtility
  errorBound := estimate.fixture.errorBound

/-- Family-wise calibration transfers to the minimum across families.  This is
the missing premise behind any finite-sample maximin promotion rule. -/
theorem calibrated_families_calibrate_the_floor
    (estimate : TwoFamilyCreditEstimate)
    (calibrated : estimate.Calibrated) :
    estimate.floorCredit.Calibrated := by
  rcases calibrated with ⟨fixtureCalibrated, comparatorCalibrated, sameError⟩
  rcases fixtureCalibrated with ⟨fixtureUpper, fixtureLower⟩
  rcases comparatorCalibrated with ⟨comparatorUpper, comparatorLower⟩
  constructor
  · by_cases trueFixtureLower :
        estimate.fixture.trueFutureUtility ≤
          estimate.comparator.trueFutureUtility
    · have estimatedToFixture := Nat.min_le_left
          estimate.fixture.estimatedFutureUtility
          estimate.comparator.estimatedFutureUtility
      simp only [TwoFamilyCreditEstimate.floorCredit,
        Nat.min_eq_left trueFixtureLower]
      omega
    · have trueComparatorLower :
          estimate.comparator.trueFutureUtility ≤
            estimate.fixture.trueFutureUtility := by omega
      have estimatedToComparator := Nat.min_le_right
          estimate.fixture.estimatedFutureUtility
          estimate.comparator.estimatedFutureUtility
      simp only [TwoFamilyCreditEstimate.floorCredit,
        Nat.min_eq_right trueComparatorLower]
      omega
  · by_cases estimatedFixtureLower :
        estimate.fixture.estimatedFutureUtility ≤
          estimate.comparator.estimatedFutureUtility
    · have trueToFixture := Nat.min_le_left
          estimate.fixture.trueFutureUtility
          estimate.comparator.trueFutureUtility
      simp only [TwoFamilyCreditEstimate.floorCredit,
        Nat.min_eq_left estimatedFixtureLower]
      omega
    · have estimatedComparatorLower :
          estimate.comparator.estimatedFutureUtility ≤
            estimate.fixture.estimatedFutureUtility := by omega
      have trueToComparator := Nat.min_le_right
          estimate.fixture.trueFutureUtility
          estimate.comparator.trueFutureUtility
      simp only [TwoFamilyCreditEstimate.floorCredit,
        Nat.min_eq_right estimatedComparatorLower]
      omega

/-- If two candidates have equally calibrated family-wise credit and their
true worst-family utilities differ by more than twice the common error, the
empirical family-floor ordering is correct. -/
theorem family_floor_discrimination_threshold
    (better worse : TwoFamilyCreditEstimate)
    (sameError : better.fixture.errorBound = worse.fixture.errorBound)
    (betterCalibrated : better.Calibrated)
    (worseCalibrated : worse.Calibrated)
    (separated :
      worse.floorCredit.trueFutureUtility +
          2 * better.floorCredit.errorBound <
        better.floorCredit.trueFutureUtility) :
    worse.floorCredit.estimatedFutureUtility <
      better.floorCredit.estimatedFutureUtility := by
  apply rrc_discrimination_threshold
    better.floorCredit worse.floorCredit
  · exact sameError
  · exact calibrated_families_calibrate_the_floor better betterCalibrated
  · exact calibrated_families_calibrate_the_floor worse worseCalibrated
  · exact separated

/-- A selector may promote from finite data only when the candidate's observed
lower bound exceeds the competitor's observed upper bound.  Under calibration,
that certificate implies the strict true floor ordering. -/
theorem separated_empirical_floor_bounds_certify_true_order
    (better worse : TwoFamilyCreditEstimate)
    (betterCalibrated : better.Calibrated)
    (worseCalibrated : worse.Calibrated)
    (certified :
      worse.floorCredit.estimatedFutureUtility +
          worse.floorCredit.errorBound <
        better.floorCredit.estimatedFutureUtility -
          better.floorCredit.errorBound) :
    worse.floorCredit.trueFutureUtility <
      better.floorCredit.trueFutureUtility := by
  have betterFloorCalibrated :=
    calibrated_families_calibrate_the_floor better betterCalibrated
  have worseFloorCalibrated :=
    calibrated_families_calibrate_the_floor worse worseCalibrated
  rcases betterFloorCalibrated with ⟨betterUpper, _⟩
  rcases worseFloorCalibrated with ⟨_, worseLower⟩
  omega

structure CertifiedFloorInterval where
  trueFloor : Nat
  lowerBound : Nat
  upperBound : Nat
  deriving DecidableEq, Repr

def CertifiedFloorInterval.Valid
    (interval : CertifiedFloorInterval) : Prop :=
  interval.lowerBound ≤ interval.trueFloor ∧
    interval.trueFloor ≤ interval.upperBound

/-- This is the exact certify-or-abstain contract implemented by S1-R015.
Unlike a plug-in maximin score, it never promotes while candidate intervals
overlap. -/
theorem separated_floor_intervals_certify_true_order
    (better worse : CertifiedFloorInterval)
    (betterValid : better.Valid)
    (worseValid : worse.Valid)
    (separated : worse.upperBound < better.lowerBound) :
    worse.trueFloor < better.trueFloor := by
  rcases betterValid with ⟨betterLower, _⟩
  rcases worseValid with ⟨_, worseUpper⟩
  omega

/-- For a registered finite pool, assigning zero success to every unobserved
challenge gives a deterministic lower bound, while assigning success to every
unobserved challenge gives a deterministic upper bound. -/
theorem finite_pool_completion_bounds
    (observedSuccesses actualUnobservedSuccesses unobservedCapacity : Nat)
    (capacityBound : actualUnobservedSuccesses ≤ unobservedCapacity) :
    observedSuccesses ≤ observedSuccesses + actualUnobservedSuccesses ∧
      observedSuccesses + actualUnobservedSuccesses ≤
        observedSuccesses + unobservedCapacity := by
  omega

end Mechanogenesis
