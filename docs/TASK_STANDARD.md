# Task Standard 0.1

A task is a directory with a public problem, graduated guidance, trusted
evaluator and private cases.

```text
task.toml
public/{world,inventory,equipment,access,disturbances,evaluator_contract}.json
guidance/G1.md ... guidance/G5.md
evaluator/<entrypoint>
private/<hidden assets>
```

`task.toml` declares track, evidence ceiling, available guidance levels,
generation count, minimum promotions, robustness threshold, evaluator command
and a seven-dimensional resource budget.

The runner exposes only `task.toml`, `public/`, one `mission.md` and the public
package digest. A submission contains system identity, declared evidence tier,
resource use and a contiguous list of generations. Each generation contains:

- distinct parent/child process hashes;
- distinct parent/child world hashes;
- all nine content-addressed MRS objects;
- an inline, hash-bound artifact;
- exact-integer construction receipts;
- experiment and generator-fork receipts.

For the current fixture tasks, `compiler_certificate` is a composed Lean
Sovereign Kernel object. It embeds the lowered canonical program, metrology
refinement certificates, assumption ledger and transition receipts. The
trusted evaluator regenerates this complete object from the stored construction
program and independent replay before considering promotion.
Lean then requires positional equality between canonical operation hashes and
receipt hashes, and exactly one certificate for every calibration operation.

The trusted report binds task package and private evaluator-bundle digests. For
each generation it states the artifact hash, confidence bounds, margin, net
value, robustness, evidence tier and two Recursive Research Credit deltas.

Promotion is fail-closed:

$$
L_{child}\ge U_{parent}+m
\land N>0
\land R\ge R_{min}.
$$

Recursive Learner promotion also requires nonnegative time and budget RRC, with
at least one strictly positive. Rejected generations do not advance either
process or world lineage.

Material quantities use task-declared integer quanta. Every receipt enforces
`input + reserve_draw = output + waste`; floating-point tolerance is not used
for accounting.
