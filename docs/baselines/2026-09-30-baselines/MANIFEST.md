# Baseline evidence bundle — public-task model baselines (2026-09-30)

Machine: single workstation, Linux. GLM transport: Anthropic-compatible channel via
`tools/openai_anthropic_shim.py`; MiMo transport: native `https://api.xiaomimimo.com/v1`
(OpenAI-compatible, `reasoning_effort` omitted — provider rejects that GLM-specific field).
Sampling policy per docs/LEADERBOARD.md §Reproduction. Each run directory holds run.json,
verification.json, score.json, evaluation.json as produced by `mbench run/verify/score`.

| Run | Task | Outcome |
|---|---|---|
| reference-successor | successor_operator_chain | PASS |
| glm53-flash-successor-002/003 | successor_operator_chain | PASS ×2 |
| glm53-flash-successor-stateless-001 | successor_operator_chain | FAIL (schema; policy deviation, excluded) |
| glm53-flash-demand-stateless-001, history-004 | demand_driven_microfactory | PASS ×2 |
| glm53-flash-demand-history-003 | demand_driven_microfactory | FAIL (capital budget; scored 0) |
| glm53-flash-demand-history-001/002 | demand_driven_microfactory | FAIL (transport; excluded) |
| glm-5-2-successor-001/002 | successor_operator_chain | PASS ×2 |
| glm-5-2-demand-history-001 | demand_driven_microfactory | PASS |
| glm-5-2-demand-stateless-001, history-002 | demand_driven_microfactory | FAIL (model decisions; scored 0) |
| glm-5-1-successor-001/002 | successor_operator_chain | PASS ×2 |
| glm-5-1-demand-* (3 runs) | demand_driven_microfactory | FAIL ×3 (model decisions; scored 0) |
| mimo-v2-6-{pro,flash}-successor-001/002 | successor_operator_chain | PASS ×4 |
| mimo-*-demand-{stateless,history-001,history-002} (6 runs) | demand_driven_microfactory | FAIL (HTTP 400 protocol: reasoning_effort rejected; excluded, superseded by demand2) |
| mimo-v2-6-pro-demand2-* (3 runs) | demand_driven_microfactory | FAIL ×3 (2 budget, 1 range; scored 0) |
| mimo-v2-6-flash-demand2-stateless-001 | demand_driven_microfactory | FAIL (budget; scored 0) |
| mimo-v2-6-flash-demand2-history-001 | demand_driven_microfactory | PASS |
| mimo-v2-6-flash-demand2-history-002 | demand_driven_microfactory | system_timeout (wall budget; excluded) |
| glm-5-3-successor-001/002 | successor_operator_chain | PASS ×2 |
| glm-5-3-demand-* (3 runs) | demand_driven_microfactory | FAIL ×3 (1 budget, 2 range; scored 0) |
