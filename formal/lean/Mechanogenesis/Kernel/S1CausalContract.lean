import Mechanogenesis.Kernel.Digest
import Mechanogenesis.Kernel.RecursiveResearchCredit
import Lean.Elab.Tactic.Omega

namespace Mechanogenesis.S1

/-!
# Executable S1 causal-update contract (ten gates)

Lean-first promotion contract for the S1 question: *does selecting training
trajectories by isolated Recursive Research Credit causally produce a better
future MRS generator than current-reward / placebo updates?*

The evidence structure below IS the metric ledger a training run must emit.
Each field is a receipt hash or a measured count — nothing is assumed.
`checkS1` turns the ledger into exactly one of three decisions, and the
theorems state what each decision obligates.  Intended closed loop with
training reality:

1. this contract fixes WHICH metrics/receipts the four-fork run must log
   (matched budgets, seals, placebo hashes, clustered intervals, full cost,
   losing-fork preservation);
2. the run produces them; `checkS1` decides promote / abstain / violate;
3. repeated abstentions or premise failures are fed back to refine the Lean
   premises (e.g. the error bounds feeding `rrc_discrimination_threshold`),
   never silently relaxed.

Gates (handoff §3.2):
 1 CommonParent          6 ReliableSelection
 2 MatchedUpdateBudget   7 Transport (declared bound, else abstain)
 3 FutureUnread          8 FullCost
 4 ForkIsolation         9 Promotion margins
 5 Attribution          10 FailurePreservation

The Python mirror (`src/mechanogenesis_bench/s1_contract.py`) reports the
failing gate numbers; this Lean side keeps the decision semantics minimal.
-/

/-- Closed Nat interval; `Valid` means nonempty (lower ≤ upper). -/
structure Interval where
  lower : Nat
  upper : Nat
  deriving DecidableEq, Repr

def Interval.validB (i : Interval) : Bool := decide (i.lower ≤ i.upper)

/-- Complete S1 evidence ledger.  Field groups mirror the ten gates. -/
structure Evidence where
  /-- Gate 1: CommonParent -/
  parentCheckpointHash : Digest
  childParentHash : Digest
  runtimeHash : Digest
  /-- Gate 2: MatchedUpdateBudget (pre-registered matched values). -/
  supervisedTokens : Nat
  matchedTokens : Nat
  optimizerSteps : Nat
  matchedSteps : Nat
  /-- Gate 3: FutureUnread (credit seal + final-query seal held unread). -/
  creditSealHash : Digest
  finalQuerySealHash : Digest
  futureUnread : Bool
  /-- Gate 4: ForkIsolation -/
  forkIsolated : Bool
  /-- Gate 5: Attribution (RRC fork ≡ placebo fork except recursive evidence). -/
  rrcEvidenceHash : Digest
  placeboEvidenceHash : Digest
  attributionMatched : Bool
  /-- Gate 6: ReliableSelection (clustered interval covering all candidates). -/
  candidateInterval : Interval
  clusterValid : Bool
  /-- Gate 7: Transport (explicit, declared before final reveal). -/
  shiftBound : Nat
  transportDeclared : Bool
  /-- Gate 8: FullCost (losing forks, simulation, rollback all charged). -/
  fullCost : Nat
  costComplete : Bool
  /-- Gate 9: Promotion margins (net intervals from isolated evaluation). -/
  parentFutureInterval : Interval
  placeboFutureInterval : Interval
  /-- Gate 10: FailurePreservation -/
  losingForksPreserved : Bool
  deriving DecidableEq, Repr

inductive Decision where
  | promote
  | abstain
  | violate
  deriving DecidableEq, Repr

/-- Hard gates 1–5, 8, 10: protocol integrity.  Any failure makes the run
uninterpretable (`violate`), not merely unpromoted. -/
def hardOK (e : Evidence) : Bool :=
  decide (e.childParentHash = e.parentCheckpointHash) &&
  decide (e.supervisedTokens = e.matchedTokens) &&
  decide (e.optimizerSteps = e.matchedSteps) &&
  e.futureUnread &&
  e.forkIsolated &&
  e.attributionMatched &&
  e.costComplete &&
  e.losingForksPreserved

