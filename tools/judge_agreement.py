#!/usr/bin/env python3
"""Cross-vendor judge consistency + family-bias analysis (no human eval needed).

Evidence base:
  A. multi-domain sessions: per-round raw judge outputs for 3 designers
     (FluxEidosV1.5, FluxEidosV2, mimo-v2.6-flash) x 2 domains x 3 judges
  B. standard-bench FluxEidosV2 (surpass v6+v7): stored mimo rating per round +
     glm-5.3 / glm-5.3-flash ratings from rejudge_cache.json on the final designs

Outputs: pairwise Spearman, Cohen's kappa (binned), Krippendorff's alpha (ordinal),
exact/sale-decision agreement, and a judge x designer family-bias matrix.
"""
import json, re, sys
from itertools import combinations
from pathlib import Path
from collections import defaultdict

import numpy as np
from scipy.stats import spearmanr, mannwhitneyu

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
BENCH = HERE.parent
MD = BENCH / 'runs' / 'multi_domain_v2'
OUT = BENCH / 'leaderboard' / 'data' / 'judge_agreement.json'

DESIGNER_LABEL = {'v15': 'FluxEidosV1.5', 'v2': 'FluxEidosV2', 'mimo-v2.6-flash': 'mimo-v2.6-flash'}
JUDGES = ['mimo-v2.6-pro', 'glm-5.3', 'glm-5.3-flash']
BINS = [0, 5, 7, 9, 11]  # 0-4 / 5-6 / 7-8 / 9-10


def parse_rating_file(p):
    try:
        t = json.loads(p.read_text())['text']
        i, j = t.find('{'), t.rfind('}')
        return int(json.loads(t[i:j + 1]).get('rating', 0))
    except Exception:
        return None


def cohen_kappa(a, b):
    a, b = np.asarray(a), np.asarray(b)
    po = (a == b).mean()
    cats = np.unique(np.concatenate([a, b]))
    pe = sum(((a == c).mean()) * ((b == c).mean()) for c in cats)
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


def krippendorff_alpha_ordinal(units):
    """units: list of rows (judges) x items; None = missing. Ordinal metric."""
    n_j, n_i = len(units), len(units[0])
    units = [[None if units[j][i] is None else units[j][i] for i in range(n_i)] for j in range(n_j)]
    values = sorted({v for row in units for v in row if v is not None})
    rank = {v: i + 1 for i, v in enumerate(values)}
    # distance between consecutive ranks
    gap = {}
    for a, b in zip(values, values[1:]):
        gap[(a, b)] = (rank[b] + rank[b - 1] - 1) if False else (rank[b] - 1 + rank[b]) / 2 - (rank[a] - 1 + rank[a]) / 2
    def dist(x, y):
        lo, hi = sorted([x, y])
        d = 0
        idx = values.index(lo)
        while values[idx] != hi:
            d += gap[(values[idx], values[idx + 1])]
            idx += 1
        return d ** 2
    D_o, units_used = 0.0, 0
    for i in range(n_i):
        obs = [units[j][i] for j in range(n_j) if units[j][i] is not None]
        if len(obs) < 2:
            continue
        m = len(obs)
        for x, y in combinations(obs, 2):
            D_o += dist(x, y)
        units_used += m
    n_u = units_used / n_j if False else None
    # simpler standard formulation
    pair_counts = 0
    D_o = 0.0
    for i in range(n_i):
        obs = [units[j][i] for j in range(n_j) if units[j][i] is not None]
        if len(obs) < 2:
            continue
        for x, y in combinations(obs, 2):
            D_o += dist(x, y)
        pair_counts += len(obs) * (len(obs) - 1)
    D_o /= pair_counts if pair_counts else 1
    # expected disagreement
    hist = defaultdict(int)
    total = 0
    for j in range(n_j):
        for i in range(n_i):
            if units[j][i] is not None:
                hist[units[j][i]] += 1
                total += 1
    D_e = 0.0
    for x in values:
        for y in values:
            D_e += (hist[x] / total) * (hist[y] / total) * dist(x, y) / 2
    return 1 - D_o / D_e if D_e else 1.0


