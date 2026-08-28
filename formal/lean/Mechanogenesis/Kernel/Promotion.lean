import Mechanogenesis.Kernel.PhysicalTransition

namespace Mechanogenesis

structure PromotionClaim where
  parentErrorUpper : Nat
  childErrorUpper : Nat
  requiredMargin : Nat
  netValue : Nat
  claimedTier : EvidenceTier
  ceilingTier : EvidenceTier
  deriving Repr

/-- An evaluator's improvement claim is not sovereign unless it names the
exact parent and child worlds to which its error bounds apply. -/
structure PromotionDecision where
  parentWorldHash : Digest
  childWorldHash : Digest
  claim : PromotionClaim
  deriving Repr

def PromotionDecision.BoundTo
    (decision : PromotionDecision)
    (input : TransitionInput)
    (output : TransitionOutput) : Prop :=
  decision.parentWorldHash = input.parentWorldHash ∧
  decision.childWorldHash = output.childWorldHash

def PromotionClaim.Accepted (claim : PromotionClaim) : Prop :=
  0 < claim.requiredMargin ∧
  claim.childErrorUpper + claim.requiredMargin ≤ claim.parentErrorUpper ∧
  0 < claim.netValue ∧
  claim.claimedTier.noStrongerThan claim.ceilingTier

def PromotionDecision.AcceptedFor
    (decision : PromotionDecision)
    (input : TransitionInput)
    (output : TransitionOutput) : Prop :=
  decision.BoundTo input output ∧ decision.claim.Accepted

def SovereignPromotion
    (transitionValid assumptionsAccounted : Prop)
    (claim : PromotionClaim) : Prop :=
  transitionValid ∧ assumptionsAccounted ∧ claim.Accepted

theorem sovereign_promotion_implies_strict_error_improvement
    (transitionValid assumptionsAccounted : Prop)
    (claim : PromotionClaim)
    (promoted : SovereignPromotion transitionValid assumptionsAccounted claim) :
    claim.childErrorUpper < claim.parentErrorUpper := by
  have marginPositive : 0 < claim.requiredMargin := promoted.2.2.1
  have bounded :
      claim.childErrorUpper + claim.requiredMargin ≤ claim.parentErrorUpper :=
    promoted.2.2.2.1
  exact Nat.lt_of_lt_of_le
    (Nat.lt_add_of_pos_right marginPositive)
    bounded

theorem sovereign_promotion_cannot_hide_transition_failure
    (transitionValid assumptionsAccounted : Prop)
    (claim : PromotionClaim)
    (promoted : SovereignPromotion transitionValid assumptionsAccounted claim) :
    transitionValid := by
  exact promoted.1

theorem sovereign_promotion_cannot_hide_assumptions
    (transitionValid assumptionsAccounted : Prop)
    (claim : PromotionClaim)
    (promoted : SovereignPromotion transitionValid assumptionsAccounted claim) :
    assumptionsAccounted := by
  exact promoted.2.1

theorem bound_promotion_implies_strict_error_improvement
    (decision : PromotionDecision)
    (input : TransitionInput)
    (output : TransitionOutput)
    (accepted : decision.AcceptedFor input output) :
    decision.claim.childErrorUpper < decision.claim.parentErrorUpper := by
  have promoted : SovereignPromotion True True decision.claim :=
    ⟨trivial, trivial, accepted.2⟩
  exact sovereign_promotion_implies_strict_error_improvement
    True True decision.claim promoted

end Mechanogenesis
