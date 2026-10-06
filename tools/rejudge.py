#!/usr/bin/env python3
"""Re-judge stored bench sessions with cross-vendor judges and recompute profit.

Addresses NMI reviewer concern #2 (single-judge ground truth): adds glm-5.3 and
glm-5.3-flash ratings on top of the stored mimo-v2.6-pro ratings, takes the
median-of-3, recomputes sold/speed-priced revenue/profit per session.

Usage (text-to-cad venv):
  python tools/rejudge.py --dir runs/local_bench/qwen9b-care-v3-it6 --tag care-v3-it6-3judge
"""
import argparse, json, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from money_bench_v5 import DEMANDS, speed_price, PRICE, ACCEPT
from openrsi_sft_v2 import anthropic_call, GLM_BASE, zai_key, extract_json

JUDGE_SYS = 'Rate the workstation design 0-10 for user satisfaction. Return ONLY JSON: {"rating":<n>,"accepted":<bool>,"feedback":"<t>"}'
EXTRA_JUDGES = [('glm-5.3', 16000), ('glm-5.3-flash', 4096)]


def judge_one(key, model, mt, demand, text):
    try:
        jt, _ = anthropic_call(GLM_BASE, key, model, JUDGE_SYS,
                               f'Demand: {demand}\nDesign: {text[:6000]}', mt, 0.2)
        return (extract_json(jt) or {}).get('rating', 0)
    except Exception:
        return 0


def stored_mimo_rating(sess, rd):
    f = sess / f'judge_mimo-v2.6-pro_r{rd}.json'
    if not f.exists():
        return None
    try:
        d = json.loads(f.read_text())
        inner = d.get('text', '') if isinstance(d.get('text'), str) else ''
        return json.loads(inner).get('rating', 0)
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', required=True, help='glob of session dirs, or a single dir')
    ap.add_argument('--tag', required=True)
    a = ap.parse_args()

    key = zai_key()
    base = Path(a.dir)
    sessions = sorted([p for p in base.iterdir() if p.is_dir() and
                        (p.name[:2].isdigit() or p.name.startswith('sess'))]) \
        if base.is_dir() and not any(base.glob('r0_a0')) else [base]

    out = []
    for sess in sessions:
        rounds, total = [], 0.0
        for rd in range(5):
            text = None
            for att in ('a0', 'a1'):
                base_att = sess / f'r{rd}_{att}'
                f = base_att / f'r{rd}_{att}.json'
                if not f.exists() and (base_att / '_ji.json').exists():  # jitrl layout
                    f = base_att / '_ji.json'
                if f.exists() and ((base_att / 'cad' / 'design.step').exists() or (base_att / 'design.step').exists()):
                    d = json.loads(f.read_text())
                    t = d.get('text') or d.get('design') or ''
                    if isinstance(t, str) and len(t) > 60:
                        text, secs = t, d.get('seconds', d.get('secs', 30))
                        break
            if text is None:
                rounds.append({'rd': rd, 'rating3': 0, 'sold': False, 'rev': 0})
                continue
            ratings = [stored_mimo_rating(sess, rd)]
            ratings += [judge_one(key, m, mt, DEMANDS[rd], text) for m, mt in EXTRA_JUDGES]
            ratings = sorted(r for r in ratings if r is not None)
            med = ratings[len(ratings)//2] if ratings else 0
            sold = med >= ACCEPT
            rev = round(PRICE * speed_price(secs)) if sold else 0
            total += rev
            rounds.append({'rd': rd, 'ratings': ratings, 'rating3': med, 'sold': sold, 'rev': rev})
            print(f"  {sess.name} R{rd+1}: {ratings} -> med {med} {'SOLD' if sold else ''}", flush=True)
        out.append({'session': sess.name, 'rounds': rounds, 'profit': round(total, 2),
                    'sold': f"{sum(1 for r in rounds if r['sold'])}/5"})

    res = Path(a.dir).parent / f'{a.tag}_rejudged.json'
    res.write_text(json.dumps(out, ensure_ascii=False, indent=2))
    profits = [r['profit'] for r in out]
    print(f"\n{a.tag}: n={len(out)} 3-judge profit mean={sum(profits)/len(profits):.0f} "
          f"runs={[round(p) for p in profits]} -> {res}")


if __name__ == '__main__':
    main()
