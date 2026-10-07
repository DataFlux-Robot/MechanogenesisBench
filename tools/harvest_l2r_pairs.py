#!/usr/bin/env python3
"""Harvest learning-to-rank pairs from dual-adapter experiment data.

Creates (winner, loser) pairs from same-context candidates where we know
CAD validity + judge rating. These train the CWM to do RELATIVE ranking
(not absolute prediction) — fixing the screening negative result.

Data sources:
  - runs/dual_adapter/screen4/sess*/  (4 candidates per round, with prediction + CAD)
  - runs/dual_adapter/control4/sess*/  (same structure)
"""
import json, glob, random
from pathlib import Path

HERE = Path(__file__).resolve().parent
BENCH = HERE.parent

pairs = []

# From dual-adapter runs: each round has 4 candidates stored, with judge result
for arm in ('screen4', 'control4'):
    for sess in sorted((BENCH / 'runs' / 'dual_adapter' / arm).glob('sess*')):
        for rd in range(5):
            # The selected candidate was CAD-evaluated and judged
            # We know its outcome from the results JSON
            results_f = BENCH / 'runs' / 'dual_adapter' / f'{arm}_results.json'
            if not results_f.exists(): continue
            # We need the actual candidate texts + their outcomes
            # From the bench run we have the r{rd}_best folder with the executed design
            best_dir = sess / f'r{rd}_best'
            ji = best_dir / '_ji.json'
            if not ji.exists(): continue
            try:
                executed = json.loads(ji.read_text())
            except: continue

            # Get the outcome from the log
            # We stored pred_rating for screened candidates
            # For now, just collect the design + any rating we can find
            design = executed.get('text', '')

            # For L2R we need at least 2 candidates from same context
            # The dual_adapter_bench generates 4 but only stores the selected one
            # We need to modify the bench to store all candidates for future runs
            pass

# Better source: the GAR-RL rollouts have 6 candidates per prompt with full scoring
# But those are being generated right now

# Alternative: use the world_model_pairs but create synthetic pairs
# Group by demand, sort by rating, create (high, low) pairs
wmp = json.loads((BENCH / 'runs' / 'training_data' / 'world_model_pairs.json').read_text())

from collections import defaultdict
by_demand = defaultdict(list)
for p in wmp:
    if p['valid']:
        by_demand[p['demand']].append(p)

RANK_SYS = '''You are a design quality judge. Given two workstation CSG designs for the same demand, output which is better. Return ONLY JSON: {"better": "<A|B>"}'''

for demand, items in by_demand.items():
    if len(items) < 2: continue
    # sort by rating descending
    items.sort(key=lambda x: -x['rating'])
    # create pairs: top vs bottom, adjacent pairs
    n_pairs = min(len(items) // 2, 5)  # up to 5 pairs per demand
    for i in range(n_pairs):
        winner = items[i]
        loser = items[-(i+1)]
        if winner['rating'] <= loser['rating']: continue  # need strict ordering

        user = json.dumps({
            'demand': demand,
            'design_A': winner['design'][:3000],
            'design_B': loser['design'][:3000],
            'note': 'Which design is better? A or B.'
        }, ensure_ascii=False)

        # Randomly swap A/B to avoid position bias
        if random.random() < 0.5:
            user = json.dumps({
                'demand': demand,
                'design_A': loser['design'][:3000],
                'design_B': winner['design'][:3000],
                'note': 'Which design is better? A or B.'
            }, ensure_ascii=False)
            answer = '{"better": "B"}'
        else:
            answer = '{"better": "A"}'

        pairs.append({
            'operator': 'l2r',
            'messages': [
                {'role': 'system', 'content': RANK_SYS},
                {'role': 'user', 'content': user},
                {'role': 'assistant', 'content': answer}
            ],
            'rating_diff': winner['rating'] - loser['rating']
        })

print(f"L2R pairs created: {len(pairs)}")
print(f"Rating gaps: min={min(p['rating_diff'] for p in pairs)}, max={max(p['rating_diff'] for p in pairs)}")

out = BENCH / 'runs' / 'training_data' / 'l2r_pairs.jsonl'
out.write_text('\n'.join(json.dumps(p, ensure_ascii=False) for p in pairs) + '\n')
print(f"saved -> {out}")
