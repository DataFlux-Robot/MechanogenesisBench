# MechanogenesisBench Leaderboard

Updated: 2026-09-30 · Evidence: [`docs/baselines/2026-09-30-baselines/`](baselines/2026-09-30-baselines/) ·
Reproduce: see [§Reproduction](#reproduction) · Submit: see [§Submitting a system](#submitting-a-system)

## How to read this table

**Composite score** = mean of task scores; task score = mean of run scores x 100; run score =
arithmetic mean of that task's preregistered component scores, each a NATIVE evaluator-defined
rate or threshold-attainment in [0,1] (no free weights, no model-dependent anchors):

- `conformance.successor_operator_chain`: promotion_rate = promotions/2; robustness_rate;
  inheritance_attainment = min(capability_gain / 500um, 1).
- `simulation.demand_driven_microfactory`: promotion_rate; robustness_rate;
  calibration_accuracy = 1 - L1_error/1e6; update_gain_attainment = min(gain/400000ppm, 1);
  lineage_exactness in {0,1}.

Model-decision failures score 0 and remain in the denominator. Excluded runs must carry a
failure-log justification (this round: one policy-deviation run under non-declared sampling;
two transport-side failures with no completed model call). Recompute:
`python tools/composite_score.py --runs runs/<...> --exclude <...>`.

Current composites: glm-5.3-flash = **82.4**; mimo-v2.6-flash = **74.2** (chain 100.0;
demand 48.3 over 2 scored runs — one pass at 96.7, one budget failure at 0, one timeout
excluded); glm-5.2 = **66.2**; glm-5.3 = glm-5.1 = mimo-v2.6-pro = **50.0** (chain 100.0
each; demand 0.0 over 3 scored runs, all model-decision failures — budget or field-range);
reference = 100.0 (single task). All model-decision failure runs score 0 and stay in the
denominators. Cross-vendor pattern at n=3 attempts per model: every flagship/base model
failed all demand-factory attempts on budget/field discipline while two of three
flash-tier models passed at least once — flagships solve the chain but overspend. Methodology follows the Artificial Analysis Intelligence Index practice of aggregating
graded 0-100 component scores from independently executed runs.

MechanogenesisBench reports a **vector scorecard, not one weighted number**. A run **passes** only
when every preregistered promotion gate holds *and* the Lean certificate for the executed chain is
accepted by the pinned checker. Pass rate is `passed runs / attempted runs` under the declared
budget and sampling policy; failed runs are listed in the [failure log](#failure-log) rather than
dropped. Cost columns are per-run model-side accounting from archived provider receipts.

## conformance.successor_operator_chain (two-generation operator chain)

Requires: strict operator improvement in both generations, exact content-hash operator inheritance
(generation 1 must consume the operator generation 0 produced), robustness ≥ 0.80 on held-out
spans, inheritance advantage ≥ 500 µm vs a counterfactual procured-operator run, byte-exact
re-execution by the trusted evaluator, and an accepted `sovereignCheck` certificate.

| System | Model | Pass | Promotions | Robustness | capability_gain | Lean | Date |
|---|---|---|---|---|---|---|---|
| Reference (deterministic, non-LLM) | — | 1/1 | 2 | 1.00 | 660.0 µm | ✓ | 2026-09-30 |
| OpenAI-compatible adapter | glm-5.3-flash | **2/2** | 2 | 1.00 | 660.0 µm | ✓ | 2026-09-30 |
| OpenAI-compatible adapter | glm-5.2 | **2/2** | 2 | 1.00 | 660.0 µm | ✓ | 2026-09-30 |
| OpenAI-compatible adapter | glm-5.1 | **2/2** | 2 | 1.00 | 660.0 µm | ✓ | 2026-09-30 |
| OpenAI-compatible adapter | mimo-v2.6-pro | **2/2** | 2 | 1.00 | 660.0 µm | ✓ | 2026-09-30 |
| OpenAI-compatible adapter | mimo-v2.6-flash | **2/2** | 2 | 1.00 | 660.0 µm | ✓ | 2026-09-30 |
| OpenAI-compatible adapter | glm-5.3 | **2/2** | 2 | 1.00 | 660.0 µm | ✓ | 2026-09-30 |

## simulation.demand_driven_microfactory (demand belief + two-generation inheritance)

Requires: strict three-channel operator improvement, robustness ≥ 0.80 under hidden disturbances,
demand-calibration error ≤ 250k/300k ppm, minimum product utility, exact lineage, generation-1
demand-update gain ≥ 400k ppm, inheritance advantage ≥ 50k ppm, and an accepted
`demandMicrofactoryCheck` certificate. `history` = generation 1 sees generation-0 public evidence.

| System | Model | Mode | Pass | Calibration err (g0/g1, ppm) | Update gain (ppm) | Exact inheritance | Lean | Date |
|---|---|---|---|---|---|---|---|---|
| OpenAI-compatible adapter | glm-5.3-flash | stateless | 1/1 | 140k / 140k | 640,000 | ✓ | ✓ | 2026-09-30 |
| OpenAI-compatible adapter | glm-5.3-flash | history | 1/2 | 140k / 140k | 680,000 | ✓ | ✓ | 2026-09-30 |
| OpenAI-compatible adapter | glm-5.2 | history | 1/3 | 144k / 240k | 750,000 | ✓ | ✓ | 2026-09-30 |
| OpenAI-compatible adapter | glm-5.1 | all modes | 0/3 | — | — | — | — | 2026-09-30 |
| OpenAI-compatible adapter | mimo-v2.6-flash | mixed | 1/2 | 166k / 217k | 578,354 | ✓ | ✓ | 2026-09-30 |
| OpenAI-compatible adapter | mimo-v2.6-pro | all modes | 0/3 | — | — | — | — | 2026-09-30 |
| OpenAI-compatible adapter | glm-5.3 | all modes | 0/3 | — | — | — | — | 2026-09-30 |

## Failure log (transparent, archived in the evidence bundle)

| Run | Outcome | Registered cause |
|---|---|---|
| glm53-flash-successor-stateless-001 | system_failed | strategy JSON missing the three required parameter domains; run used non-recommended sampling (temp 0.3 / effort low). Superseded by the recommended policy below. |
| glm53-flash-demand-history-001 | system_failed | provider transport: the Anthropic-channel key used here has no `/chat/completions` quota; resolved by the local shim (see Reproduction). |
| glm53-flash-demand-history-002 | system_failed | transport shim was down (connection refused); no model call completed. |
| glm53-flash-demand-history-003 | system_failed | **model decision failure**: generation-0 factory plan exceeded the registered capital budget (fail-closed by design). |
| glm-5-2-demand-stateless-001 | system_failed | model decision failure: capital budget exceeded (scored 0). |
| glm-5-2-demand-history-002 | system_failed | model decision failure: plan field outside registered range (scored 0). |
| glm-5-1-demand-history-001 | system_failed | model decision failure: capital budget exceeded (scored 0). |
| glm-5-1-demand-stateless-001, glm-5-1-demand-history-002 | system_failed | model decision failure: plan fields outside registered range (scored 0). |
| mimo-*-demand-stateless/history-001/history-002 (6 runs) | system_failed | HTTP 400 protocol: provider rejects the GLM-specific `reasoning_effort` field (transport-class, excluded; superseded by the demand2 reruns with the field omitted). |
| mimo-v2-6-pro-demand2-stateless/history-001 | system_failed | model decision failure: capital budget exceeded (scored 0). |
| mimo-v2-6-pro-demand2-history-002 | system_failed | model decision failure: plan field outside registered range (scored 0). |
| mimo-v2-6-flash-demand2-stateless-001 | system_failed | model decision failure: capital budget exceeded (scored 0). |
| mimo-v2-6-flash-demand2-history-002 | system_timeout | wall-budget timeout (environment-class, excluded; no model-quality claim either way). |
| glm-5-3-demand-history-001 | system_failed | model decision failure: capital budget exceeded (scored 0). |
| glm-5-3-demand-stateless-001, glm-5-3-demand-history-002 | system_failed | model decision failure: plan fields outside registered range (scored 0). |

## Reproduction

Declared model-side sampling policy for all glm-5.3-flash rows:
`temperature=1.0, top_p=0.95, thinking=enabled, reasoning_effort=max, max_tokens=8192,
max_attempts=6` (see `docs/THIRD_PARTY_BASELINES.md`). The provider offers no server-side seed;
every request/response is archived (content-hashed, credential-free) and replayable via
`MBENCH_REPLAY_MODEL_CALL_G0/_G1`.

```bash
python -m pip install -e .
lake build sovereignCheck promotionCheck demandMicrofactoryCheck
# Anthropic-protocol-only keys (e.g. Z.ai glm-*) can use the local transport shim:
python tools/openai_anthropic_shim.py 8765 &
export MBENCH_API_ENDPOINT=http://127.0.0.1:8765/v4 MBENCH_MODEL=glm-5.3-flash \
       MBENCH_API_KEY_ENV=SHIM_KEY SHIM_KEY=local-shim \
       MBENCH_THINKING=enabled MBENCH_REASONING_EFFORT=max \
       MBENCH_TEMPERATURE=1 MBENCH_TOP_P=0.95 MBENCH_MAX_TOKENS=8192 MBENCH_MAX_ATTEMPTS=6
mbench run tasks/conformance/successor_operator_chain \
  --system-command "python examples/openai_compatible_successor_operator_system.py" \
  --guidance G5 --output runs/<name>
mbench verify runs/<name> && mbench score runs/<name>
```

The shim is transport-only: it unwraps at most one complete markdown fence (mirroring native
`response_format=json_object`), never repairs partial JSON, and forwards the requested model id
verbatim; scoring lives entirely in the trusted evaluator.

## Submitting a system

1. Run any task through your system command with the env contract above (any OpenAI-compatible
   endpoint; `MBENCH_MODEL` is echoed and verified against the provider-reported model).
2. `mbench verify` + `mbench score` must pass on your machine; include `run.json`,
   `verification.json`, `score.json`, `evaluation.json` per run plus the declared sampling policy.
3. Add a row here with pass rate over ≥3 attempted runs (failed runs included), the failure log
   entry if any, and a pointer to your evidence bundle. No self-reported scores.

## Roadmap: reuse-economics dimensions (RC-Score card)

A proposed task family `mechanogenesis.reuse_economics/v1` extends this leaderboard with
**reuse-economics axes** measured by harness-run paired forks (same model with inherited capital
vs materially-equivalent capital-cleared control): `RCI` (scratch-vs-reuse net-loss ratio),
`engagement rate` (does the model actually import identity-verified inherited assets), `qualify@k`,
`cost-to-qualified`, fixed-judge ratings, and self-preference bias. First mechanism-demo data
(GLM-5.3-flash, n=1 lineage, research track): RCI 7.6/5.1 under two preregistered selection rules,
engagement 8→33% with operator-level enforcement; glm-5.1 comparison: engagement 0. Specification
in progress; see the research notes linked from the evidence bundle manifest.

## Notes and limits

Single machine, provider-side nondeterminism, small n (declare n with every row). The reference
system is a deterministic reachability check, not a model. Scores certify protocol-level
conformance/simulation evidence only — never physical manufacturing, human outcomes, or
recursive-self-improvement claims.
