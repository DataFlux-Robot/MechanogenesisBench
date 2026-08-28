import Mechanogenesis.Kernel.World

namespace Mechanogenesis

inductive AssumptionKind where
  | physicalModel
  | calibration
  | environment
  | cryptographicIdentity
  | numericalApproximation
  deriving DecidableEq, Repr

structure Assumption where
  assumptionId : String
  kind : AssumptionKind
  statementDigest : Digest
  scopeDigest : Digest
  deriving DecidableEq, Repr

abbrev AssumptionLedger := List Assumption

def AccountsFor (ledger : AssumptionLedger) (required : List String) : Prop :=
  ∀ assumptionId, assumptionId ∈ required →
    ∃ entry, entry ∈ ledger ∧ entry.assumptionId = assumptionId

theorem extending_ledger_preserves_accounting
    (ledger extension : AssumptionLedger)
    (required : List String)
    (accounts : AccountsFor ledger required) :
    AccountsFor (ledger ++ extension) required := by
  intro assumptionId requiredMember
  rcases accounts assumptionId requiredMember with ⟨entry, member, identifier⟩
  exact ⟨entry, List.mem_append_left extension member, identifier⟩

end Mechanogenesis
