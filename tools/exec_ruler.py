#!/usr/bin/env python3
"""Hardened execution ruler (demand-faithful, judge-free).

The soft execution ruler (desk-fit only) saturates for every trained arm and hides
physics differences. The demands themselves require more: no self-intersecting
parts, and rounds 2-5 MUST reuse capital. This ruler sells a round iff all three
hold, then applies the unchanged speed pricing.

Usage:
  python tools/exec_ruler.py --tags care-v4b-it2 care-v7qs-it6 care-v8comp-it6
Output: leaderboard/data/exec_ruler.json + a printed table.
"""
import argparse, glob, json, statistics as st
from pathlib import Path

BENCH = Path(__file__).resolve().parent.parent
EVAL = BENCH / 'runs' / 'local_model_eval'
OUT = BENCH / 'leaderboard' / 'data' / 'exec_ruler.json'
DESK = {0: (420, 280), 1: (420, 280), 2: (420, 280), 3: (420, 280), 4: (300, 200)}


def speed_price(secs):
    if secs < 10: return 1.5
    if secs < 30: return 1.2
    if secs < 60: return 1.0
    if secs < 120: return 0.8
    return 0.5


def run_session(result):
    fit = clean = reuse = hard = 0
    rev_hard = rev_soft = 0.0
    for rd in result['rounds']:
        cad = rd.get('cad') or {}
        ex = cad.get('extent')
        inter = cad.get('intersections', 0)
        f = bool(ex and ex[0] <= DESK[rd['rd']][0] + 0.01 and ex[1] <= DESK[rd['rd']][1] + 0.01)
        c = (inter == 0)
        r = (rd['rd'] == 0) or bool(rd.get('reused'))
        fit += f; clean += c; reuse += r
        price = round(100 * speed_price(rd.get('secs', 30)))
        if f:
            rev_soft += price
        if f and c and r:
            hard += 1
            rev_hard += price
    return {'profit': result.get('profit'), 'n': len(result['rounds']),
            'fit': fit, 'clean': clean, 'reuse': reuse, 'hard': hard,
            'rev_soft': rev_soft, 'rev_hard': rev_hard}


def sig(run):
    return (run['profit'], tuple((x['rd'], x['rating'], x['rev'], x['sold']) for x in run['rounds']))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tags', nargs='+', required=True)
    ap.add_argument('--archive', default='', help='optional JSON archive of run lists to filter against')
    ap.add_argument('--arm', default='', help='archive key to filter against (with --archive)')
    ap.add_argument('--out', default=str(OUT))
    a = ap.parse_args()
    out = {}
    arch_sigs = None
    if a.archive and a.arm:
        arch = json.load(open(a.archive))[a.arm]
        arch_sigs = {sig(r) for r in arch}
    print(f"{'arm':28s} {'n':>3s} | {'judge':>6s} | {'fit':>7s} {'clean':>7s} {'reuse':>7s} {'hard':>7s} | {'hard ¥':>7s}")
    for tag in a.tags:
        files = sorted(glob.glob(str(EVAL / f'{tag}_*' / 'result.json')))
        raw = [json.load(open(f)) for f in files]
        if arch_sigs is not None:
            raw = [r for r in raw if sig(r) in arch_sigs]
        sessions = [run_session(r) for r in raw]
        if not sessions:
            print(f'{tag}: no sessions'); continue
        n = len(sessions)
        tot = {k: sum(s[k] for s in sessions) for k in ('n', 'fit', 'clean', 'reuse', 'hard')}
        judge = st.mean([s['profit'] for s in sessions])
        hard_rev = st.mean([s['rev_hard'] for s in sessions])
        out[tag] = {'sessions': n, 'judge_mean': round(judge),
                    'fit': f"{tot['fit']}/{tot['n']}", 'clean': f"{tot['clean']}/{tot['n']}",
                    'reuse': f"{tot['reuse']}/{tot['n']}", 'hard': f"{tot['hard']}/{tot['n']}",
                    'hard_rev_mean': round(hard_rev),
                    'hard_rev_median': round(st.median([s['rev_hard'] for s in sessions])),
                    'soft_rev_mean': round(st.mean([s['rev_soft'] for s in sessions])),
                    'per_session': [{'rev_hard': s['rev_hard'], 'hard': s['hard']} for s in sessions]}
        print(f"{tag:28s} {n:3d} | {judge:6.0f} | {tot['fit']:3d}/{tot['n']:<3d} {tot['clean']:3d}/{tot['n']:<3d} "
              f"{tot['reuse']:3d}/{tot['n']:<3d} {tot['hard']:3d}/{tot['n']:<3d} | {hard_rev:7.0f}")
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(a.out, 'w'), indent=2)
    print('saved', a.out)


if __name__ == '__main__':
    main()
