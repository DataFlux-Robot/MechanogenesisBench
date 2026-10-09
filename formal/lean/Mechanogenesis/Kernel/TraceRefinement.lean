import Mechanogenesis.Kernel.Digest

namespace Mechanogenesis.TraceRefinement

/-!
# Trace -> receipt refinement

A receipt is not evidence that an event happened.  This module introduces the
minimum indexed relation needed to state the stronger claim: a concrete trace
faithfully refines the receipt that summarizes it.

The event language is intentionally small.  A runtime adapter must project its
raw subprocess/optimizer/checkpoint log into these fields before any receipt
certificate can claim `TraceFaithful`.  Hash values remain abstract `Digest`:
SHA-256 byte-level correctness belongs to the implementation TCB/refinement
boundary, not to this core file.
-/

structure Event where
  sequence : Nat
  inputDigest : Digest
  outputDigest : Digest
  cost : Nat
  deriving DecidableEq, Repr

structure Trace where
  events : List Event
  rawInputDigest : Digest
  rawOutputDigest : Digest
  deriving DecidableEq, Repr

structure Receipt where
  eventSummary : List Nat
  inputDigest : Digest
  outputDigest : Digest
  totalCost : Nat
  deriving DecidableEq, Repr


def projectEvents : List Event → List Nat
  | [] => []
  | event :: rest => event.sequence :: projectEvents rest

def projectCost : List Event → Nat
  | [] => 0
  | event :: rest => event.cost + projectCost rest

def TraceFaithful (trace : Trace) (receipt : Receipt) : Prop :=
  projectEvents trace.events = receipt.eventSummary ∧
  trace.rawInputDigest = receipt.inputDigest ∧
  trace.rawOutputDigest = receipt.outputDigest ∧
  projectCost trace.events = receipt.totalCost

instance traceFaithfulDecidable (trace : Trace) (receipt : Receipt) :
    Decidable (TraceFaithful trace receipt) := by
  unfold TraceFaithful projectEvents projectCost
  infer_instance

/-- A faithful trace determines every receipt field; no receipt field can be
silently invented after the trace has been fixed. -/
theorem traceFaithful_determines_receipt
    {trace : Trace} {receipt receipt' : Receipt}
    (h : TraceFaithful trace receipt)
    (h' : TraceFaithful trace receipt') : receipt = receipt' := by
  rcases h with ⟨he, hi, ho, hc⟩
  rcases h' with ⟨he', hi', ho', hc'⟩
  cases receipt
  cases receipt'
  simp_all [projectEvents, projectCost]

/-- The cost field of a faithful receipt is the fold of concrete event costs. -/
theorem traceFaithful_cost
    {trace : Trace} {receipt : Receipt}
    (h : TraceFaithful trace receipt) :
    projectCost trace.events = receipt.totalCost := h.2.2.2

/-- Empty traces can only refine the unique empty receipt summary with matching
input/output identities and zero cost. -/
theorem emptyTraceFaithful_iff
    {inputDigest outputDigest : Digest} {receipt : Receipt} :
    TraceFaithful
      {events := [], rawInputDigest := inputDigest, rawOutputDigest := outputDigest}
      receipt ↔
      receipt = {
        eventSummary := [], inputDigest := inputDigest,
        outputDigest := outputDigest, totalCost := 0
      } := by
  constructor
  · intro h
    rcases h with ⟨he, hi, ho, hc⟩
    cases receipt
    simp_all [projectEvents, projectCost]
  · intro h
    subst receipt
    simp [TraceFaithful, projectEvents, projectCost]

end Mechanogenesis.TraceRefinement
