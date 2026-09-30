# MechanogenesisBench Leaderboard

Updated: 2026-09-30 · Evidence: [`docs/baselines/2026-09-30-baselines/`](baselines/2026-09-30-baselines/) ·
Reproduce: see [§Reproduction](#reproduction) · Submit: see [§Submitting a system](#submitting-a-system)

## How to read this table

**Ranking = Pareto layers over a 10-component vector; no weights anywhere** (v3). The only
aggregation is the arithmetic mean of the SAME component across a model's runs. Ordering
between adjacent layers rests on verified componentwise dominance (>= on all ten, > on at
least one); models in the same layer are reported as incomparable, not equal. Components:
chain promotion / robustness / inheritance attainment; demand promotion / robustness /
calibration accuracy / update-gain attainment / lineage exactness; and two failure-gradient
components (budget compliance via the task package's own `capital_cost_milliusd()`,
schema validity), where passing runs count 1.0 and model-decision failures contribute
graded values from archived artifacts. Recompute: `python tools/pareto_score.py --models
name=run1,run2,...`. This is directly usable as a multi-objective selection signal
(MAP-Elites / quality-diversity style) and each component is a separate dense reward
channel for RL. The earlier weighted composite (`tools/composite_score.py`) is retained
as a legacy convenience only and plays no role in ranking.

Current layers (verified dominance chain; no incomparability emerged yet because no model
shows a cross-component trade-off):

| Layer | Model | demand pass | calibration | budget | schema | dominates |
|---|---|---|---|---|---|---|
| 1 | glm-5.3-flash | 0.667 | 0.860 | 0.667 | 1.000 | 5 |
| 2 | mimo-v2.6-flash | 0.500 | 0.845 | 0.500 | 1.000 | 4 |
| 3 | glm-5.2 | 0.333 | 0.571 | 0.333 | 0.667 | 3 |
| 4 | mimo-v2.6-pro | 0.000 | 0.549 | 0.000 | 0.667 | 2 |
| 5 | glm-5.3 | 0.000 | 0.280 | 0.000 | 0.333 | 1 |
| 6 | glm-5.1 | 0.000 | 0.262 | 0.000 | 0.333 | 0 |

## Statistical power (2026-10-01 scale-up)

At n=3 the Wilson 95% CI for a 2/3 pass rate is [0.21, 0.94] — overlapping almost every
other model, so small-n rows carry almost no discrimination. Scaled stateless demand-factory
replicates (`tools/batch_runs.py`, parallel workers, fresh run roots):

| Model | Mode | n | Pass | Rate | Wilson 95% CI |
|---|---|---|---|---|---|
| glm-5.3-flash | stateless | 25 | 6 | 24% | [0.12, 0.43] |
| mimo-v2.6-flash | stateless | 25 | 0 | 0% | [0.00, 0.13] |
| glm-5.3-flash | history | 25 | 11 | **44%** | [0.27, 0.63] |
| mimo-v2.6-flash | history | 25 | 3 | **12%** | [0.04, 0.30] |

Fisher exact: stateless 6/25 vs 0/25 p ≈ 0.022; history 11/25 vs 3/25 p ≈ 0.016; pooled
50-run 17/50 (34%) vs 3/50 (6%) p < 0.001. History mode (generation 1 sees generation-0
public evidence) lifts BOTH models (+20pp / +12pp) — prior evidence genuinely helps the
second generation, and mimo-v2.6-flash is NOT a zero scorer at scale: 12% in history mode. **Validity audit (2026-10-01) — the 0% headline
must be read with its miss distances, or it misrepresents the model:**

- **Task solvability**: the deterministic reference system passes both generations
  (eligible, promotions 2) — the configuration is solvable without any LLM.
- **Where mimo-v2.6-flash actually fails**: in all 13 evaluated runs, generation 1 is
  fully accepted (robustness 100%, update gain 528k–772k vs 400k gate, exact lineage,
  inheritance advantage 123k–139k vs 50k gate). The failing gate is generation-0
  **minimum product utility**, missed by **1.37%–3.92% (median 1.37%)** against the
  700k threshold — glm-5.3-flash's distribution straddles the same line (5/19 misses,
  0.69%–5.29%). The models converge on near-identical product specs (identical utility
  values appear in both); mimo systematically lands just under the line.
- **Decoding robustness**: rerun at temperature 0.6 gives the same result (0/10, same
  1.37% median miss) — the outcome is not an artifact of the GLM-recommended
  temperature-1.0 policy. Future submissions should still declare vendor-recommended
  decoding; the earlier `reasoning_effort` incompatibility (GLM-specific field) is
  already handled.
- **Correct reading**: mimo-v2.6-flash does not "fail the task" — it clears every
  second-generation gate with large margins and misses ONE generation-0 product-spec
  utility line by ~1.4% at the median. That is a real, thin, actionable difference
  against glm-5.3-flash (whose g0 passes 14/19) — precisely the granularity the graded
  components carry; the binary headline alone would overstate it.

Scaling roadmap (declared): ~33 runs/arm separates 0.67-vs-0.33 class differences at
α=0.05/power=0.8; ±0.10 CI needs ~100; ±0.03 needs ~1100; AA-grade ±0.01 needs ~10k
(~6-8 workers, ~30-60 h wall for 1k; flash-tier token cost is negligible). The
complementary research track is a **continuous multi-round demand stream** (evergreen,
versioned briefs; rolling satisfaction and drift-adaptation metrics) which measures
sustained need-serving rather than same-task sampling variance.

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
