#!/usr/bin/env python3
"""Statistical analysis: Kruskal-Wallis + Mann-Whitney + effect sizes."""
import json, math, sys
from pathlib import Path
from collections import defaultdict
import statistics

def load_profits(dirs):
    models = defaultdict(list)
    for src in dirs:
        src = Path(src)
        if not src.exists(): continue
        for rf in sorted(src.rglob('result.json')):
            try:
                r = json.loads(rf.read_text())
                m = r['designer']
                p = r.get('profit', r.get('total_rev', 0) - r.get('total_cost', 0))
                models[m].append(p)
            except: pass
    return dict(models)

def kruskal_wallis(groups):
    all_v = []
    for vals in groups.values(): all_v += vals
    n = len(all_v)
    if n < 3 or len(groups) < 2: return None
    sorted_v = sorted(all_v)
    rank_map = {}
    i = 0
    while i < len(sorted_v):
        j = i
        while j+1 < len(sorted_v) and sorted_v[j+1] == sorted_v[i]: j += 1
        avg = (i + j + 2) / 2
        for k in range(i, j+1): rank_map[sorted_v[k]] = avg
        i = j + 1
    k = len(groups)
    grand_mean = (n + 1) / 2
    H = 12.0 / (n * (n + 1)) * sum(
        len(vals) * (sum(rank_map[v] for v in vals)/len(vals) - grand_mean)**2
        for vals in groups.values())
    # chi-square p (df=k-1)
    df = k - 1
    if df == 1:
        p = 2 * (1 - 0.5*(1+math.erf(math.sqrt(H/2)/math.sqrt(2))))
    else:
        z = ((H/df)**(1/3) - (1 - 2/(9*df))) / math.sqrt(2/(9*df))
        p = 1 - 0.5*(1+math.erf(z/math.sqrt(2)))
    return {'H': round(H,3), 'df': df, 'p': round(max(0,min(1,p)), 6)}

def mann_whitney(x, y):
    nx, ny = len(x), len(y)
    if nx < 2 or ny < 2: return None
    combined = [(v, 0) for v in x] + [(v, 1) for v in y]
    combined.sort(key=lambda t: t[0])
    ranks = {}
    i = 0
    while i < len(combined):
        j = i
        while j+1 < len(combined) and combined[j+1][0] == combined[i][0]: j += 1
        avg = (i + j + 2) / 2
        for k2 in range(i, j+1): ranks[combined[k2][0]] = avg
        i = j + 1
    R1 = sum(ranks[v] for v in x)
    U1 = R1 - nx*(nx+1)/2
    U = min(U1, nx*ny - U1)
    mu = nx*ny/2
    sigma = math.sqrt(nx*ny*(nx+ny+1)/12)
    if sigma == 0: return None
    z = (U - mu) / sigma
    p = 2 * (1 - 0.5*(1+math.erf(abs(z)/math.sqrt(2))))
    return {'U': round(U,1), 'z': round(z,3), 'p': round(max(0,min(1,p)),4)}

def cohens_d(x, y):
    nx, ny = len(x), len(y)
    if nx < 2 or ny < 2: return 0
    mx, my = sum(x)/nx, sum(y)/ny
    sx = math.sqrt(sum((v-mx)**2 for v in x)/(nx-1))
    sy = math.sqrt(sum((v-my)**2 for v in y)/(ny-1))
    pooled = math.sqrt(((nx-1)*sx**2+(ny-1)*sy**2)/max(nx+ny-2,1))
    return round((mx-my)/pooled, 3) if pooled > 0 else 0

def main():
    sources = [
        '/media/exuber/Elements/DataFlux/MechanogenesisBenchDEV/money_bench_v4',
        '/media/exuber/Elements/DataFlux/MechanogenesisBenchDEV/money_bench_v5',
    ]
    models = load_profits(sources)

    # Also from mb_results.txt
    txt = Path('/tmp/mb_results.txt')
    if txt.exists():
        for line in txt.read_text().strip().split('\n'):
            parts = line.strip().split('\t')
            if len(parts) >= 2:
                models[parts[0]].append(float(parts[1]))

    print(f"{'Model':20s} | {'n':>3s} | {'Mean':>8s} | {'Median':>8s} | {'SD':>7s}")
    print('-' * 60)
    sm = sorted(models.items(), key=lambda x: -statistics.mean(x[1]) if x[1] else 0)
    for name, p in sm:
        if len(p) < 2: continue
        print(f"{name:20s} | {len(p):3d} | {statistics.mean(p):+8.2f} | {statistics.median(p):+8.2f} | {statistics.stdev(p):7.2f}")

    groups = {k: v for k, v in models.items() if len(v) >= 3}
    if len(groups) >= 2:
        print(f"\nKruskal-Wallis H test:")
        kw = kruskal_wallis(groups)
        if kw:
            print(f"  H = {kw['H']}, df = {kw['df']}, p = {kw['p']}")
            if kw['p'] < 0.001: print("  → HIGHLY SIGNIFICANT ***")
            elif kw['p'] < 0.05: print("  → SIGNIFICANT *")
            else: print("  → NOT significant")

        names = list(groups.keys())
        n_pairs = len(names)*(len(names)-1)//2
        alpha = 0.05 / max(n_pairs, 1)
        print(f"\nPairwise Mann-Whitney (Bonferroni α={alpha:.4f}):")
        print(f"{'Pair':40s} | {'p':>8s} | {'d':>6s} | {'Sig':>4s}")
        print('-' * 70)
        for i in range(len(names)):
            for j in range(i+1, len(names)):
                x, y = groups[names[i]], groups[names[j]]
                mw = mann_whitney(x, y)
                if mw:
                    d = cohens_d(x, y)
                    sig = '***' if mw['p']<0.001 else ('**' if mw['p']<0.01 else ('*' if mw['p']<alpha else 'ns'))
                    print(f"{names[i][:18]:18s} vs {names[j][:18]:18s} | {mw['p']:8.4f} | {d:6.3f} | {sig:>4s}")

if __name__ == '__main__':
    main()
