#!/usr/bin/env python3
"""Reward-usage sweet-spot analysis.

Reads the n=10 eval arms trained with the mixed surrogate y_a = (1-a)Q + a(R/10)
(a = 0.25, 0.5, 0.75, 1.0; a=0 is the existing geometry-surrogate arm) and the
judge-trained reference, computes judged profit and the hardened execution ruler,
and reports the reward-side inverted-U fit.

Usage: python tools/analyze_sweetspot_reward.py
"""
import glob, json, statistics as st
from pathlib import Path

BENCH = Path(__file__).resolve().parent.parent
EVAL = BENCH / 'runs' / 'local_model_eval'
DESK = {0: (420, 280), 1: (420, 280), 2: (420, 280), 3: (420, 280), 4: (300, 200)}
ARMS = [
    ('a=0.00 geometry', 'care-v7qs-it6'),
    ('a=0.25', 'care-a025-it6'),
    ('a=0.50', 'care-a050-it6'),
    ('a=0.75', 'care-a075-it6'),
    ('a=1.00', 'care-a100-it6'),
    ('judge-trained @6', 'care-v4b-it2'),
]


def speed_price(s):
    return 1.5 if s < 10 else 1.2 if s < 30 else 1.0 if s < 60 else 0.8 if s < 120 else 0.5


def session(result):
    hard = fit = clean = reuse = 0
    rev_hard = 0.0
    for rd in result['rounds']:
        cad = rd.get('cad') or {}
        ex = cad.get('extent')
        f = bool(ex and ex[0] <= DESK[rd['rd']][0] + 0.01 and ex[1] <= DESK[rd['rd']][1] + 0.01)
        c = cad.get('intersections', 0) == 0
        r = (rd['rd'] == 0) or bool(rd.get('reused'))
        fit += f; clean += c; reuse += r
        price = round(100 * speed_price(rd.get('secs', 30)))
        if f and c and r:
            hard += 1; rev_hard += price
    return {'profit': result.get('profit', 0), 'fit': fit, 'clean': clean, 'reuse': reuse,
            'hard': hard, 'n': len(result['rounds']), 'rev_hard': rev_hard}


def main():
    out = {}
    print(f"{'arm':20s} {'n':>2s} | {'judge ¥':>7s} {'median':>6s} | {'hard':>7s} {'hard ¥':>7s}")
    for name, tag in ARMS:
        files = sorted(glob.glob(str(EVAL / f'{tag}_*' / 'result.json')))
        ss = [session(json.load(open(f))) for f in files]
        if not ss:
            print(f'{name}: no sessions'); continue
        n = len(ss)
        profit = st.mean([s['profit'] for s in ss])
        hard_rev = st.mean([s['rev_hard'] for s in ss])
        hard = sum(s['hard'] for s in ss)
        tot = sum(s['n'] for s in ss)
        out[name] = {'tag': tag, 'n': n, 'judge_mean': round(profit),
                     'judge_median': round(st.median([s['profit'] for s in ss])),
                     'hard': f'{hard}/{tot}', 'hard_rev_mean': round(hard_rev)}
        print(f"{name:20s} {n:2d} | {profit:7.0f} {st.median([s['profit'] for s in ss]):6.0f} | "
              f"{hard:3d}/{tot:<3d} {hard_rev:7.0f}")
    json.dump(out, open(BENCH / 'runs' / 'probes' / 'sweetspot_reward.json', 'w'), indent=2)
    print('saved runs/probes/sweetspot_reward.json')


if __name__ == '__main__':
    main()
