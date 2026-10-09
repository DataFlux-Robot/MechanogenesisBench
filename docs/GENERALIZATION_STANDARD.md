# Mechanogenesis Generalization Standard 0.1

**English** | [简体中文](GENERALIZATION_STANDARD.zh-CN.md)

MechanogenesisBench 0.7 replaces a single aggregate generalization score with
three planes that cannot compensate for one another:

1. **Task universe:** five executable factor axes—world, intervention,
   embodiment, error state and mechanism;
2. **Anti-shortcut evidence:** training evidence must contain a
   same-projection/opposite-target witness for every registered low-order
   projection;
3. **Engineering and recursive evidence:** sealed compositional
   extrapolation, worst-mechanism performance, canonical/Lean/replay checks,
   an independent backend, physical trials and optional actual/placebo RRC.

## Why “sufficiently dispersed points” is not enough

Geometric distance, data entropy and single-axis coverage can all be high while
a projection-only shortcut still fits the entire training set. This standard
defines a shortcut as destroyed only when two executed cases are identical on
every axis visible to the shortcut but have different evaluator-owned targets.

All first- and second-order axis projections are registered by default. A task
may add higher-order projections, but the projection set cannot be changed
after sealed results are observed.

## Data ABI

Each `FactorizedCase` contains:

- a `case_id` and split;
- five registered factors;
- a `target_signature`: canonical program, behavioral equivalence class or
  evaluator preference;
- the complete execution cost.

A factor must change canonical/evaluator execution semantics. Merely changing
a prompt or label does not count as coverage.

## Training algorithm

`build_shortcut_destruction_curriculum` operates only on an archive whose
cases have already been executed and whose targets are known. It supports
curriculum selection and an oracle ceiling; it cannot be deployed as the
selector for the next physical experiment.

The online phase uses `select_disagreement_experiment`.
`AcquisitionCandidate` explicitly contains no target. A frozen world model
supplies a target distribution and model hash through `CandidateTargetBelief`,
and the algorithm maximizes expected shortcut destruction per unit of complete
cost. Only the evaluator-revealed `FactorizedCase` after execution can shrink
the version space.

A world-model forecast cannot be solely responsible for acquisition. If its
decision-level lower bound does not cover the complete experiment cost, the
controller must abstain from the learned choice and call
`select_grounded_separating_experiment`. Under a residual projection, this
fallback fixes the projection value and chooses the farthest contrasts on
factors invisible to that projection; the candidate ABI still contains no
target. A structural contrast creates a separability opportunity, not a
collision certificate. Only an observed target difference after execution
destroys a shortcut.

If evidence supports a finite ambiguity budget $B$ for a projection, executing
$B+1$ structurally distinct contrasts forces at least one collision. Without
that upper bound, “sufficiently dispersed” is only a search heuristic, not a
finite success guarantee. A learned selector can reduce average cost; only new
access, sensors, interventions or causal evidence that lowers a certifiable
$B$ can lower the worst-case threshold.

If no executable witness exists while a residual shortcut remains, training
must stop with `non_identifiable/access_insufficient`. The next action should
create a new intervention, sensor, fixture or world—not copy more samples from
the same distribution.

`lean_guided_training_objective` includes task, counterfactual-ranking,
intervention-prediction, nuisance-consistency, future-RRC and
shortcut-survival terms. Description-length or weight-decay pressure is
enabled only after the residual shortcut set is empty.

## Sealed split

A valid compositional split simultaneously requires:

- no overlap in case IDs or complete factor tuples;
- every sealed single-axis value to appear in training;
- at least one sealed second-order combination absent from training;
- training evidence to destroy every registered projection shortcut;
- both overall and worst-mechanism accuracy/regret to pass their gates.

The last condition cannot be replaced by the overall mean.

## HWE-style engineering evidence gate

Every sealed case must pass canonical parsing, the Lean kernel, reference
replay and an independent backend, with at least three independent numerical
seeds. A physical claim additionally requires at least one real physical trial.
This design adopts HWE Bench's staged engineering-verification principle; it
does not claim that mechanical manufacturing and FPGA verification are
equivalent.

Default command:

```bash
mbench generalization audit corpus.json \
  --predictions predictions.json \
  --engineering-receipt engineering.json
```

A simulation-only development report must explicitly pass
`--allow-simulation-only`; its output has no physical evidence tier.

## Leaderboard output

Results are not collapsed into a hidden weighted score. At minimum, report in
parallel:

- engineering frontier: success/performance/time/cost;
- sealed compositional accuracy/regret and the worst-mechanism floor;
- destroyed/registered shortcut classes;
- evidence tier;
- for a Recursive Learner: actual-vs-parent, actual-vs-placebo and complete net
  value.

## Claim boundary

Passing this standard establishes only finite extrapolation evidence for the
registered task universe and shortcut classes. It proves neither universal
generalization to arbitrary new worlds nor completeness of the physical model.