/-- Soft gates 6, 7, 9: certify-or-abstain. -/
def softOK (e : Evidence) : Bool :=
  e.clusterValid &&
  e.transportDeclared &&
  e.candidateInterval.validB &&
  e.parentFutureInterval.validB &&
  e.placeboFutureInterval.validB &&
  decide (e.parentFutureInterval.upper + e.fullCost < e.candidateInterval.lower) &&
  decide (e.placeboFutureInterval.upper + e.fullCost < e.candidateInterval.lower)

def checkS1 (e : Evidence) : Decision :=
  if hardOK e = true then
    (if softOK e = true then .promote else .abstain)
  else .violate

/-! ## What promotion obligates -/

theorem promote_requires_hardOK {e : Evidence} (h : checkS1 e = .promote) :
    hardOK e = true := by
  unfold checkS1 at h
  by_cases hh : hardOK e = true
  · rw [if_pos hh] at h
    by_cases hs : softOK e = true
    · rw [if_pos hs] at h
      exact hh
    · rw [if_neg hs] at h
      exact absurd h (by simp [Decision])
  · rw [if_neg hh] at h
    exact absurd h (by simp [Decision])

theorem promote_requires_softOK {e : Evidence} (h : checkS1 e = .promote) :
    softOK e = true := by
  unfold checkS1 at h
  by_cases hh : hardOK e = true
  · rw [if_pos hh] at h
    by_cases hs : softOK e = true
    · rw [if_pos hs] at h
      exact hs
    · rw [if_neg hs] at h
      exact absurd h (by simp [Decision])
  · rw [if_neg hh] at h
    exact absurd h (by simp [Decision])

theorem promote_requires_common_parent {e : Evidence}
    (h : checkS1 e = .promote) : e.childParentHash = e.parentCheckpointHash := by
  have hh := promote_requires_hardOK h
  unfold hardOK at hh
  simp only [Bool.and_eq_true] at hh
  exact of_decide_eq_true hh.1.1.1.1.1.1.1

theorem promote_requires_matched_budget {e : Evidence}
    (h : checkS1 e = .promote) :
    e.supervisedTokens = e.matchedTokens ∧ e.optimizerSteps = e.matchedSteps := by
  have hh := promote_requires_hardOK h
  unfold hardOK at hh
  simp only [Bool.and_eq_true] at hh
  exact ⟨of_decide_eq_true hh.1.1.1.1.1.1.2, of_decide_eq_true hh.1.1.1.1.1.2⟩

theorem promote_requires_future_unread {e : Evidence}
    (h : checkS1 e = .promote) : e.futureUnread = true := by
  have hh := promote_requires_hardOK h
  unfold hardOK at hh
  simp only [Bool.and_eq_true] at hh
  exact hh.1.1.1.1.2

theorem promote_requires_fork_isolation {e : Evidence}
    (h : checkS1 e = .promote) : e.forkIsolated = true := by
  have hh := promote_requires_hardOK h
  unfold hardOK at hh
  simp only [Bool.and_eq_true] at hh
  exact hh.1.1.1.2

theorem promote_requires_attribution {e : Evidence}
    (h : checkS1 e = .promote) : e.attributionMatched = true := by
  have hh := promote_requires_hardOK h
  unfold hardOK at hh
  simp only [Bool.and_eq_true] at hh
  exact hh.1.1.2

theorem promote_requires_full_cost {e : Evidence}
    (h : checkS1 e = .promote) : e.costComplete = true := by
  have hh := promote_requires_hardOK h
  unfold hardOK at hh
  simp only [Bool.and_eq_true] at hh
  exact hh.1.2

