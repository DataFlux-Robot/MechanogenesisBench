/-
Preservation theorems for the canonical Mechanism IR reference fragment.

The executable interpreter uses fixed-point integers and emits one receipt per
world transition. These lemmas establish algebraic properties of that design;
they do not establish that the chosen geometry or error model is physically
complete.
-/

structure LengthQ where
  micrometres : Nat

structure DurationQ where
  microseconds : Nat

structure EnergyQ where
  millijoules : Nat

structure MassBalanceQ where
  material : Nat
  input : Nat
  reserveDraw : Nat
  output : Nat
  waste : Nat

def MassClosed (balance : MassBalanceQ) : Prop :=
  balance.input + balance.reserveDraw = balance.output + balance.waste

def AllMassClosed : List MassBalanceQ → Prop
  | [] => True
  | balance :: rest => MassClosed balance ∧ AllMassClosed rest

def TotalMassIn : List MassBalanceQ → Nat
  | [] => 0
  | balance :: rest =>
      (balance.input + balance.reserveDraw) + TotalMassIn rest

def TotalMassOut : List MassBalanceQ → Nat
  | [] => 0
  | balance :: rest =>
      (balance.output + balance.waste) + TotalMassOut rest

theorem local_mass_closure_composes_globally
    (balances : List MassBalanceQ)
    (closed : AllMassClosed balances) :
    TotalMassIn balances = TotalMassOut balances := by
  induction balances with
  | nil => rfl
  | cons balance rest inductionHypothesis =>
      have headClosed : MassClosed balance := closed.1
      have tailClosed : AllMassClosed rest := closed.2
      simp only [TotalMassIn, TotalMassOut]
      rw [headClosed]
      rw [inductionHypothesis tailClosed]

structure SubtractiveTransition where
  stockMass : Nat
  partMass : Nat
  wasteMass : Nat

def IsConservativeSubtraction (transition : SubtractiveTransition) : Prop :=
  transition.stockMass = transition.partMass + transition.wasteMass

theorem conservative_subtraction_cannot_create_part_mass
    (transition : SubtractiveTransition)
    (conservative : IsConservativeSubtraction transition) :
    transition.partMass ≤ transition.stockMass := by
  rw [conservative]
  exact Nat.le_add_right transition.partMass transition.wasteMass

structure WorldReceipt where
  parentWorld : Nat
  childWorld : Nat

def ReceiptChain : Nat → List WorldReceipt → Nat → Prop
  | start, [], finish => start = finish
  | start, receipt :: rest, finish =>
      receipt.parentWorld = start ∧
      ReceiptChain receipt.childWorld rest finish

theorem empty_receipt_chain_cannot_change_world
    (start finish : Nat)
    (chain : ReceiptChain start [] finish) :
    start = finish := by
  exact chain

theorem receipt_chain_tail_is_bound_to_first_child
    (start finish : Nat)
    (first : WorldReceipt)
    (rest : List WorldReceipt)
    (chain : ReceiptChain start (first :: rest) finish) :
    first.parentWorld = start ∧
    ReceiptChain first.childWorld rest finish := by
  exact chain

structure ErrorBudgetQ where
  locatorClearance : Nat
  referenceClearance : Nat
  angularTipError : Nat
  probeRepeatability : Nat
  disturbanceBound : Nat

def WorstCaseError (budget : ErrorBudgetQ) : Nat :=
  budget.locatorClearance +
  budget.referenceClearance +
  budget.angularTipError +
  budget.probeRepeatability +
  budget.disturbanceBound

theorem increasing_unmodelled_disturbance_cannot_reduce_bound
    (budget : ErrorBudgetQ)
    (extra : Nat) :
    WorstCaseError budget ≤
      WorstCaseError { budget with
        disturbanceBound := budget.disturbanceBound + extra } := by
  simp only [WorstCaseError]
  simp [Nat.add_assoc]

structure PhysicalContributionWitness where
  parentProcessError : Nat
  fixtureLocalError : Nat
  transferError : Nat
  childProcessError : Nat
  parentArtifactLocalError : Nat
  childArtifactLocalError : Nat

def ValidPhysicalContribution (witness : PhysicalContributionWitness) : Prop :=
  witness.childProcessError =
      witness.fixtureLocalError + witness.transferError ∧
  witness.childProcessError < witness.parentProcessError ∧
  witness.childArtifactLocalError ≤ witness.parentArtifactLocalError

def ParentArtifactAbsoluteError (witness : PhysicalContributionWitness) : Nat :=
  witness.parentProcessError + witness.parentArtifactLocalError

def ChildArtifactAbsoluteError (witness : PhysicalContributionWitness) : Nat :=
  witness.childProcessError + witness.childArtifactLocalError

theorem valid_physical_contribution_strictly_improves_successor_bound
    (witness : PhysicalContributionWitness)
    (valid : ValidPhysicalContribution witness) :
    ChildArtifactAbsoluteError witness < ParentArtifactAbsoluteError witness := by
  exact Nat.add_lt_add_of_lt_of_le valid.2.1 valid.2.2