def main():
    rows = []  # {designer, domain, source, round, judge -> rating}

    # ── A. multi-domain: parse judge output files ──
    for arm_dir in sorted(MD.iterdir()):
        if not arm_dir.is_dir():
            continue
        designer = DESIGNER_LABEL.get(arm_dir.name, arm_dir.name)
        for dom_dir in sorted(arm_dir.iterdir()):
            if not dom_dir.is_dir():
                continue
            for sess in sorted(dom_dir.glob('sess*')):
                # collect per round the three judges (t0 only; t1 is retry-after-zero)
                by_round = defaultdict(dict)
                for jd in sess.glob('j_*_t0'):
                    m = re.match(r'j_(.+)_t0', jd.name)
                    if not m:
                        continue
                    jname = m.group(1)
                    if jname not in JUDGES:
                        continue
                    for f in jd.glob('judge_*_r*.json'):
                        rd = int(re.search(r'_r(\d+)', f.name).group(1))
                        r = parse_rating_file(f)
                        if r is not None:
                            by_round[rd][jname] = r
                for rd, jr in sorted(by_round.items()):
                    if len(jr) == 3:
                        row = {'designer': designer, 'domain': dom_dir.name,
                               'source': 'multi_domain', 'round': rd}
                        row.update(jr)
                        rows.append(row)

    # ── B. standard bench V2: stored mimo + cached glm on final artifacts ──
    from rejudge_v2 import round_artifacts, RUNS as SURPASS
    cache = {tuple(json.loads(k)): v for k, v in
             json.loads((SURPASS / 'rejudge_cache.json').read_text()).items()}
    zeros = 0
    for tag in ('v6', 'v7'):
        runs = json.loads((SURPASS / f'{tag}_results.json').read_text())
        for i, run in enumerate(runs):
            sess_dir = SURPASS / tag / f'sess{i + 1}'
            for rr in run['rounds']:
                rd, rec = rr['rd'], rr['rating']
                txt, amb = round_artifacts(sess_dir, rd, rec)
                if txt is None:
                    continue
                # locate the artifact key whose text matches
                art = None
                for cand in sorted(sess_dir.glob(f'r{rd}_*')):
                    cj = cand / '_ji.json'
                    if cj.exists():
                        try:
                            if json.loads(cj.read_text())['text'] == txt:
                                art = cand.name
                                break
                        except Exception:
                            continue
                if art is None:
                    continue
                g1 = cache.get((tag, i, rd, art, 'glm-5.3'))
                g2 = cache.get((tag, i, rd, art, 'glm-5.3-flash'))
                if g1 is None or g2 is None:
                    continue
                if g1 == 0 or g2 == 0:
                    zeros += 1
                rows.append({'designer': 'FluxEidosV2', 'domain': 'workstation',
                             'source': f'surpass_{tag}', 'round': rd,
                             'mimo-v2.6-pro': rec, 'glm-5.3': g1, 'glm-5.3-flash': g2})

    print(f'parsed {len(rows)} fully-judged round-triples '
          f'(glm zeros in cache: {zeros})', flush=True)

    # ── consistency metrics ──
    res = {'n_triples': len(rows), 'by_source': {}, 'family_bias': {}}

    def consistency(subset, label):
        if len(subset) < 10:
            return
        R = {j: [r[j] for r in subset] for j in JUDGES}
        out = {'n': len(subset), 'pairwise': {}}
        for a, b in combinations(JUDGES, 2):
            rho, p = spearmanr(R[a], R[b])
            ba = np.digitize(R[a], BINS[1:-1])
            bb = np.digitize(R[b], BINS[1:-1])
            kap = cohen_kappa(ba, bb)
            sale_agree = ((np.array(R[a]) >= 5) == (np.array(R[b]) >= 5)).mean()
            out['pairwise'][f'{a}|{b}'] = {'spearman': round(float(rho), 3),
                                           'p': float(p), 'kappa_binned': round(float(kap), 3),
                                           'sale_agreement': round(float(sale_agree), 3)}
        out['krippendorff_alpha_ordinal'] = round(
            krippendorff_alpha_ordinal([[r[j] for r in subset] for j in JUDGES]), 3)
        out['exact_agreement'] = round(sum(1 for r in subset
                                           if len({r[j] for j in JUDGES}) == 1) / len(subset), 3)
        res['by_source'][label] = out
        print(f'[{label}] n={out["n"]} alpha={out["krippendorff_alpha_ordinal"]} '
              f'exact={out["exact_agreement"]}', flush=True)
        for k, v in out['pairwise'].items():
            print(f'   {k}: rho={v["spearman"]} kappa={v["kappa_binned"]} '
                  f'sale_agree={v["sale_agreement"]}', flush=True)

    consistency(rows, 'all')
    for src in sorted({r['source'] for r in rows}):
        consistency([r for r in rows if r['source'] == src], src)
    for designer in sorted({r['designer'] for r in rows}):
        consistency([r for r in rows if r['designer'] == designer], f'designer:{designer}')

    # ── family bias: judge x designer mean ratings ──
    designers = sorted({r['designer'] for r in rows})
    matrix = {j: {d: round(float(np.mean([r[j] for r in rows if r['designer'] == d])), 2)
                  for d in designers} for j in JUDGES}
    res['family_bias']['mean_rating_matrix'] = matrix
    # key test: does the mimo judge score mimo designs higher than FluxEidos designs,
    # relative to the glm judges' gap?  (judge gap-inflation)
    gaps = {}
    for j in JUDGES:
        mimo_des = [r[j] for r in rows if r['designer'] == 'mimo-v2.6-flash']
        ours = [r[j] for r in rows if r['designer'] in ('FluxEidosV1.5', 'FluxEidosV2')]
        u, p = mannwhitneyu(mimo_des, ours, alternative='greater')
        gaps[j] = {'mean_on_mimo': round(float(np.mean(mimo_des)), 2),
                   'mean_on_ours': round(float(np.mean(ours)), 2),
                   'gap': round(float(np.mean(mimo_des) - np.mean(ours)), 2),
                   'p_one_sided': round(float(p), 4), 'n_mimo': len(mimo_des), 'n_ours': len(ours)}
    res['family_bias']['judge_gaps'] = gaps
    print('\nfamily-bias (multi-domain cells):')
    print(json.dumps(matrix, indent=1))
    for j, g in gaps.items():
        print(f'  {j}: mimo-designs {g["mean_on_mimo"]} vs ours {g["mean_on_ours"]} '
              f'(gap {g["gap"]:+}, p={g["p_one_sided"]})')

    OUT.write_text(json.dumps(res, indent=2))
    (OUT.parent / 'judge_triples.json').write_text(json.dumps(rows, indent=2))
    print(f'\nsaved: {OUT}')


if __name__ == '__main__':
    main()
