#!/usr/bin/env python3
"""Seed-replicated sweet-spot analysis: U(a) across 3 seeds, mean +/- CI, peak fit.

Collects the eval sessions of the 5 mixed-surrogate arms (a = 0, 0.25, 0.5, 0.75,
1.0) across seed 1 (care-aXXX-it6 / care-v7qs-it6 for a=0) and seeds 2/3
(care-aXXX-s2/s3), computes market profit and the hardened execution ruler, and
fits the pre-registered reward curve U(a) = U0 + A(1-exp(-a/tau)) - B a^gamma.
"""
import glob, json, statistics as st, sys
import numpy as np
from scipy.optimize import curve_fit

BENCH = '/home/exuber/CODE/CORE/pythonProject1/AUTORESEARCH/MechanogenesisBench-upstream'
DESK = {0: (420, 280), 1: (420, 280), 2: (420, 280), 3: (420, 280), 4: (300, 200)}
ARMS = {
    0.0: ['care-v7qs-it6', 'care-a000-s2', 'care-a000-s3'],
    0.25: ['care-a025-it6', 'care-a025-s2', 'care-a025-s3'],
    0.5: ['care-a050-it6', 'care-a050-s2', 'care-a050-s3'],
    0.75: ['care-a075-it6', 'care-a075-s2', 'care-a075-s3'],
    1.0: ['care-a100-it6', 'care-a100-s2', 'care-a100-s3'],
}


def sp(s):
    return 1.5 if s < 10 else 1.2 if s < 30 else 1.0 if s < 60 else 0.8 if s < 120 else 0.5


def session(f):
    r = json.load(open(f))
    hard = 0.0
    for rd in r['rounds']:
        cad = rd.get('cad') or {}
        ex = cad.get('extent')
        fit = bool(ex and ex[0] <= DESK[rd['rd']][0] + 0.01 and ex[1] <= DESK[rd['rd']][1] + 0.01)
        clean = cad.get('intersections', 0) == 0
        reuse = (rd['rd'] == 0) or bool(rd.get('reused'))
        if fit and clean and reuse:
            hard += round(100 * sp(rd.get('secs', 30)))
    return {'profit': r['profit'], 'hard': hard}


def collect(tag):
    return [session(f) for f in sorted(glob.glob(f'{BENCH}/runs/local_model_eval/{tag}_*/result.json'))]


def fit_curve(a, y):
    def f(x, u0, A, tau, B, g):
        return u0 + A * (1 - np.exp(-x / max(tau, 1e-3))) - B * np.power(x, g)
    p0 = [min(y), max(y) - min(y), 0.3, 1.0, 1.0]
    try:
        popt, _ = curve_fit(f, a, y, p0=p0, maxfev=20000,
                            bounds=([-1e9, 0, 0.01, 0, 0.1], [1e9, 1e9, 10, 1e9, 5]))
        xs = np.linspace(0, 1, 501)
        ys = f(xs, *popt)
        return {'params': [round(float(x), 4) for x in popt],
                'a_star': round(float(xs[int(np.argmax(ys))]), 3),
                'fit': [round(float(f(x, *popt)), 1) for x in a]}
    except Exception as e:
        return {'error': str(e)}


def main():
    out = {'market': {}, 'hard': {}, 'seed_means': {}}
    print(f"{'a':>5} {'tag':22s} {'n':>3s} {'market':>7s} {'hard':>6s}")
    for a, tags in ARMS.items():
        out['market'][a] = []
        out['hard'][a] = []
        for tag in tags:
            ss = collect(tag)
            if not ss:
                print(f'{a:5.2f} {tag:22s} no sessions')
                continue
            m = st.mean([x['profit'] for x in ss])
            h = st.mean([x['hard'] for x in ss])
            out['market'][a].append(round(m, 1))
            out['hard'][a].append(round(h, 1))
            print(f'{a:5.2f} {tag:22s} {len(ss):3d} {m:7.0f} {h:6.0f}')
        if out['market'][a]:
            ms = out['market'][a]; hs = out['hard'][a]
            out['seed_means'][a] = {
                'market_mean': round(st.mean(ms), 1),
                'market_sd': round(st.stdev(ms), 1) if len(ms) > 1 else 0.0,
                'market_ci95': round(1.96 * st.stdev(ms) / np.sqrt(len(ms)), 1) if len(ms) > 1 else 0.0,
                'hard_mean': round(st.mean(hs), 1),
                'hard_sd': round(st.stdev(hs), 1) if len(hs) > 1 else 0.0,
            }
            print(f'      => seed mean {st.mean(ms):.0f} +/- {out["seed_means"][a]["market_ci95"]:.0f} '
                  f'| hard {st.mean(hs):.0f}')
    xs = sorted(out['seed_means'])
    if len(xs) >= 4:
        ym = [out['seed_means'][a]['market_mean'] for a in xs]
        yh = [out['seed_means'][a]['hard_mean'] for a in xs]
        out['fit_market'] = fit_curve(np.array(xs), np.array(ym))
        out['fit_hard'] = fit_curve(np.array(xs), np.array(yh))
        print('\nfit market:', out['fit_market'])
        print('fit hard  :', out['fit_hard'])
    json.dump(out, open(f'{BENCH}/runs/probes/seedrep_analysis.json', 'w'), indent=2)
    print('saved runs/probes/seedrep_analysis.json')


if __name__ == '__main__':
    main()
