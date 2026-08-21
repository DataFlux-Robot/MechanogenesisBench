# Architecture

## Product boundary

Mechanogenesis Engine is intended to become a broad physical invention,
simulation, construction and experiment product. MechanogenesisBench is the
native protocol by which that product—and competing systems—can be evaluated.
They share one canonical semantics; the benchmark is not a smaller toy physics
engine beside the product.

The central loop is:

```text
Gθ generator checkpoint
  -> Meta Research Strategy (MRS)
  -> task-specific mechanism language, theory and compiler
  -> construction + experiment programs
  -> canonical world transition + physical/refinement execution
  -> independent evidence and promotion decision
  -> isolated parent/child generator forks on future tasks
  -> causally credited Gθ update
```

The first commercial/recursive task family is a manufacturing unit that
autonomously designs a tooling or metrology artifact which improves the next
manufacturing generation.

## One semantic spine

The target Lean Sovereign Kernel owns these canonical meanings:

- typed dimensions, coordinate frames, uncertainty and provenance;
- geometry/topology, materials, fields, bodies, joints and interfaces;
- manufacturing capabilities, inventories, operations and world transitions;
- sensor interventions, experiments and custody-bound evidence receipts;
- process and world lineages, which are distinct and content-addressed;
- promotion, rollback and generator-fork semantics.

Version 0.6 makes the first subset executable: fixed-point quantities, frame
and world identity, assumption/evidence ledgers, refinement contracts,
Lean-owned lowered shape/assembly/manufacturing IR, receipt-chain/material/
resource accounting, a bounded metrology refinement and world-bound promotion.
General geometry evaluation, fields, contact, manufacturing physics, sensor
custody, rollback and fork semantics remain target modules rather than
implemented claims.

Python, GPU solvers and hardware drivers execute refinements of this spine; they
do not define parallel physical truth. Every promotable backend output must
carry a transition certificate accepted by `sovereignCheck`; its evaluator
decision must then be bound to the same parent/child worlds and accepted by
`promotionCheck`. See `LEAN_SOVEREIGN_KERNEL.md`.

A solver is accepted only through a refinement contract: it declares the
canonical fragment it implements, approximation assumptions, error/control
regime and conserved quantities. Newton, MuJoCo, FEM packages, collision
libraries and GPU kernels can then serve as numerical backends or independent
falsifiers. They never become the owner of canonical state through an ad-hoc
adapter.

## Control and trust planes

The untrusted system sees only the public task package and selected guidance.
It emits a content-addressed MRS bundle, candidate artifact, construction
receipts, experiment receipts and resource declaration. A trusted evaluator
uses private cases and produces confidence bounds, robustness, net value,
evidence tier and Recursive Research Credit. The verifier independently binds:

- task package, private evaluator bundle and artifact hashes;
- parent/child process lineage and parent/child world lineage;
- exact integer material closure per operation;
- evidence tier to the task ceiling;
- resource use to the budget;
- accepted status to all promotion gates.

The current runner provides only process isolation and is deliberately capped
at `CONFORMANCE`. Competition and hardware claims require container/VM
isolation, read-only task mounts, network policy, signed measurement custody and
reproducible evaluator images.

## Tracks

- `fixed_engine`: generate artifacts/programs while engine and research policy
  remain fixed.
- `open_system`: the submission may generate a task language/compiler and use
  declared external tools.
- `recursive_learner`: it must additionally demonstrate that a generator update
  improves held-out future research under isolated forks.

Guidance levels withdraw scaffolding from G1 (decomposition and protocol hints)
through G5 (mission and access only). Results are comparable only within the
same task, track, guidance, evidence tier and budget vector.

## Why the score is a vector

A single number allows speed to conceal material waste, capability to conceal
human labour, or simulation confidence to masquerade as hardware evidence.
MechanogenesisBench therefore reports capability gain, robustness, autonomy,
productive time, productive budget, recursive credit and evidence tier as
separate coordinates. Pareto analysis belongs above this kernel.
