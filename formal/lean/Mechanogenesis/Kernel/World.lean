import Mechanogenesis.Kernel.Frame

namespace Mechanogenesis

abbrev Digest := String
abbrev EntityId := String

structure InventoryEntry where
  itemId : EntityId
  materialId : EntityId
  quantity : Nat
  deriving DecidableEq, Repr

structure Capability where
  capabilityId : EntityId
  kind : String
  errorBoundMicrometres : Nat
  validRegimeDigest : Digest
  evidenceDigest : Digest
  deriving DecidableEq, Repr

/-- The authoritative abstract world identity. Rich geometry and fields live
in content-addressed objects referenced by `worldDigest`; no backend owns a
second independent meaning of world state. -/
structure WorldState where
  schemaId : String
  worldSpecDigest : Digest
  worldDigest : Digest
  sequence : Nat
  inventory : List InventoryEntry
  capabilities : List Capability
  deriving DecidableEq, Repr

def DescendsFrom (parent child : WorldState) : Prop :=
  parent.schemaId = child.schemaId ∧
  parent.worldSpecDigest = child.worldSpecDigest ∧
  parent.sequence < child.sequence

theorem world_descent_is_transitive
    {first second third : WorldState}
    (firstSecond : DescendsFrom first second)
    (secondThird : DescendsFrom second third) :
    DescendsFrom first third := by
  exact ⟨firstSecond.1.trans secondThird.1,
    firstSecond.2.1.trans secondThird.2.1,
    Nat.lt_trans firstSecond.2.2 secondThird.2.2⟩

end Mechanogenesis
