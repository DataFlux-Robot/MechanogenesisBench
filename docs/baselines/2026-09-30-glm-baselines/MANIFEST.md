# Baseline evidence bundle — GLM public-task baselines (2026-09-30)

Machine: single workstation, Linux. Transport: Anthropic-compatible channel via
`tools/openai_anthropic_shim.py` (OpenAI ABI preserved). Sampling policy: see
docs/LEADERBOARD.md §Reproduction. Each run directory contains run.json,
verification.json, score.json, evaluation.json as produced by `mbench run/verify/score`;
model calls are archived credential-free (content-hashed) in the full run trees.

| Run | Task | Outcome |
|---|---|---|
| reference-successor | successor_operator_chain | PASS |
| glm53-flash-successor-002/003 | successor_operator_chain | PASS ×2 |
| glm53-flash-successor-stateless-001 | successor_operator_chain | FAIL (schema; policy deviation, excluded) |
| glm53-flash-demand-stateless-001, history-004 | demand_driven_microfactory | PASS ×2 |
| glm53-flash-demand-history-003 | demand_driven_microfactory | FAIL (capital budget) |
| glm53-flash-demand-history-001/002 | demand_driven_microfactory | FAIL (transport; excluded) |
| glm-5-2-successor-001/002 | successor_operator_chain | PASS ×2 |
| glm-5-2-demand-history-001 | demand_driven_microfactory | PASS |
| glm-5-2-demand-stateless-001 | demand_driven_microfactory | FAIL (capital budget) |
| glm-5-2-demand-history-002 | demand_driven_microfactory | FAIL (field out of range) |
| glm-5-1-successor-001/002 | successor_operator_chain | PASS ×2 |
| glm-5-1-demand-stateless-001, history-001, history-002 | demand_driven_microfactory | FAIL ×3 (1 budget, 2 field range) |
