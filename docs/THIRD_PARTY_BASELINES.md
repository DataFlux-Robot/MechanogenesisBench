# Third-party model baselines

**English** | [简体中文](THIRD_PARTY_BASELINES.zh-CN.md)

## What is evaluated

The first non-canned baseline task is
`tasks/conformance/generated_metrology_fixture`. A model receives the public
mission, world, intervention domains and budget, then emits one typed physical
research strategy. Benchmark-owned code performs bounded search, compiles the
selected construction program, executes the canonical reference semantics,
emits a Lean-checkable certificate and invokes the trusted evaluator.

This separation is deliberate: a model cannot earn a score by asserting that a
fixture works or by inventing an experiment receipt. It controls the strategy;
the benchmark controls execution and evaluation.

That task is a one-generation `CONFORMANCE` result. It tests third-party model
integration and strategy reachability, not hardware performance, parameter
inheritance or PRSI.

The next calibration task is
`tasks/conformance/successor_operator_chain`. It executes two generations in
one canonical world state. Generation 1 must machine its product with the exact
operator made in generation 0. The evaluator checks capability-byte identity,
world lineage, held-out error cases and a procured-baseline counterfactual. Its
demand briefs are frozen synthetic stimuli, so this remains conformance rather
than evidence of real human satisfaction or parameter inheritance.

The first coupled demand-and-production task is
`tasks/simulation/demand_driven_microfactory`. The model emits every scored
choice rather than a search strategy. Across two generations it must infer a
demand distribution, forecast reject/adopt/delight, specify a complete
low-speed mobility product and invest in mechanical assembly, PCB test and
battery calibration operators. New demand evidence arrives in generation 1,
which must consume the exact generation-0 operator bytes. Hidden cases score
calibration, physical robustness, product utility, demand-update gain and the
causal advantage of inherited production capacity.

| Failure stage | Observable limitation |
|---|---|
| Action formation | malformed or incomplete product/factory action |
| Demand sensing | belief disagrees with held-out demand truth |
| Demand closure | generation-1 belief does not improve after new evidence |
| Product realization | literal design fails safety, quality or utility cases |
| Machine making | capital plan fails to improve all three production operators |
| Physical inheritance | successor does not bind/use the exact prior operator |
| Demand expansion | synthetic delight is measurable, but human-endorsed surprise requires an authorized human outcome |

The deterministic reference reaches all simulation gates. It proves task
reachability, not language-model reachability. Model baselines are scored only
from their retained literal actions.

## OpenAI-compatible adapter

Install the repository and build the two Lean checkers used by this task:

```bash
python -m pip install -e '.[dev]'
lake build sovereignCheck promotionCheck demandMicrofactoryCheck
```

Set the credential only in the process environment. For GLM-5.3-Flash on the
BigModel endpoint:

```bash
export ZHIPU_API_KEY='...'
export MBENCH_API_ENDPOINT='https://open.bigmodel.cn/api/paas/v4'
export MBENCH_MODEL='glm-5.3-flash'
export MBENCH_THINKING='enabled'
export MBENCH_REASONING_EFFORT='max'
export MBENCH_TEMPERATURE='1'
export MBENCH_TOP_P='0.95'
export MBENCH_MAX_TOKENS='8192'

mbench run tasks/conformance/generated_metrology_fixture \
  --system-command 'python examples/openai_compatible_fixture_system.py' \
  --guidance G5 \
  --output runs/glm53-fixture-g5-001
```

Run the two-generation history-enabled arm:

```bash
export MBENCH_HISTORY_MODE='public_evidence'
mbench run tasks/conformance/successor_operator_chain \
  --system-command 'python examples/openai_compatible_successor_operator_system.py' \
  --guidance G5 \
  --output runs/glm53-successor-history-001
```

Run the coupled demand-microfactory arm:

```bash
export MBENCH_HISTORY_MODE='public_evidence'
mbench run tasks/simulation/demand_driven_microfactory \
  --system-command 'python examples/openai_compatible_demand_microfactory_system.py' \
  --guidance G5 \
  --output runs/glm53-demand-microfactory-history-001
```

