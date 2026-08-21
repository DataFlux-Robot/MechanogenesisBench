# Mechanogenesis Engine — Product-First Specification

## Intended product

Mechanogenesis Engine is not a Newton fork and not a collection of simulator
adapters. It is a canonical executable world for agents that invent, assemble,
instrument, test and recursively improve mechanisms. It must eventually cover
the useful path from material and component inventories to manufacturable
assemblies, controllers, experiments and successor manufacturing capability.

“Large and comprehensive” is an end-state requirement. Implementation is
staged by semantic closure: every stage extends the same IR and evidence model
rather than creating a disposable intermediate product.

## Canonical kernel

The small trusted kernel should contain only semantics that all later domains
must share:

1. `Quantity`: dimensions, units, intervals/distributions and calibration.
2. `Frame/Topology`: coordinate frames, ports, incidence and assembly identity.
3. `WorldState`: geometry, fields, inventories, equipment state and provenance.
4. `Capability`: preconditions, controlled variables, resolution, envelope,
   consumables, failure modes and postconditions.
5. `Intervention`: an executable change with declared observables and custody.
6. `ConstructionProgram`: typed operations that transform world state.
7. `ExperimentProgram`: interventions, controls, measurements and stopping rules.
8. `Receipt`: content-bound inputs, outputs, uncertainty, resources and lineage.
9. `RefinementContract`: maps a canonical fragment to a numerical backend with
   assumptions and error obligations.

LLMs may generate task languages, theories, compilers and programs, but may not
silently redefine these invariants. Proposed kernel extensions require a schema
migration, conformance corpus and machine-checked preservation obligations.

## Multi-scale physics

Mechanism invention crosses scales and domains: rigid/multibody motion,
contact/friction, compliant bodies, fracture, thermal flow, fluids,
electromagnetics, electronics, control, sensing, machining/additive processes,
wear and metrology. The engine represents this as a typed coupling graph rather
than one monolithic solver.

Each region has a domain, spatial/temporal scale, state variables, conserved
fluxes, uncertainty and fidelity level. Couplings exchange canonical port
quantities. A scheduler refines only regions whose uncertainty can change the
promotion decision. Cross-domain conservation residuals and refinement error
are evidence, not hidden logs.

Initial native reference semantics should be intentionally slow and auditable.
Optimized/GPU solvers are refinements. Independent solvers can falsify a result
through disagreement tests; consensus alone does not establish physical truth.

## MRS and Gθ interfaces

For task $\tau$, the generator emits:

$$
(\mathcal L_\tau,\ Sem_\tau,\ C_\tau,\ Cert_\tau,\ H_\tau,
P^c_\tau,\ P^e_\tau,\ V_\tau,\ \Delta G_\theta).
$$

These are respectively the task-specific language, semantics, compiler,
compiler certificate, theory portfolio, construction program, experiment
program, evaluator contract and generator-update proposal. All nine are stored
as real content-addressed objects. PID, MPC, neural policies, LLM agents and new
representations are possible research conclusions, not predeclared plug-ins.

The research runtime should combine:

- an LLM proposal/theory/program generator;
- multi-world hypothesis populations and calibrated world models;
- causal intervention selection and Separability Ladder estimation;
- RL or search over executable research trajectories;
- SFT on verified useful actions and preference learning on same-parent forks;
- test-time learning within a sealed episode, with update receipts;
- isolated generator forks to estimate Recursive Research Credit.

The executable 0.4 fragment instantiates this boundary with
`FixtureResearchStrategy`: Gθ generates task-local symbols, ordered parameter
support, weighted world hypotheses, objective/stopping rules and an experiment
policy. A trusted compiler rejects unsupported semantics and lowers candidates
to canonical IR; task evaluators independently replay that lowering. This is a
bounded first fragment, not yet arbitrary topology, compiler or strategy-form
invention. See `GTHETA_MRS_RUNTIME.md`.

## First real task family

The minimum non-toy recursive episode is:

1. inspect a manufacturing cell and its uncertainty;
2. invent and manufacture a calibration, fixturing or measurement tool;
3. validate it under hidden disturbances;
4. promote the improved manufacturing process;
5. use that process to manufacture a more capable successor tool;
6. show through isolated Gθ forks that the research update improves future task
   efficiency, not merely the current artifact reward.

The first hardware scope should use a bounded stock/material set and existing
machine tools. It does not claim autonomous semiconductor-fab replication.

## Product/benchmark modes

The same executable engine exposes two modes:

- product mode: interactive design, simulation, planning, hardware execution,
  diagnosis and evidence management;
- benchmark mode: sealed tasks, withdrawn guidance, resource metering, private
  evaluation, signed traces and reproducible scorecards.

The benchmark task ABI must therefore remain a subset of the product API. No
benchmark-only world representation is permitted.

## Acceptance gates for an engine milestone

A new domain or backend is not “supported” until it has:

- a canonical semantic fragment and typed state transition;
- conservation/invariant tests and adversarial counterexamples;
- a reference interpreter or oracle-sized exact cases;
- a refinement contract and quantified valid regime;
- cross-validation or hardware calibration where claimed;
- task packages that can falsify incorrect implementations;
- evidence-tier wording that matches what was actually measured.
