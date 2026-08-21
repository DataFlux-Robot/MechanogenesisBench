import Mechanogenesis.Kernel.AssumptionLedger

namespace Mechanogenesis

inductive EvidenceTier where
  | conformance
  | simulation
  | crossValidatedSimulation
  | hardwareInLoop
  | hardware
  | recursivePhysical
  deriving DecidableEq, Repr

def EvidenceTier.rank : EvidenceTier → Nat
  | .conformance => 0
  | .simulation => 1
  | .crossValidatedSimulation => 2
  | .hardwareInLoop => 3
  | .hardware => 4
  | .recursivePhysical => 5

def EvidenceTier.noStrongerThan
    (claimed ceiling : EvidenceTier) : Prop :=
  claimed.rank ≤ ceiling.rank

structure ObservationReceipt where
  deviceId : EntityId
  rawDataDigest : Digest
  preprocessingDigest : Digest
  calibrationDigest : Digest
  coordinateFrame : FrameId
  uncertaintyDigest : Digest
  custodyDigest : Digest
  deriving DecidableEq, Repr

structure EvidenceEnvelope where
  tier : EvidenceTier
  observations : List ObservationReceipt
  assumptionLedger : AssumptionLedger
  deriving Repr

theorem evidence_tier_trans
    {first second third : EvidenceTier}
    (firstSecond : first.noStrongerThan second)
    (secondThird : second.noStrongerThan third) :
    first.noStrongerThan third := by
  exact Nat.le_trans firstSecond secondThird

end Mechanogenesis
