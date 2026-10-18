#!/usr/bin/env python3
"""Robot-domain design judge: rate body designs for expected locomotion reliability.

Reads runs/robot_bench/pilot_designs.json (8-parameter numeric designs) and asks
the judge (mimo-v2.6-pro) for a 0-10 expected-reliability rating, 3 repeats per
design, at temperature 0.2. Saves runs/robot_bench/pilot_judge.json.
"""
import json, os, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

BENCH = Path(__file__).resolve().parent.parent
DESIGNS = BENCH / 'runs' / 'robot_bench' / 'pilot_designs.json'
OUT = BENCH / 'runs' / 'robot_bench' / 'pilot_judge.json'
MIMO_BASE = os.environ.get('MIMO_BASE_URL', 'https://token-plan-cn.xiaomimimo.com/v1')
REPS = 3
DEMAND = ('Walk forward at 0.10 m/s on flat ground for 30 s, upright, with low '
          'lateral drift and no falls.')
SYS = ('You are a legged-robot engineer. Given a body design (masses, centre of '
       'mass offset, joint range scales), rate its expected locomotion reliability '
       'for the demand 0-10. Return ONLY JSON: {"rating":<n>,"accepted":<bool>}')


def judge_once(design):
    import httpx
    key = os.environ.get('MIMO_KEY', 'none')
    prompt = f"Demand: {DEMAND}\nDesign: {json.dumps(design, ensure_ascii=False)}"
    for _ in range(3):
        try:
            with httpx.Client(timeout=httpx.Timeout(90, connect=10), trust_env=False) as c:
                r = c.post(f'{MIMO_BASE}/chat/completions',
                           headers={'Authorization': f'Bearer {key}'},
                           json={'model': 'mimo-v2.6-pro',
                                 'messages': [{'role': 'system', 'content': SYS},
                                              {'role': 'user', 'content': prompt}],
                                 'max_tokens': 256, 'temperature': 0.2})
            if r.status_code != 200:
                time.sleep(2); continue
            t = (r.json()['choices'][0]['message'].get('content') or '').strip()
            i, j = t.find('{'), t.rfind('}')
            return int(json.loads(t[i:j+1]).get('rating', 0))
        except Exception:
            time.sleep(2)
    return None


def main():
    designs = json.load(open(DESIGNS))
    tasks = [(i, rep) for i in range(len(designs)) for rep in range(REPS)]
    def work(t):
        i, rep = t
        return {'i': i, 'rep': rep, 'rating': judge_once(designs[i])}
    rows = []
    with ThreadPoolExecutor(max_workers=6) as ex:
        for r in ex.map(work, tasks):
            rows.append(r)
    json.dump({'designs': designs, 'rows': rows}, open(OUT, 'w'), indent=1)
    ok = [r for r in rows if r['rating'] is not None]
    print(f'judged {len(ok)}/{len(rows)} calls -> {OUT}')


if __name__ == '__main__':
    main()
