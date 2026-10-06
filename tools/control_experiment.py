#!/usr/bin/env python3
"""Control group experiment: is the acceleration from REUSE or just shorter prompts?

Runs the SAME model under 4 conditions:
  treatment:  normal (capital = real STEP files from previous rounds)
  no_capital: capital list is EMPTY in all rounds (same prompts otherwise)
  shuffled:   capital list has WRONG round numbers (r3 asset listed as r1)
  self_only:  capital only has the immediately previous round (not all history)

If acceleration (speed↑) only happens in treatment → reuse is the cause ✅
If acceleration happens in all conditions → it's just prompt shortening ❌
"""
import argparse, json, os, sys, time
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from money_bench_v5 import (
    MODELS, DEMANDS, SYSTEM, JUDGE_SYS,
    anthropic_call, call, real_cad_eval, check_real_reuse,
    multi_judge, speed_price, PRICE, ACCEPT, TOKEN_PRICE
)

RESULTS = Path('/home/exuber/CODE/CORE/pythonProject1/AUTORESEARCH/MechanogenesisBench-upstream/runs/control_experiments')


def manipulate_capital(capital, condition, rd):
    """Apply the control condition to the capital registry."""
    if condition == 'treatment':
        return capital  # normal: all previous rounds' STEP files
    elif condition == 'no_capital':
        return {}  # empty: model must build from scratch every round
    elif condition == 'shuffled':
        # Wrong association: rename keys so r1↔r3, r2↔r4 etc.
        shuffled = {}
        items = list(capital.items())
        n = len(items)
        for i, (k, v) in enumerate(items):
            j = (i + 2) % n if n > 2 else (i + 1) % n
            shuffled[items[j][0]] = v  # value from wrong round under this key
        return shuffled
    elif condition == 'self_only':
        # Only the immediately previous round's design
        prev_key = f'r{rd}'  # r1, r2, ...
        return {k: v for k, v in capital.items() if k == prev_key}
    return capital


