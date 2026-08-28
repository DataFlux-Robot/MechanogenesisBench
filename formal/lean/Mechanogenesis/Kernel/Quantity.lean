namespace Mechanogenesis

inductive Dimension where
  | length
  | angle
  | duration
  | energy
  | mass
  | count
  deriving DecidableEq, Repr

/-- Nonnegative fixed-point physical quantity. `scale` names the number of
quanta per canonical unit; the kernel never silently converts scales. -/
structure Quantity (dimension : Dimension) where
  quanta : Nat
  scale : Nat
  scalePositive : 0 < scale

abbrev LengthQ := Quantity .length
abbrev DurationQ := Quantity .duration
abbrev EnergyQ := Quantity .energy
abbrev MassQ := Quantity .mass

def SameScale {dimension : Dimension}
    (left right : Quantity dimension) : Prop :=
  left.scale = right.scale

def Quantity.le {dimension : Dimension}
    (left right : Quantity dimension) : Prop :=
  SameScale left right ∧ left.quanta ≤ right.quanta

theorem quantity_le_trans
    {dimension : Dimension}
    {first second third : Quantity dimension}
    (firstSecond : Quantity.le first second)
    (secondThird : Quantity.le second third) :
    Quantity.le first third := by
  exact ⟨firstSecond.1.trans secondThird.1, Nat.le_trans firstSecond.2 secondThird.2⟩

end Mechanogenesis