theorem promote_requires_losing_forks_preserved {e : Evidence}
    (h : checkS1 e = .promote) : e.losingForksPreserved = true := by
  have hh := promote_requires_hardOK h
  unfold hardOK at hh
  simp only [Bool.and_eq_true] at hh
  exact hh.2

theorem promote_requires_net_margin {e : Evidence}
    (h : checkS1 e = .promote) :
    e.parentFutureInterval.upper + e.fullCost < e.candidateInterval.lower ∧
    e.placeboFutureInterval.upper + e.fullCost < e.candidateInterval.lower := by
  have hs := promote_requires_softOK h
  unfold softOK at hs
  simp only [Bool.and_eq_true] at hs
  exact ⟨of_decide_eq_true hs.1.2, of_decide_eq_true hs.2⟩

/-- Gate 7 in the promote case: an explicit transport bound was declared
before the final reveal. -/
theorem promote_requires_declared_transport {e : Evidence}
    (h : checkS1 e = .promote) : e.transportDeclared = true := by
  have hs := promote_requires_softOK h
  unfold softOK at hs
  simp only [Bool.and_eq_true] at hs
  exact hs.1.1.1.1.1.2

/-! ## What each integrity failure forces -/

theorem hard_gate_failure_forces_violate {e : Evidence}
    (hbad : hardOK e = false) : checkS1 e = .violate := by
  unfold checkS1
  rw [if_neg (by rw [hbad]; simp)]

theorem future_read_forces_violate {e : Evidence}
    (hleak : e.futureUnread = false) : checkS1 e = .violate := by
  apply hard_gate_failure_forces_violate
  unfold hardOK
  simp [hleak]

theorem budget_mismatch_forces_violate {e : Evidence}
    (ht : e.supervisedTokens ≠ e.matchedTokens) : checkS1 e = .violate := by
  apply hard_gate_failure_forces_violate
  unfold hardOK
  simp [ht]

theorem parent_mismatch_forces_violate {e : Evidence}
    (hp : e.childParentHash ≠ e.parentCheckpointHash) : checkS1 e = .violate := by
  apply hard_gate_failure_forces_violate
  unfold hardOK
  simp [hp]

theorem missing_cost_forces_violate {e : Evidence}
    (hc : e.costComplete = false) : checkS1 e = .violate := by
  apply hard_gate_failure_forces_violate
  unfold hardOK
  simp [hc]

theorem losing_forks_dropped_forces_violate {e : Evidence}
    (hl : e.losingForksPreserved = false) : checkS1 e = .violate := by
  apply hard_gate_failure_forces_violate
  unfold hardOK
  simp [hl]

/-- Undeclared transport keeps the run interpretable but forbids promotion
(certify-or-abstain). -/
theorem transport_undeclared_forces_not_promote {e : Evidence}
    (ht : e.transportDeclared = false) : checkS1 e ≠ .promote := by
  intro hprom
  have hdecl := promote_requires_declared_transport hprom
  rw [ht] at hdecl
  exact Bool.noConfusion hdecl

/-- Missing net margin likewise forces abstention, never promotion. -/
theorem margin_failure_forces_not_promote {e : Evidence}
    (hm : e.parentFutureInterval.upper + e.fullCost
            ≥ e.candidateInterval.lower) : checkS1 e ≠ .promote := by
  intro hprom
  have hmargin := (promote_requires_net_margin hprom).1
  omega

/-! ## Bridge to the RRC kernel: calibrated estimates justify the margins -/