def run_condition(spec, judges, dn, condition, root, n_rounds=5):
    root = Path(root); root.mkdir(parents=True, exist_ok=True)
    capital = {}  # real capital registry
    rounds = []

    for rd in range(n_rounds):
        # Apply control condition to what the model sees
        visible_capital = manipulate_capital(dict(capital), condition, rd)

        best_text, best_usage, best_cad, best_secs = None, None, None, 0
        reused = False

        for att in range(2):
            label = f'r{rd}_a{att}'
            msg = json.dumps({
                'demand': DEMANDS[rd],
                'capital': [{'id': k, 'desc': v.get('description', '')}
                           for k, v in visible_capital.items()],
                'hint': 'Use capital(asset_id) to import previous modules.' if visible_capital else None})
            try:
                text, usage, secs = call(spec, SYSTEM, msg, root / label, label)
                if not text.strip(): continue
                # CAD eval uses the VISIBLE capital (what the model sees)
                cad = real_cad_eval(text, visible_capital, root / label / 'cad')
                if cad.get('metrics'):
                    best_text, best_usage, best_cad, best_secs = text, usage, cad, secs
                    reused = check_real_reuse(text, set(visible_capital.keys()))
                    break
            except: continue

        if best_cad is None:
            rounds.append({'rd': rd, 'rating': 0, 'sold': False, 'rev': 0,
                          'reused': False, 'secs': 0, 'cad': None})
            continue

        # Judge
        scores = multi_judge(judges, DEMANDS[rd], best_text, best_cad, root, rd)
        ratings = [s['rating'] for s in scores if s['rating'] > 0]
        median_rating = sorted(ratings)[len(ratings)//2] if ratings else 0
        sold = median_rating >= ACCEPT
        sp = speed_price(best_secs)
        rev = round(PRICE * sp) if sold else 0

        # Register capital (ALWAYS register the real output, regardless of condition)
        # This ensures the capital registry is identical across conditions;
        # only what the model SEES differs.
        if best_cad.get('step_path'):
            capital[f'r{rd+1}'] = {
                'status': 'EXECUTED_CAD',
                'step_path': best_cad['step_path'],
                'description': f'Round {rd+1}',
                'measurements': best_cad.get('metrics', {}),
            }

        rounds.append({'rd': rd, 'rating': median_rating, 'sold': sold,
                      'rev': rev, 'reused': reused, 'secs': best_secs,
                      'cad': best_cad.get('facts_summary')})

        ic = '✅' if sold else '❌'; ru = '♻️' if reused else '🔧'
        print(f'  {condition} R{rd+1}: {ic} {median_rating}/10 {ru} {best_secs:.0f}s', flush=True)

    # Compute metrics
    early = [r for r in rounds if r['rd'] < 2 and r['secs'] > 0]
    late = [r for r in rounds if r['rd'] >= 3 and r['secs'] > 0]
    et = sum(r['secs'] for r in early) / max(len(early), 1)
    lt = sum(r['secs'] for r in late) / max(len(late), 1)
    t_accel = round(et / lt, 2) if lt > 0 else None

    total_rev = sum(r['rev'] for r in rounds)
    total_sold = sum(1 for r in rounds if r['sold'])
    total_reuse = sum(1 for r in rounds if r.get('reused'))

    return {'designer': dn, 'condition': condition, 'rounds': rounds,
            'total_rev': total_rev, 'total_sold': f'{total_sold}/{n_rounds}',
            'total_reuse': f'{total_reuse}/{n_rounds-1}',
            't_accel': t_accel,
            'avg_rating': round(sum(r['rating'] for r in rounds) / n_rounds, 1)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--designer', required=True, choices=list(MODELS))
    p.add_argument('--judge', default='mimo-v2.6-pro')
    p.add_argument('--conditions', nargs='+',
                   default=['treatment', 'no_capital', 'shuffled', 'self_only'])
    a = p.parse_args()

    ds = MODELS[a.designer]
    judges = {a.judge: MODELS[a.judge]}
    for s, n in [(ds, a.designer)] + [(v, k) for k, v in judges.items()]:
        if s.get('key_env') and not os.environ.get(s['key_env']):
            print(f'FATAL: {s["key_env"]} not set'); sys.exit(1)

    tag = time.strftime('%Y%m%d_%H%M%S')
    all_results = []

    for cond in a.conditions:
        root = RESULTS / a.designer / f'{cond}_{tag}'
        print(f'\n{"=" * 50}')
        print(f'  Condition: {cond}')
        print(f'{"=" * 50}')
        result = run_condition(ds, judges, a.designer, cond, root)
        all_results.append(result)

    # Summary comparison
    print(f'\n{"=" * 70}')
    print(f'  CONTROL EXPERIMENT RESULTS: {a.designer}')
    print(f'{"=" * 70}')
    print(f'  {"Condition":15s} | {"Revenue":>8s} | {"Sold":>6s} | {"Reuse":>6s} | {"Accel":>6s} | {"Rating":>6s}')
    print(f'  {"-" * 65}')
    for r in all_results:
        accel = f'{r["t_accel"]}x' if r.get('t_accel') else '—'
        print(f'  {r["condition"]:15s} | ¥{r["total_rev"]:7.0f} | {r["total_sold"]:>6s} | {r["total_reuse"]:>6s} | {accel:>6s} | {r["avg_rating"]:5.1f}')

    # Statistical conclusion
    tr = next((r for r in all_results if r['condition'] == 'treatment'), None)
    nc = next((r for r in all_results if r['condition'] == 'no_capital'), None)
    if tr and nc:
        print(f'\n  PRSI VERDICT:')
        if tr['t_accel'] and nc['t_accel']:
            if tr['t_accel'] > nc['t_accel'] * 1.2:
                print(f'  ✅ Acceleration is from REUSE ({tr["t_accel"]}x vs {nc["t_accel"]}x without capital)')
            else:
                print(f'  ❌ Acceleration NOT from reuse ({tr["t_accel"]}x vs {nc["t_accel"]}x — similar)')
        if tr['total_rev'] > nc['total_rev']:
            print(f'  ✅ Revenue higher with capital (¥{tr["total_rev"]} vs ¥{nc["total_rev"]})')
        else:
            print(f'  ❌ Revenue NOT higher with capital')

    out = RESULTS / a.designer / f'control_{tag}.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(all_results, indent=2, ensure_ascii=False) + '\n')
    print(f'\n  Results: {out}')


if __name__ == '__main__':
    main()