Repeat with `MBENCH_HISTORY_MODE=none` for the matched stateless arm. The model
still receives the exact physical operator available in generation 1, while
prior demand and product evidence are withheld. This separates use of
cross-generation evidence from physical operator inheritance.

The same adapter can evaluate another OpenAI-compatible model by changing the
endpoint, model and `MBENCH_API_KEY_ENV`. A participant may instead implement
the process ABI directly; no repository-local model code is required.

## Reproducibility bundle

Every successful adapter run retains:

- the complete credential-free request payload;
- the complete credential-free response envelope and exact response content
  presented to the strict parser;
- requested and returned model identities, provider request ID and finish
  reason;
- prompt, completion and total token counts when supplied by the provider;
- provider latency and every bounded retry or transport failure;
- strategy, compiled program, construction receipts and content-addressed MRS;
- trusted evaluation, verification and vector score.

For the microfactory task, the retained action is the full demand belief,
outcome forecast, product specification and three-operator capital plan for
each generation. Accepted runs additionally retain and execute
`demand_microfactory_certificate.json` through Lean.

The model action is nested in the content-addressed `update_proposal` MRS
object, so replacing either its request or response changes the submission
identity. API credentials are never written to an artifact.

An archived provider call can be replayed without another API request:

```bash
export MBENCH_MODEL='glm-5.3-flash'
export MBENCH_REPLAY_MODEL_CALL='/path/to/archived/call.json'

mbench run tasks/conformance/generated_metrology_fixture \
  --system-command 'python examples/openai_compatible_fixture_system.py' \
  --guidance G5 \
  --output runs/glm53-fixture-replay-001
```

The two-generation adapter instead accepts
`MBENCH_REPLAY_MODEL_CALL_G0` and `MBENCH_REPLAY_MODEL_CALL_G1`, preventing one
archived action from being silently reused for both generations.

Legacy calls that retain only a request hash are labelled
`legacy_hash_only`; they can reproduce strategy execution and scoring but do
not satisfy the stronger complete-request provenance requirement.

## Comparison rules

Scores are comparable only when task digest, guidance, prompt policy, model
controls, network/retry policy and evaluator digest match. A provider model
upgrade creates a new baseline identity even when the marketing model name is
unchanged. Offline replay must charge the original provider latency rather than
the shorter replay time.

Provider-side energy and an unreported API price remain unobserved. Such a run
may report capability and robustness, but it must not be used for energy- or
cost-efficiency claims. A live baseline also requires multiple independent
calls or provider-supported seeds before uncertainty is reported.

## Human-demand extension

Population user simulation belongs in an optional demand-formation track, not
inside the physical core score. A MatrAIx adapter can sample heterogeneous
personas, challenge candidate demand briefs and record subgroup responses. Its
outputs remain `synthetic_response` evidence and cannot promote physical truth,
purchase, adoption or welfare claims. Real demand calibration requires a
forecast frozen before an authorized evaluator-owned outcome.

This modular position supports human-demand-guided machine development without
making one persona model a mandatory dependency or allowing simulated demand
to compensate for a failed construction or experiment.

The next registered human track separates pre-use demand elicitation, post-use
demand correction and delayed endorsement of a genuinely new affordance. A
persona model may generate stress cases and population hypotheses; only
authorized human observations can close calibration or positive-surprise
claims. This makes demand perception, closure and guidance measurable without
turning simulated approval into ground truth.

## Anthropic-protocol-only keys (transport shim)

Providers whose keys have Anthropic-channel quota only (e.g. some Z.ai `glm-*` keys) can still run
the unmodified OpenAI-compatible adapter through the local transport shim
`tools/openai_anthropic_shim.py`: point `MBENCH_API_ENDPOINT` at the shim, which forwards to the
Anthropic `/v1/messages` endpoint, echoes the requested model id, and unwraps at most one complete
markdown fence (mirroring native `response_format=json_object`). Scoring, receipts and replay are
unchanged. See `docs/LEADERBOARD.md` §Reproduction for the full command.
