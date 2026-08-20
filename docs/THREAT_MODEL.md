# Threat Model

## Fail-closed today

- malformed schemas and missing MRS objects;
- artifact, task and private-evaluator bundle substitution;
- broken process/world lineage;
- material non-closure;
- evaluator decisions above the evidence ceiling;
- false accepted flags, insufficient robustness or non-positive net value;
- negative/absent recursive credit on accepted Recursive Learner generations;
- declared resource-budget overflow.

## Not contained today

The development runner executes an arbitrary process on the host. It does not
prevent filesystem inspection, network access, evaluator probing, resource
under-reporting, clock manipulation or collusion. Therefore its maximum evidence
tier is conformance.

Before an external leaderboard or hardware claim, add an OCI/microVM runner,
read-only public mounts, physically separate private evaluation, network deny by
default, cgroup/GPU/energy metering, signed clock and instrument receipts,
reproducible images and append-only trace storage.

Formal proofs establish protocol implications under explicit assumptions. They
do not turn a compromised evaluator, wrong world model or unobserved disturbance
into valid physical evidence.
