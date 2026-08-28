# Scope and claim boundary

## Public object

MechanogenesisBench evaluates a third-party system through versioned task
packages, a public input view, content-addressed submissions, evaluator-owned
hidden information and fail-closed scoring. It does not prescribe the model,
planner, optimizer or training method used by a participant.

The intended long-term object is an agent that can turn a physical goal into a
mechanism-research specification (MRS), a construction program, an experiment
and auditable evidence. A bounded recursive track additionally asks whether a
physical result from one generation improves a later generation under matched
resources and exact lineage.

## Repository exclusion boundary

The public repository excludes:

- FLUXPRSI model and researcher implementations;
- candidate-update generation and full-parameter training code;
- private training curricula, buffers and optimizer policies;
- model checkpoints, internal prompts and experiment artifacts;
- internal proof-development plans and operational handoffs;
- product runtime and customer data.

The words PRSI and recursive appear in the benchmark because they name a
property that the benchmark is intended to measure. They do not imply that the
repository contains the FLUXPRSI system or that the property has been achieved.

## Evidence discipline

Every positive result must state its evidence tier. A conformance episode
shows that the protocol can be executed and rejected correctly. A simulation
result remains model-qualified. Hardware claims require metrology, calibration,
custody and physical execution receipts. No finite `PRSI-n` result implies
unbounded improvement or acceleration.

Lean proves implications inside an explicit formal model. Runtime certificates
bind concrete bytes to those predicates. Neither substitutes for empirical
evidence that model assumptions hold, nor for a reachability result showing
that a trained policy can actually produce an accepted successor.
