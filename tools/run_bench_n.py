#!/usr/bin/env python3
"""Run money_bench_v5 sessions for a commercial designer with results on local disk.
Usage: python tools/run_bench_n.py --designer deepseek-flash --n 5
"""
import argparse, json, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import money_bench_v5 as mb

RESULTS_LOCAL = HERE.parent / 'runs' / 'local_bench'

ap = argparse.ArgumentParser()
ap.add_argument('--designer', required=True, choices=list(mb.MODELS))
ap.add_argument('--judges', nargs='+', default=['mimo-v2.6-pro'])
ap.add_argument('--n', type=int, default=5)
a = ap.parse_args()

mb.RESULTS = RESULTS_LOCAL
judges = {j: mb.MODELS[j] for j in a.judges if j in mb.MODELS}
all_runs = []
for i in range(a.n):
    root = RESULTS_LOCAL / a.designer / time.strftime('%Y%m%d_%H%M%S')
    print(f"\n💰 {a.designer} session {i+1}/{a.n}")
    r = mb.run(mb.MODELS[a.designer], judges, a.designer, root)
    (root / 'result.json').write_text(json.dumps(r, indent=2, ensure_ascii=False) + '\n')
    mb.display(r)
    all_runs.append(r)
out = RESULTS_LOCAL / f'{a.designer}_all_runs.json'
out.write_text(json.dumps(all_runs, ensure_ascii=False, indent=2))
profits = [r['profit'] for r in all_runs]
print(f"\n{a.designer}: n={len(all_runs)} profit mean={sum(profits)/len(profits):.1f} runs={[round(p,1) for p in profits]}")
