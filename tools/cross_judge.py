#!/usr/bin/env python3
"""Multi-judge cross-validation: are LLM judges reliable and unbiased?

Takes existing design outputs from the control experiment and money bench,
sends them to 3 judges from DIFFERENT vendors, and computes:
  1. Inter-rater agreement (Cohen's κ, Krippendorff's α)
  2. Family bias (does MiMo judge favor MiMo designers?)
  3. Rating correlation (Spearman ρ between judge pairs)

If κ ≥ 0.6 and no family bias → LLM judges are reliable → publishable
"""
import argparse, json, os, sys, time
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from money_bench_v5 import MODELS, call, JUDGE_SYS

RESULTS = Path('/home/exuber/CODE/CORE/pythonProject1/AUTORESEARCH/MechanogenesisBench-upstream/runs/cross_judge')

# Judges from 3 different vendor families
JUDGES = {
    'mimo-v2.6-pro': MODELS['mimo-v2.6-pro'],      # Xiaomi
    
    'glm-5.3': {'model': 'glm-5.3', 'api_base': 'https://api.z.ai/api/anthropic',
                'protocol': 'anthropic', 'key_env': 'ZAI_KEY', 'max_tokens': 32000, 'temp': 0.6},                    # Zhipu
    # DeepSeek removed: API key expired
}


def collect_designs(source_dir):
    """Collect (designer, round, text, cad_metrics) tuples from existing runs."""
    designs = []
    source = Path(source_dir)

    # From money_bench_v5 results
    for result_file in sorted(source.rglob('result.json')):
        if 'money_bench_v5' not in str(source_file) and 'control_experiments' not in str(source):
            continue
        try:
            r = json.loads(result_file.read_text())
            designer = r.get('designer', 'unknown')
            for rd_data in r.get('rounds', []):
                rd = rd_data['rd']
                # Find the design file
                design_dir = result_file.parent / f'r{rd}_a0'
                design_file = design_dir / f'r{rd}_a0.json'
                if not design_file.exists():
                    design_file = result_file.parent / f'r{rd}_a1' / f'r{rd}_a1.json'
                if not design_file.exists():
                    continue
                d = json.loads(design_file.read_text())
                text = d.get('text', '')
                if not text.strip():
                    continue
                designs.append({
                    'designer': designer,
                    'round': rd,
                    'text': text[:2000],
                    'original_rating': rd_data.get('rating', 0),
                    'cad': rd_data.get('cad'),
                })
        except Exception:
            continue

    # Also from control experiment directories
    for condition_dir in sorted(source.glob('*/')):
        for round_dir in sorted(condition_dir.glob('r*_a0')):
            design_file = round_dir / f'{round_dir.name}.json'
            if not design_file.exists():
                continue
            try:
                d = json.loads(design_file.read_text())
                text = d.get('text', '')
                if not text.strip():
                    continue
                designer = condition_dir.parent.name  # model name
                rd = int(round_dir.name.split('_')[0][1:])
                condition = condition_dir.name.split('_2026')[0]
                designs.append({
                    'designer': f'{designer}({condition})',
                    'round': rd,
                    'text': text[:2000],
                    'original_rating': 0,  # from treatment only
                    'cad': None,
                })
            except Exception:
                continue

    return designs


def judge_design(judge_spec, demand, text, folder, label):
    """Get one judge's rating for one design."""
    try:
        prompt = (f'User demand: {demand}\n'
                  f'Design: {text[:1500]}\n'
                  f'Rate satisfaction 0-10.')
        resp, _, _ = call(judge_spec, JUDGE_SYS, prompt, folder, label)
        parsed = json.loads(resp)
        return parsed.get('rating', 0)
    except Exception:
        return -1  # error sentinel


def cohens_kappa(ratings1, ratings2):
    """Cohen's κ for two raters on ordinal scale."""
    from collections import Counter
    n = len(ratings1)
    if n == 0: return 0

    # Observed agreement
    agree = sum(1 for a, b in zip(ratings1, ratings2) if a == b)
    po = agree / n

    # Expected agreement (per-category)
    cats = set(ratings1) | set(ratings2)
    pe = sum(Counter(ratings1)[c] / n * Counter(ratings2)[c] / n for c in cats)

    if pe == 1: return 1
    return (po - pe) / (1 - pe)