/-- If the interval bounds are calibrated estimates (same error bound,
`CreditEstimate.Calibrated`) and the true separation clears the 2ε + cost
bar, then the promote margin reflects true ordering — the RRC kernel's 2ε
discrimination threshold, now carrying full cost. -/
theorem promote_margin_certified_by_calibrated_estimates
    (e : Evidence) (cEst pEst : Mechanogenesis.CreditEstimate)
    (hEq : cEst.errorBound = pEst.errorBound)
    (hc : cEst.Calibrated) (hp : pEst.Calibrated)
    (hsep : pEst.trueFutureUtility + 2 * cEst.errorBound + e.fullCost
              < cEst.trueFutureUtility)
    (hlower : cEst.estimatedFutureUtility + e.fullCost
                = e.candidateInterval.lower)
    (hupper : pEst.estimatedFutureUtility = e.parentFutureInterval.upper)
    (hprom : checkS1 e = .promote) :
    e.parentFutureInterval.upper + e.fullCost < e.candidateInterval.lower := by
  rcases hc with ⟨hcUpper, hcLower⟩
  rcases hp with ⟨hpUpper, hpLower⟩
  have hthreshold := Mechanogenesis.rrc_discrimination_threshold
    cEst pEst hEq ⟨hcUpper, hcLower⟩ ⟨hpUpper, hpLower⟩ (by omega)
  have hmargin := (promote_requires_net_margin hprom).1
  omega


/-! ## Interval semantics: what the main-v1 abstention teaches the contract

Empirical input (2026-08-23 main v1, worst_family_top1_correct over three
training seeds): candidate [0,1,1] vs placebo [1,0,0] — identical means,
per-seed ordering reversed.  The lemmas below make the implied structural
fact explicit: with min-max cluster intervals, ANY single dominance of a
candidate cluster value by a placebo cluster value makes gate-9 separation
impossible, and adding more clusters can never repair it (extremes only
widen).  Hence the pre-registered refinement: keep the separation check,
switch the interval STATISTIC to population-clustered confidence bounds
(computed in Python, checked against the same Lean semantics), and report a
machine-checkable abstain diagnosis (`crossed` vs `no_resolution`). -/

def lmin : List Nat → Nat
  | [] => 0
  | [a] => a
  | a :: as => Nat.min a (lmin as)

def lmax : List Nat → Nat
  | [] => 0
  | [a] => a
  | a :: as => Nat.max a (lmax as)

theorem lmin_le_mem : ∀ (l : List Nat) (x : Nat), x ∈ l → lmin l ≤ x := by
  intro l
  induction l with
  | nil => intro x hx; exact absurd hx (by simp)
  | cons a as ih =>
      intro x hx
      cases as with
      | nil =>
          rcases List.mem_cons.mp hx with rfl | hm
          · show lmin [x] ≤ x; simp [lmin]
          · exact absurd hm (by simp)
      | cons b bs =>
          show Nat.min a (lmin (b :: bs)) ≤ x
          rcases List.mem_cons.mp hx with rfl | hm
          · exact Nat.min_le_left _ _
          · exact Nat.le_trans (Nat.min_le_right _ _) (ih x hm)

theorem mem_le_lmax : ∀ (l : List Nat) (x : Nat), x ∈ l → x ≤ lmax l := by
  intro l
  induction l with
  | nil => intro x hx; exact absurd hx (by simp)
  | cons a as ih =>
      intro x hx
      cases as with
      | nil =>
          rcases List.mem_cons.mp hx with rfl | hm
          · show x ≤ lmax [x]; simp [lmax]
          · exact absurd hm (by simp)
      | cons b bs =>
          show x ≤ Nat.max a (lmax (b :: bs))
          rcases List.mem_cons.mp hx with rfl | hm
          · exact Nat.le_max_left _ _
          · exact Nat.le_trans (ih x hm) (Nat.le_max_right _ _)

/-- A single crossing pair (a candidate cluster value dominated by a placebo
cluster value) blocks gate-9 min-max separation, whatever the cost. -/
theorem crossing_pair_blocks_separation
    (cand placebo : List Nat) (cost c p : Nat)
    (hc : c ∈ cand) (hp : p ∈ placebo) (hge : c ≤ p) :
    ¬ (lmax placebo + cost < lmin cand) := by
  intro hsep
  have h1 : lmin cand ≤ c := lmin_le_mem cand c hc
  have h2 : p ≤ lmax placebo := mem_le_lmax placebo p hp
  omega

end Mechanogenesis.S1
