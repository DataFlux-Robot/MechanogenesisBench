/-
MechanogenesisBench protocol invariants.

These theorems concern a bounded certification protocol. They do not prove
that a simulator is faithful, that an evaluator is honest, or that physical
recursive self-improvement is universally achievable.
-/

structure Decision where
  beforeUpper : Nat
  afterLower : Nat
  margin : Nat
  netValue : Nat
  robustness : Nat

def Promotable (threshold : Nat) (d : Decision) : Prop :=
  0 < d.margin ∧
  d.beforeUpper + d.margin ≤ d.afterLower ∧
  0 < d.netValue ∧
  threshold ≤ d.robustness

structure Resources where
  time : Nat
  budget : Nat
  energy : Nat
  material : Nat
  human : Nat

def Within (used limit : Resources) : Prop :=
  used.time ≤ limit.time ∧
  used.budget ≤ limit.budget ∧
  used.energy ≤ limit.energy ∧
  used.material ≤ limit.material ∧
  used.human ≤ limit.human

structure Step where
  decision : Decision
  accepted : Prop
  parentProcess : Nat
  childProcess : Nat
  expectedParentProcess : Nat
  parentWorld : Nat
  childWorld : Nat
  expectedParentWorld : Nat
  materialIn : Nat
  reserveDraw : Nat
  materialOut : Nat
  waste : Nat
  evidenceRank : Nat
  evidenceCeiling : Nat
  parentResearchTime : Nat
  childResearchTime : Nat
  parentResearchBudget : Nat
  childResearchBudget : Nat

def MaterialClosed (s : Step) : Prop :=
  s.materialIn + s.reserveDraw = s.materialOut + s.waste

def LineageClosed (s : Step) : Prop :=
  s.parentProcess = s.expectedParentProcess ∧
  s.parentWorld = s.expectedParentWorld ∧
  s.parentProcess ≠ s.childProcess ∧
  s.parentWorld ≠ s.childWorld

def RecursiveCredit (s : Step) : Prop :=
  s.childResearchTime ≤ s.parentResearchTime ∧
  s.childResearchBudget ≤ s.parentResearchBudget ∧
  (s.childResearchTime < s.parentResearchTime ∨
   s.childResearchBudget < s.parentResearchBudget)

structure CertifiedStep (threshold : Nat) (recursiveTrack : Prop) (s : Step) : Prop where
  acceptanceExact : s.accepted ↔ Promotable threshold s.decision
  materialClosed : MaterialClosed s
  lineageClosed : LineageClosed s
  evidenceBounded : s.evidenceRank ≤ s.evidenceCeiling
  recursiveCredit : recursiveTrack → s.accepted → RecursiveCredit s

theorem accepted_has_bounded_gain
    {threshold : Nat} {recursiveTrack : Prop} {s : Step}
    (certificate : CertifiedStep threshold recursiveTrack s)
    (accepted : s.accepted) :
    s.decision.beforeUpper + s.decision.margin ≤ s.decision.afterLower := by
  exact (certificate.acceptanceExact.mp accepted).2.1

theorem accepted_is_strict_when_margin_positive
    {threshold : Nat} {recursiveTrack : Prop} {s : Step}
    (certificate : CertifiedStep threshold recursiveTrack s)
    (accepted : s.accepted) :
    s.decision.beforeUpper < s.decision.afterLower := by
  have lowerBound := accepted_has_bounded_gain certificate accepted
  have positiveMargin := (certificate.acceptanceExact.mp accepted).1
  have marginStep : s.decision.beforeUpper <
      s.decision.beforeUpper + s.decision.margin := by
    exact Nat.lt_add_of_pos_right positiveMargin
  exact Nat.lt_of_lt_of_le marginStep lowerBound

theorem accepted_has_positive_net_value
    {threshold : Nat} {recursiveTrack : Prop} {s : Step}
    (certificate : CertifiedStep threshold recursiveTrack s)
    (accepted : s.accepted) :
    0 < s.decision.netValue := by
  exact (certificate.acceptanceExact.mp accepted).2.2.1

theorem accepted_meets_robustness_threshold
    {threshold : Nat} {recursiveTrack : Prop} {s : Step}
    (certificate : CertifiedStep threshold recursiveTrack s)
    (accepted : s.accepted) :
    threshold ≤ s.decision.robustness := by
  exact (certificate.acceptanceExact.mp accepted).2.2.2

theorem recursive_acceptance_has_at_least_one_strict_efficiency_gain
    {threshold : Nat} {s : Step}
    (certificate : CertifiedStep threshold True s)
    (accepted : s.accepted) :
    (s.childResearchTime ≤ s.parentResearchTime ∧
     s.childResearchBudget ≤ s.parentResearchBudget) ∧
    (s.childResearchTime < s.parentResearchTime ∨
     s.childResearchBudget < s.parentResearchBudget) := by
  have credit := certificate.recursiveCredit trivial accepted
  exact ⟨⟨credit.1, credit.2.1⟩, credit.2.2⟩

structure ResearchTrajectory where
  currentReward : Nat
  futureResearchValue : Nat

def CurrentRewardIndistinguishable
    (left right : ResearchTrajectory) : Prop :=
  left.currentReward = right.currentReward

theorem current_reward_is_not_a_sufficient_recursive_credit_statistic :
    ∃ left right : ResearchTrajectory,
      CurrentRewardIndistinguishable left right ∧
      left.futureResearchValue < right.futureResearchValue := by
  refine ⟨
    { currentReward := 10, futureResearchValue := 1 },
    { currentReward := 10, futureResearchValue := 2 },
    ?_, ?_
  ⟩
  · rfl
  · decide

structure GeneratorFork where
  sameParent : Prop
  sameTaskDistribution : Prop
  sameBudget : Prop
  baselineFutureCost : Nat
  childFutureCost : Nat

def Isolated (fork : GeneratorFork) : Prop :=
  fork.sameParent ∧ fork.sameTaskDistribution ∧ fork.sameBudget

def AttributableImprovement (fork : GeneratorFork) : Prop :=
  Isolated fork ∧ fork.childFutureCost < fork.baselineFutureCost

theorem observed_future_gain_without_isolation_is_not_attributable :
    ∃ fork : GeneratorFork,
      fork.childFutureCost < fork.baselineFutureCost ∧
      ¬ AttributableImprovement fork := by
  let fork : GeneratorFork := {
    sameParent := False
    sameTaskDistribution := True
    sameBudget := True
    baselineFutureCost := 10
    childFutureCost := 5
  }
  refine ⟨fork, by decide, ?_⟩
  intro attributed
  exact attributed.1.1

structure RecursivePromotionConditions where
  reachable : Prop
  attributable : Prop
  discriminable : Prop
  positiveNetValue : Prop

def RecursivePromotionEligible (c : RecursivePromotionConditions) : Prop :=
  c.reachable ∧ c.attributable ∧ c.discriminable ∧ c.positiveNetValue

theorem recursive_promotion_requires_all_four_conditions
    (conditions : RecursivePromotionConditions)
    (eligible : RecursivePromotionEligible conditions) :
    conditions.reachable ∧
    conditions.attributable ∧
    conditions.discriminable ∧
    conditions.positiveNetValue := by
  exact eligible
