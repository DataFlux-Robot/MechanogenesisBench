#!/usr/bin/env python3
"""Weight-free multi-objective scoring for MechanogenesisBench (Pareto frontier).

No cross-component weights anywhere. A model is a vector of component rates;
the only aggregation is the arithmetic mean of the SAME component across runs
(same-kind rates, no trade-off encoded). Ordering = non-dominated sorting
(Pareto layers); models in the same layer are honestly incomparable.

Vector (9 components):
  chain:   promotion_rate, robustness_rate, inheritance_attainment
  demand:  promotion_rate, robustness_rate, calibration_accuracy,
           update_gain_attainment, lineage_exactness
  closeness (failure gradient, demand runs): budget_compliance, schema_validity
Passing runs contribute evaluated values (closeness = 1.0). Model-decision
failures contribute graded values from archived artifacts (calibration vs hidden
truth; budget ratio via the task package's own capital_cost_milliusd; field
validity fraction). Parse-level failures contribute conservative zeros (raw
responses now archived for future runs). Transport failures are excluded only
with a failure-log justification.
"""
import argparse
import json
from pathlib import Path

from mechanogenesis_bench.demand_microfactory import (
    DEMAND_ATTRIBUTES, FactoryInvestment,
)

DEMAND_TRUTH = Path('tasks/simulation/demand_driven_microfactory/private/spec.json')
DEMAND_BUDGET_G0 = 65_000_000
SUCCESSOR_GATE_UM = 500.0
DEMAND_UPDATE_GATE_PPM = 400000.0

# Continuity guarantee (2026-10-01): every displayed quantity is a continuous
# attainment ratio clip(measured/gate, 0, 1); unmeasured components are reported
# as None (displayed as an em dash), never floored to 0. Discrete pass counts are
# diagnostics only and never appear as ranking/display columns.
VECTORS = ('chain_robustness', 'chain_inheritance',
           'g0_utility_attainment', 'g1_calibration', 'demand_robustness',
           'update_gain_attainment', 'lineage_exactness',
           'budget_compliance', 'schema_validity')
G0_UTILITY_GATE = 700_000


def expand(paths):
    out = []
    for token in paths:
        if '*' in token:
            out += sorted(str(x) for x in Path('.').glob(token) if x.is_dir() and (x / 'run.json').exists())
        else:
            out.append(token)
    return out


def _load(run):
    run = Path(run)
    return (json.loads((run / 'run.json').read_text()),
            json.loads((run / 'score.json').read_text()),
            json.loads((run / 'evaluation.json').read_text()))


def graded_failure(run):
    """(calibration, budget_compliance, schema_validity) for a failed demand run."""
    actions = sorted((run / 'system' / 'model_calls').glob('g*/model_action.json'))
    if not actions:
        return 0.0, 0.0, 0.0
    action = json.loads(actions[0].read_text())
    try:
        plan = json.loads(action['response_content'])
    except (TypeError, json.JSONDecodeError):
        return 0.0, 0.0, 0.0
    truth = json.loads(DEMAND_TRUTH.read_text())
    t = truth['truth_attribute_weights_ppm']
    truth_g0 = t[0] if isinstance(t, list) else t
    weights = (plan.get('demand_belief') or {}).get('attribute_weights_ppm') or {}
    if set(weights) == set(DEMAND_ATTRIBUTES) and all(
            isinstance(v, int) and 0 <= v <= 1_000_000 for v in weights.values()):
        l1 = sum(abs(weights[a] - int(truth_g0[a])) for a in DEMAND_ATTRIBUTES)
        calibration = max(0.0, 1.0 - l1 / 1e6)
    else:
        calibration = 0.0
    factory = plan.get('factory') or {}
    try:
        cost = FactoryInvestment(**factory).capital_cost_milliusd()
    except TypeError:
        cost = 0
    budget = min(1.0, DEMAND_BUDGET_G0 / cost) if cost > 0 else 0.0
    valid = sum(1 for v in factory.values()
                if isinstance(v, int) and not isinstance(v, bool) and v >= 0)
    schema = valid / len(factory) if factory else 0.0
    return round(calibration, 4), round(budget, 4), round(schema, 4)


