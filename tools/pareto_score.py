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

VECTORS = ('chain_promotion', 'chain_robustness', 'chain_inheritance',
           'demand_promotion', 'demand_robustness', 'demand_calibration',
           'demand_update_gain', 'demand_lineage',
           'budget_compliance', 'schema_validity')


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
            passed = run_meta.get('status') == 'complete' and score.get('eligible')
        except FileNotFoundError:
            run_meta = json.loads((run / 'run.json').read_text())
            passed = False
        if 'successor' in run_meta['task_id']:
            if passed:
                row = {'promotion': score['promotions'] / 2,
                       'robustness': score['robustness_pass_rate'],
                       'inheritance': min((score.get('capability_gain') or 0.0) / SUCCESSOR_GATE_UM, 1.0)}
            else:
                row = {'promotion': 0.0, 'robustness': 0.0, 'inheritance': 0.0}
            for k, v in row.items():
                chain.setdefault(k, []).append(v)
        else:
            if passed:
                metrics = evaluation['microfactory_metrics']
                gens = metrics.get('generations', [{}])
                err = min((g.get('demand_calibration_error_ppm') or 1e6) for g in gens) if gens else 1e6
                row = {'promotion': score['promotions'] / 2,
                       'robustness': score['robustness_pass_rate'],
                       'calibration': max(0.0, 1.0 - err / 1e6),
                       'update_gain': min((metrics.get('demand_update_gain_ppm') or 0) / DEMAND_UPDATE_GATE_PPM, 1.0),
                       'lineage': 1.0 if metrics.get('exact_operator_inheritance') else 0.0,
                       'budget': 1.0, 'schema': 1.0}
            else:
                cal, bud, sch = graded_failure(run)
                row = {'promotion': 0.0, 'robustness': 0.0, 'calibration': cal,
                       'update_gain': 0.0, 'lineage': 0.0, 'budget': bud, 'schema': sch}
            for k, v in row.items():
                demand.setdefault(k, []).append(v)
    vec = {'chain_promotion': chain.get('promotion', [0.0]), 'chain_robustness': chain.get('robustness', [0.0]),
           'chain_inheritance': chain.get('inheritance', [0.0]),
           'demand_promotion': demand.get('promotion', [0.0]), 'demand_robustness': demand.get('robustness', [0.0]),
           'demand_calibration': demand.get('calibration', [0.0]),
           'demand_update_gain': demand.get('update_gain', [0.0]), 'demand_lineage': demand.get('lineage', [0.0]),
           'budget_compliance': demand.get('budget', [0.0]), 'schema_validity': demand.get('schema', [0.0])}
    return {k: round(sum(v) / len(v), 4) for k, v in vec.items()}, \
        {k: len(v) for k, v in vec.items()}


def dominates(a, b):
    return all(a[k] >= b[k] for k in VECTORS) and any(a[k] > b[k] for k in VECTORS)


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
        vec, counts = model_vector(runs.split(','))
        models[name] = vec
    layers = pareto_layers(models)
    print('| Layer | Model | ' + ' | '.join(VECTORS) + ' | dominates |')
    print('|---|---|' + '---|' * (len(VECTORS) + 1))
    for i, layer in enumerate(layers, 1):
        for name in layer:
            vec = models[name]
            dom = sum(dominates(vec, m) for m in models.values())
            print(f'| {i} | **{name}** | ' + ' | '.join(f'{vec[k]:.3f}' for k in VECTORS) + f' | {dom} |')
    print('\nNo weights are used anywhere; same-layer models are incomparable, not equal.')


if __name__ == '__main__':
    main()
