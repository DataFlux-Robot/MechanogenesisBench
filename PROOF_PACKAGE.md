# Proof Package

## Claim

The broad claim “the algorithm automatically produces strictly improving and
accelerating physical generations” is not derivable from a benchmark protocol
alone. The corrected claim implemented here is:

Given a trusted evaluator, a task-bounded evidence model, content-bound MRS
artifacts, closed construction lineage, exact resource/material accounting and
an accepted decision whose strictly positive margin, robustness and net-value tests all
hold, every promoted generation has a certified strict lower-bound improvement.
On the Recursive Learner track, promotion additionally requires non-worsening
held-out research time and budget, with at least one strictly improving under
an isolated generator-fork comparison.

Current-task reward alone is not a sufficient statistic for that recursive
credit.

For canonical Mechanism IR 0.3, local exact mass closure composes to global
closure; a conservative subtractive transition cannot create part mass; an
empty receipt sequence cannot change a world identity; and increasing an
explicit disturbance term cannot reduce the modeled worst-case error.

For the stateful physical-contribution fragment, if a fixture qualifies a
child process bound strictly below its parent process bound and the successor's
local artifact error is no worse than the parent's, then the successor's
absolute artifact-error bound is strictly smaller.

## Status

PROVABLE AFTER WEAKENING / EXTRA ASSUMPTION

## Assumptions

- The evaluator is trusted, version-bound and executes the stated contract.
- `beforeUpper` and `afterLower` are valid confidence bounds for the same
  higher-is-better task metric.
- The promotion rule requires a strictly positive margin.
- Evidence tiers accurately describe how the observations were obtained.
- Material quantities use one exact integer quantum per declared material.
- Generator forks share the parent checkpoint, held-out task distribution and
  budget; otherwise measured future gain is not causally attributable.
- A benchmark certificate is not a proof that the underlying physical model is
  complete or that an unmodelled disturbance cannot invalidate it.
- Mechanism IR geometry facts, material-density ratios and disturbance bounds
  are assumed to match the executable inputs. The Lean layer proves
  preservation implications, not those empirical premises.
- The fixture-local and qualification-transfer bounds are valid for the same
  machine/setup regime, the qualified process is actually cited by successor
  construction, and successor local error is no greater than parent local
  error.

## Notation

- $U_b$ is the upper confidence bound of the parent metric.
- $L_c$ is the lower confidence bound of the child metric.
- $m>0$ is the required promotion margin.
- $R$ is robustness pass rate and $R_{min}$ its threshold.
- $N$ is task-defined net value after resource costs.
- Recursive Research Credit compares held-out future research cost between
  isolated parent and child generator forks.
- $p_0,p_1$ are parent/qualified process-error bounds and
  $\ell_0,\ell_1$ are parent/successor local artifact-error bounds.

## Proof Strategy

Use direct conjunction elimination from the fail-closed promotion predicate,
then compose $U_b < U_b+m$ with $U_b+m\le L_c$. Give constructive
counterexamples for the stronger reward-sufficiency and non-isolated causal
attribution claims. For the physical-contribution result, combine one strict
process inequality with one weak local-artifact inequality using monotonicity
of natural-number addition.

## Dependency Map

1. Strict bounded gain depends on exact acceptance, $m>0$, and comparable
   confidence bounds.
2. Robustness and positive net value follow from separate promotion gates.
3. Recursive efficiency gain depends on isolated fork evidence and the
   Recursive Learner gate.
4. Current reward insufficiency uses two trajectories with identical current
   reward and different future research value.
5. Causal attribution uses identical-parent/task/budget isolation; observed
   improvement without these conditions is insufficient.
6. Mechanism material closure follows by induction over operation-local
   balances. No-creation and receipt-chain statements follow directly from the
   subtractive and transition constructors. Error monotonicity follows from
   nonnegative integer addition.
7. The physical-contribution result depends separately on strict process-bound
   improvement and non-worsening successor-local error; monotonicity of natural
   number addition composes them into strict absolute-artifact improvement.

## Proof