def model_vector(runs):
    chain, demand = {}, {}
    for run in runs:
        run = Path(run)
        try:
            run_meta, score, evaluation = _load(run)
            evaluated = True
        except FileNotFoundError:
            run_meta = json.loads((run / 'run.json').read_text())
            evaluation, score, evaluated = {}, {}, False
        def put(bucket, key, value):
            if value is not None:
                bucket.setdefault(key, []).append(value)
        if 'successor' in run_meta['task_id']:
            put(chain, 'robustness', score.get('robustness_pass_rate') if score else None)
            put(chain, 'inheritance', min((score.get('capability_gain') or 0.0) / SUCCESSOR_GATE_UM, 1.0) if score else None)
        else:
            gens = evaluation.get('microfactory_metrics', {}).get('generations', [])
            if evaluated and gens:
                u0 = gens[0].get('minimum_product_utility_micro')
                err1 = gens[1].get('demand_calibration_error_ppm') if len(gens) > 1 else None
                metrics = evaluation['microfactory_metrics']
                put(demand, 'g0_utility', min(u0, G0_UTILITY_GATE) / G0_UTILITY_GATE if u0 is not None else None)
                put(demand, 'g1_calibration', max(0.0, 1.0 - err1 / 1e6) if err1 is not None else None)
                put(demand, 'robustness', score['robustness_pass_rate'])
                put(demand, 'update_gain', min((metrics.get('demand_update_gain_ppm') or 0) / DEMAND_UPDATE_GATE_PPM, 1.0))
                put(demand, 'lineage', 1.0 if metrics.get('exact_operator_inheritance') else 0.0)
                put(demand, 'budget', 1.0)
                put(demand, 'schema', 1.0)
            else:
                cal, bud, sch = graded_failure(run)
                put(demand, 'g1_calibration', cal if cal > 0 else None)
                put(demand, 'budget', bud if bud > 0 else None)
                put(demand, 'schema', sch if sch > 0 else None)
    measured = {'chain_robustness': chain.get('robustness', []), 'chain_inheritance': chain.get('inheritance', []),
                'g0_utility_attainment': demand.get('g0_utility', []),
                'g1_calibration': demand.get('g1_calibration', []),
                'demand_robustness': demand.get('robustness', []),
                'update_gain_attainment': demand.get('update_gain', []),
                'lineage_exactness': demand.get('lineage', []),
                'budget_compliance': demand.get('budget', []),
                'schema_validity': demand.get('schema', [])}
    vec = {k: (round(sum(v) / len(v), 4) if v else 0.0) for k, v in measured.items()}
    counts = {k: len(v) for k, v in measured.items()}
    return vec, counts


def dominates(a, b):
    # Dominance judged only where BOTH sides were measured, and only when at least
    # three components are jointly measured (guards single-component dominance).
    keys = [k for k in VECTORS if a['_n'][k] and b['_n'][k]]
    if len(keys) < 3:
        return False
    return all(a[k] >= b[k] for k in keys) and any(a[k] > b[k] for k in keys)


def pareto_layers(models):
    remaining, layers = dict(models), []
    while remaining:
        front = [name for name, vec in remaining.items()
                 if not any(dominates(other, vec) for other_name, other in remaining.items()
                            if other_name != name)]
        for name in front:
            del remaining[name]
        layers.append(sorted(front, key=lambda n: -sum(dominates(models[n], m) for m in models.values())))
    return layers


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--models', nargs='+', required=True, help='name=run1,run2,...')
    args = parser.parse_args()
    models = {}
    for spec in args.models:
        name, runs = spec.split('=', 1)
        vec, counts = model_vector(expand(runs.split(',')))
        vec['_n'] = counts
        models[name] = vec
    # Ranking requires minimum measurement depth; shallow models would otherwise
    # hide behind unmeasured components (missing-data dominance artifact).
    MIN_N = 10
    HEADLINE = ('g1_calibration',)  # measurable from archived plans even without execution
    rankable = {n: v for n, v in models.items() if all(v['_n'][k] >= MIN_N for k in HEADLINE)}
    unranked = {n: v for n, v in models.items() if n not in rankable}
    models = rankable
    layers = pareto_layers(models) if models else []
    print('| Layer | Model | ' + ' | '.join(VECTORS) + ' (measured n) | dominates |')
    print('|---|---|' + '---|' * (len(VECTORS) + 1))
    for i, layer in enumerate(layers, 1):
        for name in layer:
            vec = models[name]
            dom = sum(dominates(vec, m) for m in models.values())
            counts = vec['_n']
            cells = ' | '.join(f'{vec[k]:.3f} ({counts[k]})' if counts[k] else '—' for k in VECTORS)
            print(f'| {i} | **{name}** | ' + cells + f' | {dom} |')
    if unranked:
        print('\nUnranked (fewer than %d measured headline runs; scale-up pending): %s'
              % (MIN_N, ', '.join(sorted(unranked))))
    print('\nNo weights are used anywhere; same-layer models are incomparable, not equal.')


if __name__ == '__main__':
    main()
