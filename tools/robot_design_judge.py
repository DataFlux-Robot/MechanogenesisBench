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
DESIGNS = Path(os.environ.get('ROBOT_DESIGNS', str(BENCH / 'runs' / 'robot_bench' / 'pilot_designs.json')))
OUT = Path(os.environ.get('ROBOT_JUDGE_OUT', str(BENCH / 'runs' / 'robot_bench' / 'pilot_judge.json')))
MIMO_BASE = os.environ.get('MIMO_BASE_URL', 'https://token-plan-cn.xiaomimimo.com/v1')
REPS = 3
DEMAND = json.loads(os.environ.get('ROBOT_DEMAND', 'null')) or {
    'name': 'forward_010', 'vx': 0.10, 'yaw': 0.0,
    'text': 'Walk forward at 0.10 m/s on flat ground for 30 s.'}
DEMAND_TEXT = DEMAND.get('text', str(DEMAND))
SYS = ('You are a legged-robot engineer reviewing a body design before a 30 s '
       'locomotion trial. The design is given as mass scales, a centre-of-mass '
       'x offset (m), and joint range scales. Use this rubric:\n'
       '0-2: likely falls or cannot produce the commanded motion\n'
       '3-5: marginal; may walk but fails tracking or drifts\n'
       '6-8: likely passes with reasonable margin\n'
       '9-10: excellent stability and tracking margin\n'
       'Consider mass distribution, COM offset, and whether the range changes '
       'clip the nominal posture. Return ONLY JSON: '
       '{"rating":<n>,"accepted":<bool>,"why":"<one line>"}')


def judge_once(design):
    import httpx
    key = os.environ.get('MIMO_KEY', 'none')
    prompt = f"Demand: {DEMAND_TEXT}\nDesign: {json.dumps(design, ensure_ascii=False)}"
    for _ in range(3):
        try:
            with httpx.Client(timeout=httpx.Timeout(90, connect=10), trust_env=False) as c:
                r = c.post(f'{MIMO_BASE}/chat/completions',
                           headers={'Authorization': f'Bearer {key}'},
                           json={'model': 'mimo-v2.6-pro',
                                 'messages': [{'role': 'system', 'content': SYS},
                                              {'role': 'user', 'content': prompt}],
                                 'max_tokens': 256, 'temperature': 0.5})
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