Step 1. Exact acceptance yields
$$
U_b+m\le L_c,\qquad N>0,\qquad R\ge R_{min}.
$$
These are separate conjuncts; none is inferred from a scalar aggregate.

Step 2. Since $m>0$, addition is strictly monotone, so
$$
U_b<U_b+m.
$$
Combining this inequality with $U_b+m\le L_c$ by transitivity gives
$$
U_b<L_c.
$$
Thus the child’s certified lower bound exceeds the parent’s certified upper
bound. This is stronger than comparing two point estimates, but remains
conditional on the validity of the bounds.

Step 3. On a Recursive Learner episode, exact promotion additionally requires
$$
T_c\le T_b,\qquad B_c\le B_b,
$$
and
$$
T_c<T_b\ \lor\ B_c<B_b.
$$
Therefore accepted recursive credit cannot be obtained by trading an
unreported regression in one declared efficiency coordinate for improvement
in the other, and at least one coordinate improves strictly.

Step 4. Let trajectories $a$ and $b$ both have current reward $10$, while
their future research values are respectively $1$ and $2$. They are
indistinguishable to a statistic containing only current reward, yet their
recursive values differ. Hence current reward is not sufficient in general.

Step 5. Let an observed fork have future costs $10$ and $5$, but use a
different parent checkpoint. The numerical improvement holds while the
isolation predicate is false. Consequently the improvement cannot be assigned
to the generator update under the stated causal contract. This establishes the
need for isolated forks rather than merely future-looking reward.

Step 6. For a list of local material balances $b_i$, assume each satisfies
$$
m_i^{in}+m_i^{reserve}=m_i^{out}+m_i^{waste}.
$$
Induction over the receipt list rewrites each head equality and applies the
tail hypothesis, giving equality of the corresponding global sums. For a
subtractive transition, $m_{stock}=m_{part}+m_{waste}$ immediately implies
$m_{part}\le m_{stock}$. The receipt-chain base constructor permits no world
change without a receipt. Finally, adding nonnegative disturbance $\delta$ to
an additive error budget yields $e\le e+\delta$.

`BenchmarkProtocol.lean` machine-checks Steps 1–5 and
`MechanismIR.lean` machine-checks Step 6.

Step 7. Let $p_0$ and $p_1$ be the parent and qualified process-error bounds,
and let $\ell_0$ and $\ell_1$ be the parent and successor local artifact-error
bounds. Qualification supplies
$$
p_1=e_f+e_t<p_0,
$$
where $e_f$ is the fixture-local bound and $e_t$ the bounded transfer error.
Require separately that $\ell_1\le\ell_0$. Monotonicity of addition with one
strict and one weak inequality gives
$$
p_1+\ell_1<p_0+\ell_0.
$$
The two sides are respectively the successor and parent absolute artifact
bounds. `MechanismIR.lean` machine-checks this implication. ∎

## Corrections or Missing Assumptions

- Universal physical improvement, automatic discovery and iteration
  acceleration are not proved.
- Conformance evidence checks the ABI and gates only. Simulation evidence needs
  calibrated uncertainty and cross-solver falsification; physical evidence
  needs instrumented execution and custody-bound receipts.
- “Strictly improves every generation” is only defensible for promoted
  generations; rejected and failed attempts remain part of the research trace.

## Open Risks

- A trusted evaluator can still encode the wrong objective or a misspecified
  physical model.
- Confidence-bound construction and generator-fork experimental power are
  task-specific and are not formalized in this first kernel.
- The current process-only runner does not prevent a hostile submission from
  reading local private assets. It is restricted to conformance development;
  competition runs require container/VM isolation and attestation.
- Axis-aligned AABB restrictions make volume accounting auditable but do not
  yet cover overlapping unions, general rotations, surface finish, fit forces,
  strength, wear or thermomechanical drift.
- The physical-contribution theorem does not prove that a fixture's stated
  local or transfer bounds are calibrated. It also fails if the successor
  gains enough local error to offset process improvement; that condition is an
  explicit gate rather than a hidden assumption.
