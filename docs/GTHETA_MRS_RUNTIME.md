# Gθ / MRS Research Runtime 0.1

## Purpose

Gθ is the learnable generator whose output is a Meta Research Strategy (MRS),
not a final mechanism and not arbitrary executable source code. For a mission
$\tau$, the intended full output remains

$$
G_\theta(\tau,W,B,E)
\rightarrow
(\mathcal L_\tau,Sem_\tau,C_\tau,Cert_\tau,H_\tau,
P^c_\tau,P^e_\tau,V_\tau,\Delta G_\theta).
$$

Version 0.5 executes the first closed fragment of this interface. A reference
or OpenAI-compatible LLM proposer generates a fixture research strategy. A
small trusted compiler validates that strategy, compiles its supported
candidates to canonical Mechanism IR, executes them against the current world,
tests them against multiple world hypotheses and emits the nine content-bound
MRS objects.

This is not yet general MRS invention. It is the first executable proof that
the strategy itself can control candidate reachability, experiment ordering
and multi-world rejection without being allowed to redefine physical truth.

## Executable chain

```text
mission + world access + budget + prior evidence
                    |
                    v
       Gθ strategy proposer (LLM or replayable reference)
                    |
                    v
       strict FixtureResearchStrategy JSON
       - generated task language and symbols
       - ordered candidate support
       - multi-world hypothesis portfolio
       - search/stopping rule
       - experiment policy
                    |
                    v
       trusted bounded strategy compiler
       - reject unknown fields and code
       - enforce public intervention domains
       - enforce execution budget
       - compile each candidate to canonical IR
                    |
                    v
       reference interpreter + robust model sweep
                    |
                    v
       construction program + receipts + Lean-checkable MRS certificate
                    |
                    v
       independent evaluator reconstructs strategy and reruns mapping
                    |
                    v
       world-bound decision accepted by Lean promotionCheck
```

The LLM boundary is data-only. Responses must be one bare JSON object with
exact fields, bounded strings, bounded arrays, integer fixed-point units and no
unknown topology or operator. Markdown fences, source code fields, unavailable
interventions and excess budgets fail closed.

## Current strategy language

`FixtureResearchStrategy` contains:

- `language`: a task-local symbol system whose three symbols bind to locator
  spacing, bore clearance and reference offset;
- `world_hypotheses`: weighted span/disturbance models evaluated for every
  executable candidate;
- `search`: candidate ordering, base-material ordering, objective order,
  stopping rule and hard execution limit;
- `experiment`: the minimum hypothesis coverage and robust-model sweep rule;
- `research_hypothesis`: the generated causal rationale to preserve in the
  research trace.

The present trusted compiler admits one topology:
`two_locator_one_reference`. The generated language is therefore real but
bounded: it changes symbols, support, order, model portfolio and experiment
logic, while topology semantics remain fixed. Calling this unrestricted
language invention would be false.

## Reference Gθ algorithm

The deterministic proposer is a conformance oracle and training-data seed. It
constructs a three-world portfolio from public evidence and orders candidate
support using a physics prior:

1. maximize locator baseline to reduce angular amplification;
2. minimize locator/reference clearance;
3. use the smallest manufacturable base;
4. evaluate the nominal world plus two span/disturbance extrapolations;
5. stop at the first candidate certified under every generated model.

On the current fixture task, this strategy exposes 240 possible constructions
but reaches a robustly feasible candidate in one physical execution. Its model
errors are 130, 145 and 160 μm under a 200 μm gate. An ablated strategy whose
budgeted support contains only short-baseline, large-clearance candidates
fails. This is a reachability ablation, not evidence that the reference prior
is universally optimal.

Run `python experiments/gtheta_phase_boundary.py` to reproduce both the support
ablation and a model-separation ablation: a marginal 200 μm candidate passes
the nominal world, while adding the generated span/disturbance worlds rejects
it.

## Lean-guided design constraints

`formal/lean/GTheta.lean` establishes three conditional results.

First, for finite strategy support $S_\theta$ and feasibility set $F$,

$$
\exists\text{ supported feasible output}
\iff
S_\theta\cap F\ne\varnothing.
$$

For an ordered budget $B$, replace $S_\theta$ with its first $B$ candidates.
This makes support recall an algorithm-level threshold: selector intelligence
cannot repair a generated support prefix with zero feasible mass.

Second, robust feasibility across world models is conjunctive. Adding a
grounded model cannot expand the robust feasible set, and a model on which a
candidate fails strictly removes that candidate. Thus world-model growth must
be evaluated both for useful separation and for overconservative false
rejection.

Third, accepted compilation transfers feasibility only under an explicit
compiler-soundness obligation. The design consequence is that Gθ may generate
languages and searches, but every language fragment needs a trusted lowering
rule and executable certificate before it can affect a promoted world.

The generated compiler-certificate MRS object is now a Sovereign Kernel
certificate rather than a descriptive label. It binds strategy support,
construction program, world lineage, exact material/resource receipts and an
explicit assumption ledger. The private evaluator additionally binds its
promotion decision to the certificate's exact parent/child world pair; Lean
rejects mismatched credit or insufficient improvement.

These theorems do not prove that an LLM finds a good support set, that generated
world models contain reality or that physical error bounds are calibrated.

## Learned Gθ roadmap

The same strategy schema supports a learnable generator without changing the
trusted kernel:

- SFT: train on accepted strategy-generation traces, including hypotheses,
  rejected supports and compiler diagnostics rather than final artifacts only;
- preference learning: compare same-parent strategy forks by future feasible
  support, discrimination power, execution cost and net value;
- RL: reward independently accepted physical contribution and prospective
  Recursive Research Credit, with explicit token, experiment, material and
  time penalties;
- test-time training: update an episode-local proposer from failed compilation,
  model disagreement and experiment receipts, while retaining the parent
  checkpoint for causal comparison;
- world-model learning: propose new separating hypotheses, then require an
  executable intervention or calibrated refinement receipt before those models
  can gate promotion.

The training target is not current artifact reward alone. A strategy update is
recursively valuable only if isolated future-task forks show better supported
reachability, causal attribution, reliable discrimination and positive net
value.

## Running it

Reference proposer:

```bash
mengine research-fixture \
  tasks/conformance/generated_metrology_fixture/public/mechanism_world.json \
  tasks/conformance/generated_metrology_fixture/public/fixture_goal.json \
  --mission tasks/conformance/generated_metrology_fixture/guidance/G5.md \
  --evaluator-contract tasks/conformance/generated_metrology_fixture/public/evaluator_contract.json \
  --strategy-output /tmp/strategy.json \
  --mrs-output /tmp/mrs.json \
  --program-output /tmp/program.json
```

OpenAI-compatible proposer:

```bash
OPENAI_API_KEY=... mengine research-fixture ... \
  --proposer openai-compatible \
  --llm-endpoint https://provider.example/v1 \
  --llm-model model-name
```

The network proposer is optional and is not called in deterministic tests.

## Next semantic expansion

The next compiler fragment should let Gθ choose among genuinely different
fixture/tool topologies and generate experiment bytecode, while retaining:

- canonical quantities, frames, topology identity and world lineage;
- explicit public action/access sets;
- bounded compiler verification and resource accounting;
- independent strategy-to-program replay;
- counterexample-preserving model portfolios;
- hardware or calibrated solver evidence before claims exceed conformance.