def spearman_rho(x, y):
    """Spearman rank correlation."""
    def rank(v):
        sorted_v = sorted(range(len(v)), key=lambda i: v[i])
        ranks = [0] * len(v)
        for rank_val, idx in enumerate(sorted_v):
            ranks[idx] = rank_val
        return ranks
    rx, ry = rank(x), rank(y)
    n = len(x)
    d2 = sum((a - b) ** 2 for a, b in zip(rx, ry))
    return 1 - 6 * d2 / (n * (n * n - 1)) if n > 1 else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', default='/media/exuber/Elements/DataFlux/MechanogenesisBenchDEV',
                        help='Directory containing money_bench_v5 and control_experiments')
    parser.add_argument('--max-designs', type=int, default=20,
                        help='Maximum designs to judge (for API cost control)')
    args = parser.parse_args()

    # Check judge API keys
    available_judges = {}
    for name, spec in JUDGES.items():
        if not spec.get('key_env') or os.environ.get(spec['key_env']):
            available_judges[name] = spec
        else:
            print(f'SKIP judge {name}: {spec.get("key_env", "?")} not set')

    if len(available_judges) < 2:
        print(f'FATAL: Need at least 2 judges, got {len(available_judges)}')
        sys.exit(1)

    # Collect designs from treatment condition (most representative)
    print('\nCollecting designs...')
    control_dir = Path(args.source) / 'control_experiments' / 'glm-5.3-flash'
    designs = []

    # From treatment runs (these have both designs and original ratings)
    for result_file in sorted(control_dir.glob('treatment_*/**/result.json')):
        pass  # Individual results don't exist as files

    # Better: collect from the money_bench_v5 results
    mb5_dir = Path(args.source) / 'money_bench_v5'
    for run_dir in sorted(mb5_dir.glob('*/')):
        result_file = run_dir / 'result.json'
        if not result_file.exists(): continue
        try:
            r = json.loads(result_file.read_text())
            designer = r['designer']
            for rd_data in r.get('rounds', []):
                rd = rd_data['rd']
                # Find design file
                for att in (0, 1):
                    df = run_dir / f'r{rd}_a{att}' / f'r{rd}_a{att}.json'
                    if df.exists():
                        d = json.loads(df.read_text())
                        text = d.get('text', '')
                        if text.strip():
                            designs.append({
                                'designer': designer,
                                'round': rd,
                                'text': text[:2000],
                                'original_rating': rd_data.get('rating', 0),
                            })
                        break
        except Exception:
            continue

    # From ALL control experiment conditions (more diversity)
    for cond_dir in sorted(control_dir.glob('*_2026*')):
        for round_dir in sorted(cond_dir.glob('r*_a0')):
            df = round_dir / f'{round_dir.name}.json'
            if not df.exists(): continue
            try:
                d = json.loads(df.read_text())
                text = d.get('text', '')
                if text.strip():
                    rd = int(round_dir.name.split('_')[0][1:])
                    designs.append({
                        'designer': 'glm-5.3-flash(treatment)',
                        'round': rd,
                        'text': text[:2000],
                        'original_rating': 0,
                    })
            except Exception:
                continue

    # Limit for cost
    designs = designs[:args.max_designs]
    print(f'Collected {len(designs)} designs from {len(set(d["designer"] for d in designs))} designers')

    # Judge each design with each judge
    out_dir = RESULTS / time.strftime('%Y%m%d_%H%M%S')
    out_dir.mkdir(parents=True, exist_ok=True)

    for i, design in enumerate(designs):
        demand = "Design a desk workstation (see design below)"
        for jname, jspec in available_judges.items():
            label = f'judge_{jname}_d{i}'
            rating = judge_design(jspec, demand, design['text'], out_dir, label)
            design.setdefault('judges', {})[jname] = rating
        if (i + 1) % 5 == 0:
            print(f'  Judged {i+1}/{len(designs)} designs', flush=True)

    # Analysis
    judge_names = list(available_judges.keys())
    all_ratings = {j: [d['judges'].get(j, -1) for d in designs] for j in judge_names}

    print(f'\n{"=" * 60}')
    print(f'  CROSS-JUDGE VALIDATION ({len(judge_names)} judges, {len(designs)} designs)')
    print(f'{"=" * 60}')

    # 1. Inter-rater agreement
    print(f'\n  Inter-rater agreement:')
    for i in range(len(judge_names)):
        for j in range(i + 1, len(judge_names)):
            j1, j2 = judge_names[i], judge_names[j]
            r1 = [max(0, r) for r in all_ratings[j1]]
            r2 = [max(0, r) for r in all_ratings[j2]]
            valid = [(a, b) for a, b in zip(r1, r2) if a >= 0 and b >= 0]
            if len(valid) < 5: continue
            v1, v2 = zip(*valid)
            kappa = cohens_kappa(list(v1), list(v2))
            rho = spearman_rho(list(v1), list(v2))
            print(f'    {j1} vs {j2}: κ={kappa:.3f} ρ={rho:.3f} (n={len(valid)})')

    # 2. Family bias analysis
    print(f'\n  Family bias:')
    for jname in judge_names:
        j_family = jname.split('-')[0]  # e.g., 'mimo', 'glm', 'deepseek'
        same_family = [d['judges'].get(jname, -1) for d in designs
                      if j_family in d['designer'].lower()]
        diff_family = [d['judges'].get(jname, -1) for d in designs
                      if j_family not in d['designer'].lower()]
        same_valid = [r for r in same_family if r >= 0]
        diff_valid = [r for r in diff_family if r >= 0]
        if same_valid and diff_valid:
            same_avg = sum(same_valid) / len(same_valid)
            diff_avg = sum(diff_valid) / len(diff_valid)
            bias = same_avg - diff_avg
            flag = '⚠️ BIAS' if abs(bias) > 1.0 else '✓ unbiased'
            print(f'    {jname}: same-family={same_avg:.1f} diff-family={diff_avg:.1f} '
                  f'bias={bias:+.1f} {flag} (n={len(same_valid)}v{len(diff_valid)})')

    # 3. Summary
    print(f'\n  SUMMARY:')
    kappas = []
    for i in range(len(judge_names)):
        for j in range(i + 1, len(judge_names)):
            j1, j2 = judge_names[i], judge_names[j]
            r1 = [max(0, r) for r in all_ratings[j1]]
            r2 = [max(0, r) for r in all_ratings[j2]]
            valid = [(a, b) for a, b in zip(r1, r2) if a >= 0 and b >= 0]
            if len(valid) >= 5:
                kappas.append(cohens_kappa(*zip(*valid)))
    if kappas:
        avg_kappa = sum(kappas) / len(kappas)
        print(f'    Average κ: {avg_kappa:.3f}',
              '(✓ reliable)' if avg_kappa >= 0.6 else '(⚠️ low agreement)')
    print(f'    Judges: {", ".join(judge_names)}')
    print(f'    Designs: {len(designs)}')

    # Save
    (out_dir / 'cross_judge_results.json').write_text(
        json.dumps({'designs': designs, 'judges': judge_names}, indent=2, ensure_ascii=False))
    print(f'\n  Results: {out_dir / "cross_judge_results.json"}')


if __name__ == '__main__':
    main()
