import Mechanogenesis.Kernel.RefinementContract
import Lean.Data.Json.FromToJson

namespace Mechanogenesis

structure MaterialBalance where
  material : String
  inputQ : Nat
  reserveDrawQ : Nat
  outputQ : Nat
  wasteQ : Nat
  deriving DecidableEq, Repr, Lean.FromJson, Lean.ToJson

def MaterialBalance.Closed (balance : MaterialBalance) : Prop :=
  balance.inputQ + balance.reserveDrawQ = balance.outputQ + balance.wasteQ

def MaterialBalance.closedB (balance : MaterialBalance) : Bool :=
  balance.inputQ + balance.reserveDrawQ == balance.outputQ + balance.wasteQ

structure TransitionReceipt where
  index : Nat
  operationHash : Digest
  parentWorldHash : Digest
  childWorldHash : Digest
  balances : List MaterialBalance
  durationUs : Nat
  energyMj : Nat
  deriving DecidableEq, Repr, Lean.FromJson, Lean.ToJson

def ReceiptMassClosed (receipt : TransitionReceipt) : Prop :=
  receipt.balances.all MaterialBalance.closedB = true

def AllReceiptsMassClosed (receipts : List TransitionReceipt) : Prop :=
  receipts.all (fun receipt => receipt.balances.all MaterialBalance.closedB) = true

def receiptChainB : Digest → List TransitionReceipt → Digest → Bool
  | start, [], finish => start == finish
  | start, receipt :: rest, finish =>
      receipt.parentWorldHash == start &&
      receiptChainB receipt.childWorldHash rest finish

def ReceiptChain
    (start : Digest) (receipts : List TransitionReceipt) (finish : Digest) : Prop :=
  receiptChainB start receipts finish = true

def receiptsIndexedFromB : Nat → List TransitionReceipt → Bool
  | _, [] => true
  | expected, receipt :: rest =>
      receipt.index == expected && receiptsIndexedFromB (expected + 1) rest

def ReceiptsIndexedFrom (expected : Nat) (receipts : List TransitionReceipt) : Prop :=
  receiptsIndexedFromB expected receipts = true

def TotalDurationUs : List TransitionReceipt → Nat
  | [] => 0
  | receipt :: rest => receipt.durationUs + TotalDurationUs rest

def TotalEnergyMj : List TransitionReceipt → Nat
  | [] => 0
  | receipt :: rest => receipt.energyMj + TotalEnergyMj rest

structure TransitionInput where
  worldSpecHash : Digest
  parentWorldHash : Digest
  programHash : Digest
  sequenceBefore : Nat
  deriving DecidableEq, Repr, Lean.FromJson, Lean.ToJson

structure TransitionOutput where
  childWorldHash : Digest
  sequenceAfter : Nat
  totalDurationUs : Nat
  totalEnergyMj : Nat
  deriving DecidableEq, Repr, Lean.FromJson, Lean.ToJson

def TransitionAccountingConditions
    (input : TransitionInput)
    (output : TransitionOutput)
    (receipts : List TransitionReceipt) : Prop :=
  receipts ≠ [] ∧
  ReceiptChain input.parentWorldHash receipts output.childWorldHash ∧
  ReceiptsIndexedFrom 0 receipts ∧
  AllReceiptsMassClosed receipts ∧
  output.sequenceAfter = input.sequenceBefore + receipts.length ∧
  output.totalDurationUs = TotalDurationUs receipts ∧
  output.totalEnergyMj = TotalEnergyMj receipts

def validTransitionAccountingB
    (input : TransitionInput)
    (output : TransitionOutput)
    (receipts : List TransitionReceipt) : Bool :=
  receipts.isEmpty == false &&
  receiptChainB input.parentWorldHash receipts output.childWorldHash &&
  receiptsIndexedFromB 0 receipts &&
  receipts.all (fun receipt => receipt.balances.all MaterialBalance.closedB) &&
  output.sequenceAfter == input.sequenceBefore + receipts.length &&
  output.totalDurationUs == TotalDurationUs receipts &&
  output.totalEnergyMj == TotalEnergyMj receipts

def ValidTransitionAccounting
    (input : TransitionInput)
    (output : TransitionOutput)
    (receipts : List TransitionReceipt) : Prop :=
  validTransitionAccountingB input output receipts = true

theorem valid_transition_accounting_conditions
    (input : TransitionInput)
    (output : TransitionOutput)
    (receipts : List TransitionReceipt)
    (valid : ValidTransitionAccounting input output receipts) :
    TransitionAccountingConditions input output receipts := by
  simp [ValidTransitionAccounting, validTransitionAccountingB] at valid
  rcases valid with
    ⟨⟨⟨⟨⟨⟨nonempty, chain⟩, indexed⟩, massClosed⟩, sequence⟩, duration⟩, energy⟩
  refine ⟨nonempty, chain, indexed, ?_, sequence, duration, energy⟩
  simpa [AllReceiptsMassClosed] using massClosed

theorem valid_transition_has_strict_sequence_advance
    (input : TransitionInput)
    (output : TransitionOutput)
    (receipts : List TransitionReceipt)
    (valid : ValidTransitionAccounting input output receipts) :
    input.sequenceBefore < output.sequenceAfter := by
  have conditions := valid_transition_accounting_conditions input output receipts valid
  rw [conditions.2.2.2.2.1]
  cases receipts with
  | nil => exact (conditions.1 rfl).elim
  | cons _ rest =>
      exact Nat.lt_add_of_pos_right (Nat.succ_pos rest.length)

theorem valid_transition_preserves_lineage
    (input : TransitionInput)
    (output : TransitionOutput)
    (receipts : List TransitionReceipt)
    (valid : ValidTransitionAccounting input output receipts) :
    ReceiptChain input.parentWorldHash receipts output.childWorldHash := by
  exact (valid_transition_accounting_conditions input output receipts valid).2.1

theorem valid_transition_preserves_mass_closure
    (input : TransitionInput)
    (output : TransitionOutput)
    (receipts : List TransitionReceipt)
    (valid : ValidTransitionAccounting input output receipts) :
    AllReceiptsMassClosed receipts := by
  exact (valid_transition_accounting_conditions input output receipts valid).2.2.2.1

end Mechanogenesis
