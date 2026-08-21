import Mechanogenesis.Kernel.Evidence

namespace Mechanogenesis

inductive TrustClass where
  | kernelVerified
  | certificateChecked
  | empiricallyCalibrated
  | advisory
  deriving DecidableEq, Repr

/-- An external backend is acceptable only through a pure checker and a proof
that checker acceptance transfers the declared postcondition. -/
structure RefinementContract
    (Input : Type u) (Output : Type v) (Certificate : Type w) where
  trustClass : TrustClass
  precondition : Input → Prop
  postcondition : Input → Output → Prop
  check : Input → Output → Certificate → Bool
  checkerSound : ∀ input output certificate,
    check input output certificate = true →
    precondition input →
    postcondition input output

structure CheckedRun
    {Input : Type u} {Output : Type v} {Certificate : Type w}
    (contract : RefinementContract Input Output Certificate) where
  input : Input
  output : Output
  certificate : Certificate
  precondition : contract.precondition input
  accepted : contract.check input output certificate = true

theorem checked_run_satisfies_contract
    {Input : Type u} {Output : Type v} {Certificate : Type w}
    {contract : RefinementContract Input Output Certificate}
    (run : CheckedRun contract) :
    contract.postcondition run.input run.output := by
  exact contract.checkerSound
    run.input run.output run.certificate run.accepted run.precondition

end Mechanogenesis
