# Baseline evidence bundle — glm-5.3-flash (2026-09-30)

Machine: single workstation, Linux. Transport: Anthropic-compatible channel via
`tools/openai_anthropic_shim.py` (OpenAI ABI preserved). Sampling policy: see
docs/LEADERBOARD.md §Reproduction. Every run directory contains run.json,
verification.json, score.json, evaluation.json as produced by `mbench run/verify/score`;
model calls are archived credential-free (request/response content hashes) inside the
full run trees retained by the runner maintainers; replay identifiers are in run.json.

| Run | Task | Outcome |
|---|---|---|
| reference-successor | conformance.successor_operator_chain | PASS (promotions 2, robustness 1.0) |
| glm53-flash-successor-002 | conformance.successor_operator_chain | PASS |
| glm53-flash-successor-003 | conformance.successor_operator_chain | PASS |
| glm53-flash-successor-stateless-001 | conformance.successor_operator_chain | FAIL (schema, non-recommended sampling) |
| glm53-flash-demand-stateless-001 | simulation.demand_driven_microfactory | PASS (stateless) |
| glm53-flash-demand-history-004 | simulation.demand_driven_microfactory | PASS (history) |
| glm53-flash-demand-history-003 | simulation.demand_driven_microfactory | FAIL (capital budget overspend) |
| glm53-flash-demand-history-001/002 | simulation.demand_driven_microfactory | FAIL (transport; see failure log) |
