/-
Conditional theorems for the Gθ -> MRS research-strategy boundary.

These theorems characterize when a strategy can possibly return a feasible
physical candidate.  They do not assert that an LLM discovers such a strategy,
that the world models are complete, or that a simulator is physically faithful.
-/

universe u v w

structure ResearchStrategy (Candidate : Type u) where
  support : List Candidate

def Reachable {Candidate : Type u}
    (strategy : ResearchStrategy Candidate)
    (candidate : Candidate) : Prop :=
  candidate ∈ strategy.support

def HasFeasibleSupport {Candidate : Type u}
    (strategy : ResearchStrategy Candidate)
    (Feasible : Candidate → Prop) : Prop :=
  ∃ candidate, Reachable strategy candidate ∧ Feasible candidate

def SupportedSelection {Candidate : Type u}
    (strategy : ResearchStrategy Candidate)
    (selection : Option Candidate) : Prop :=
  ∀ candidate, selection = some candidate → Reachable strategy candidate

def SelectsFeasible {Candidate : Type u}
    (Feasible : Candidate → Prop)
    (selection : Option Candidate) : Prop :=
  ∃ candidate, selection = some candidate ∧ Feasible candidate

/- A feasible output is possible exactly when the generated strategy support
contains at least one feasible candidate.  Better downstream selection cannot
repair a support set that excludes every feasible candidate. -/
theorem feasible_output_iff_feasible_strategy_support
    {Candidate : Type u}
    (strategy : ResearchStrategy Candidate)
    (Feasible : Candidate → Prop) :
    (∃ selection,
      SupportedSelection strategy selection ∧
      SelectsFeasible Feasible selection) ↔
    HasFeasibleSupport strategy Feasible := by
  constructor
  · intro outputExists
    rcases outputExists with ⟨selection, supported, candidate, selected, feasible⟩
    exact ⟨candidate, supported candidate selected, feasible⟩
  · intro supportExists
    rcases supportExists with ⟨candidate, reachable, feasible⟩
    refine ⟨some candidate, ?_, candidate, rfl, feasible⟩
    intro selectedCandidate selected
    cases selected
    exact reachable

def BudgetedStrategy {Candidate : Type u}
    (strategy : ResearchStrategy Candidate)
    (budget : Nat) : ResearchStrategy Candidate :=
  { support := strategy.support.take budget }

/- The same phase boundary applies to the prefix that an ordered strategy can
execute within budget.  A candidate after that prefix is not operationally
reachable even if it occurs somewhere in the unbounded proposal. -/
theorem budgeted_feasible_output_iff_feasible_prefix
    {Candidate : Type u}
    (strategy : ResearchStrategy Candidate)
    (Feasible : Candidate → Prop)
    (budget : Nat) :
    (∃ selection,
      SupportedSelection (BudgetedStrategy strategy budget) selection ∧
      SelectsFeasible Feasible selection) ↔
    HasFeasibleSupport (BudgetedStrategy strategy budget) Feasible := by
  exact feasible_output_iff_feasible_strategy_support
    (BudgetedStrategy strategy budget) Feasible

def RobustFeasible {Candidate : Type u} {World : Type v}
    (worlds : List World)
    (Passes : Candidate → World → Prop)
    (candidate : Candidate) : Prop :=
  ∀ world, world ∈ worlds → Passes candidate world

/- Adding a grounded world hypothesis cannot turn a robustly infeasible
candidate into a robustly feasible one under the same pass predicate. -/
theorem grounded_world_expansion_cannot_expand_candidate_feasibility
    {Candidate : Type u} {World : Type v}
    (worlds : List World)
    (newWorld : World)
    (Passes : Candidate → World → Prop)
    (candidate : Candidate)
    (expanded : RobustFeasible (newWorld :: worlds) Passes candidate) :
    RobustFeasible worlds Passes candidate := by
  intro world member
  exact expanded world (List.mem_cons_of_mem newWorld member)

/- A separating hypothesis strictly removes a particular candidate: it passed
every previous model but fails the new intervention model. -/
theorem separating_world_removes_candidate
    {Candidate : Type u} {World : Type v}
    (worlds : List World)
    (newWorld : World)
    (Passes : Candidate → World → Prop)
    (candidate : Candidate)
    (_oldRobust : RobustFeasible worlds Passes candidate)
    (failsNew : ¬ Passes candidate newWorld) :
    ¬ RobustFeasible (newWorld :: worlds) Passes candidate := by
  intro expanded
  apply failsNew
  exact expanded newWorld (by simp)

/- The trusted compiler certificate transfers physical feasibility only under
an explicit compiler-soundness premise.  Parser acceptance by itself is not a
physics proof. -/
theorem accepted_compilation_certifies_reachable_feasible
    {Candidate : Type u} {Program : Type w}
    (strategy : ResearchStrategy Candidate)
    (Feasible : Candidate → Prop)
    (Compiles : Candidate → Program → Prop)
    (Accepted : Program → Prop)
    (compilerSound :
      ∀ candidate program,
        Compiles candidate program → Accepted program → Feasible candidate)
    (candidate : Candidate)
    (program : Program)
    (reachable : Reachable strategy candidate)
    (compiled : Compiles candidate program)
    (accepted : Accepted program) :
    Reachable strategy candidate ∧ Feasible candidate := by
  exact ⟨reachable, compilerSound candidate program compiled accepted⟩
