#!/usr/bin/env python3
"""Flywheel turn 2: mine REAL judge feedback into memory-format improve examples."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from money_bench_v5 import SYSTEM

DEM = ["Build a phone dock for 78x12x160mm phone. Desk 420x280mm. From scratch.",
       "Customer upgraded to 90x14x175mm phone. Adapt the dock. MUST reuse the base from round 1.",
       "Add earbuds bay (65x48x28mm). MUST keep the adapted dock and add to it.",
       "Add tablet stand (250x10x175mm) behind. Combine all modules. MUST reuse dock+earbuds.",
       "Desk shrank to 300x200mm! Shrink but keep ALL functions. MUST optimize accumulated design."]
HERE = Path(__file__).resolve().parent.parent


def load_judge(sess):
    out = {}
    for jf in Path(sess).glob('judge_*_r*.json'):
        rd = int(jf.name.rsplit('_r', 1)[1].split('.')[0])
        try:
            d = json.loads(jf.read_text())
            inner = d.get('text', '') if isinstance(d.get('text'), str) else ''
            j = json.loads(inner)
            out[rd] = {'rating': j.get('rating', 0), 'feedback': (j.get('feedback') or '')[:120]}
        except Exception:
            pass
    return out


def round_design(sess, rd):
    for att in ('a0', 'a1'):
        f = Path(sess) / f'r{rd}_{att}' / f'r{rd}_{att}.json'
        if f.exists():
            t = json.loads(f.read_text()).get('text', '')
            if len(t) > 100:
                return t
    return None


def reused(text):
    try:
        return any(n.get('op') == 'capital' for n in json.loads(text).get('nodes', []))
    except Exception:
        return False


def mine(pairs):
    out = []
    for name, sess in pairs:
        judges = load_judge(sess)
        for tgt in range(1, 5):
            text = round_design(sess, tgt)
            if not text or not reused(text):
                continue
            if judges.get(tgt, {}).get('rating', 0) < 5:
                continue
            caps, ok = [], True
            for i in range(tgt):
                j = judges.get(i)
                if not j:
                    ok = False
                    break
                caps.append({'id': f'r{i+1}',
                             'desc': f"Round {i+1} design; rated {j['rating']}/10; feedback: {j['feedback']}"})
            if not ok:
                continue
            user = json.dumps({'demand': DEM[tgt], 'capital': caps,
                               'hint': 'Use capital(asset_id) to import previous modules.'}, ensure_ascii=False)
            assistant = text.replace('"h":', '"hypothesis":')
            out.append({'operator': 'improve-mem-real', 'round': tgt, 'designer': name,
                        'messages': [{'role': 'system', 'content': SYSTEM},
                                     {'role': 'user', 'content': user},
                                     {'role': 'assistant', 'content': assistant}]})
    return out


local = [(d.name, s) for d in sorted((HERE / 'runs' / 'local_bench').iterdir()) if d.is_dir()
         for s in sorted(d.glob('*/'))]
ssd = [('glm-5.3-flash/ssd', s) for s in sorted(
    Path('/media/exuber/Elements/DataFlux/MechanogenesisBenchDEV/money_bench_v5/glm-5.3-flash').glob('*/'))]
examples = mine(local) + mine(ssd)
seen, out = set(), []
for e in examples:
    k = e['messages'][1]['content'] + '||' + e['messages'][2]['content'][:300]
    if k in seen:
        continue
    seen.add(k)
    out.append(e)
(HERE / 'runs' / 'training_data' / 'sft_v3_memory_real.jsonl').write_text(
    '\n'.join(json.dumps(e, ensure_ascii=False) for e in out) + '\n')
print('real-feedback memory examples:', len(out))
