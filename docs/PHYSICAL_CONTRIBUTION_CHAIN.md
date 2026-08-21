# Stateful Physical-Contribution Chain

## Why this extension exists

A generated tool is not yet physical recursive improvement. The tool must
change the process that produces a successor, and the successor program must
actually execute from that changed physical world. Mechanism IR 0.3 therefore
adds state continuation and machine-process qualification.

The bounded chain is:

```text
P0: base machine process, absolute setup bound 800 µm
  -> constructs S0 fixture
S0: local metrology bound 130 µm
  -> qualifies P1 with 10 µm transfer bound
P1: qualified machine process, absolute setup bound 140 µm
  -> constructs S1 from S0's child world
S1: local bound 130 µm; absolute-frame bound 270 µm
```

The first artifact under `P0` has absolute-frame bound
`800 + 130 = 930 µm`. The successor cites `P1` in its `machine_part`
instruction and has bound `140 + 130 = 270 µm`. This is the first executable
`S0 -> P1 -> S1` witness in the repository.

## Canonical semantics

Every machine contributes a base `machine_process` capability with an absolute
setup-error bound. `machine_part` must cite a capability for the same machine;
the constructed-part record retains both that bound and the machine's relative
repeatability.

`calibrate` creates two separate error coordinates:

- local fixture error: clearances, angular amplification, manufacturing
  repeatability, probe repeatability and declared disturbance;
- absolute-frame error: cited process error plus local fixture error.

`qualify_process` consumes no material but requires an assembled fixture and a
source capability bound to it. It creates a child machine-process capability
only when

$$
e_{fixture}+e_{transfer}<e_{parent\ process}.
$$

This is a fail-closed transition. A decorative fixture, an unrelated
capability, a non-improving transfer, a mismatched machine or a reused child
capability ID is rejected.

`execute_from_state` validates the world-spec hash, inventory domain and bounds,
canonical state shape and monotone sequence before copying and continuing the
state. The second program's parent hash must be the exact first child hash.
An arbitrary state file is not thereby proved reachable; the trusted benchmark
evaluator closes that gap by reproducing the first generation in memory.

## Formal result

Let $p_0$ and $p_1$ be parent and qualified process bounds, and
$\ell_0,\ell_1$ parent and successor local artifact bounds. Under

$$
p_1<p_0 \quad\text{and}\quad \ell_1\le\ell_0,
$$

natural-number addition gives

$$
p_1+\ell_1<p_0+\ell_0.
$$

Lean proves this as
`valid_physical_contribution_strictly_improves_successor_bound`. The theorem is
conditional: calibration must justify all four empirical bounds, and a
successor whose local error worsens too far does not receive a certificate.

## Benchmark task

`conformance.recursive_fixture_process` independently reloads both stored MRS
construction programs, executes the first from the initial world and the
second from the reproduced child state, and verifies every program, world,
artifact and receipt hash. Hidden span/disturbance interventions conservatively
perturb both fixture error and qualification transfer.

The reference run has two promotions, 480 generated/executed candidates,
0.72155 kg modeled material use, about 4.002 MJ modeled energy use and 100%
hidden-case robustness. Its evidence tier remains `CONFORMANCE`.
