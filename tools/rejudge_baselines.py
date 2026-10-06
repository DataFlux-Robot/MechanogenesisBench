#!/usr/bin/env python3
"""Symmetric 3-judge recompute for the four commercial baselines.

Reads all_trajectories.json (260 rounds with texts + stored mimo ratings),
adds glm-5.3 and glm-5.3-flash ratings, takes median-of-3, recomputes
per-session profit under the same speed pricing.
"""
import json, sys, time
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from money_bench_v5 import DEMANDS, speed_price, PRICE, ACCEPT
from openrsi_sft_v2 import anthropic_call, GLM_BASE, zai_key, extract_json

JUDGE_SYS = 'Rate the workstation design 0-10 for user satisfaction. Return ONLY JSON: {"rating":<n>,"accepted":<bool>,"feedback":"<t>"}'
OUT = HERE.parent / 'runs' / 'rsi_night'


def main():
    key = zai_key()
    data = json.loads((HERE.parent / 'runs' / 'training_data' / 'all_trajectories.json').read_text())
    streams = defaultdict(list)
    for d in data:
        streams[d['designer']].append(d)

    results = {}
    for designer, items in streams.items():
        sessions, cur = [], None
        for d in items:
            if d['round'] == 0:
                if cur: sessions.append(cur)
                cur = []
            if cur is not None: cur.append(d)
        if cur: sessions.append(cur)
        sess_stats = []
        t_start = time.time()
        for si, s in enumerate([x for x in sessions if len(x) == 5]):
            total = 0.0
            for r in s:
                text = r['text']
                if '"h":' in text and '"hypothesis":' not in text:
                    text = text.replace('"h":', '"hypothesis":')
                ratings = [r.get('rating', 0)]
                for model, mt in (('glm-5.3', 16000), ('glm-5.3-flash', 4096)):
                    for attempt in range(2):
                        try:
                            jt, _ = anthropic_call(GLM_BASE, key, model, JUDGE_SYS,
                                                   f"Demand: {DEMANDS[r['round']]}\nDesign: {text[:6000]}", mt, 0.2)
                            rating = (extract_json(jt) or {}).get('rating', 0)
                            if rating: break
                        except Exception:
                            time.sleep(3); rating = 0
                    ratings.append(rating)
                ratings = sorted(ratings)
                med = ratings[len(ratings)//2]
                if med >= ACCEPT:
                    total += round(PRICE * speed_price(r.get('secs', 30)))
            sess_stats.append(total)
            el = time.time() - t_start
            print(f"{designer} session {si+1}: 3-judge profit {total:.0f} ({el:.0f}s elapsed)", flush=True)
        results[designer] = sess_stats
        (OUT / 'baseline_rejudge.json').write_text(json.dumps(results, indent=2))
        print(f"== {designer}: n={len(sess_stats)} mean={sum(sess_stats)/len(sess_stats):.0f} "
              f"runs={[round(x) for x in sess_stats]}", flush=True)


if __name__ == '__main__':
    main()
