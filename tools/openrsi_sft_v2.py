#!/usr/bin/env python3
"""OpenRSI-style SFT v2: four-operator data pipeline (Draft/Improve/Debug/Crossover).

Follows Frontis-MA1 (arXiv:2607.28568) execution-grounded data gates:
  DRAFT     round-0 design, sold, median rating >= 6
  IMPROVE   round>=1, actually reused capital, sold, revenue > session round-0
  DEBUG     broken design + real CAD error -> repaired design that passes CAD
  CROSSOVER two sold parents (same demand, different designers) -> merged child
            that passes CAD and judges >= stronger parent

All examples carry the exact money_bench_v5 message format so training matches eval.

Usage (run with text-to-cad venv + PYTHONPATH, see run_openrsi_v2.sh):
  python tools/openrsi_sft_v2.py core
  python tools/openrsi_sft_v2.py debug   [--limit N]
  python tools/openrsi_sft_v2.py crossover [--limit N]
  python tools/openrsi_sft_v2.py merge
"""
import argparse, json, os, sys, time, random
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from money_bench_v5 import (SYSTEM, DEMANDS, real_cad_eval, anthropic_call)

ROOT = HERE.parent
TRAJ = ROOT / 'runs' / 'training_data' / 'all_trajectories.json'
OUT = ROOT / 'runs' / 'training_data'
OUT.mkdir(parents=True, exist_ok=True)

GLM_BASE = 'https://api.z.ai/api/anthropic'


def zai_key():
    cfg = json.loads(Path(os.path.expanduser('~/.config/fluxkernel/model.json')).read_text())
    return cfg.get('api_key') or ''


def fix_h(text):
    """Training data v1 contained the wrong key; normalize to the schema the evaluator expects."""
    return text.replace('"h":', '"hypothesis":')


def user_msg(rd, capital_ids):
    capital = [{'id': k, 'desc': f'Round {k[1:]} design'} for k in capital_ids]
    return json.dumps({'demand': DEMANDS[rd], 'capital': capital,
                       'hint': 'Use capital(asset_id) to import previous modules.' if capital else None})


def sessions_from_trajectories():
    data = json.loads(TRAJ.read_text())
    streams = defaultdict(list)
    for d in data:
        streams[d['designer']].append(d)
    sessions = []
    for designer, items in streams.items():
        cur = None
        for d in items:
            if d['round'] == 0:
                if cur: sessions.append(cur)
                cur = []
            if cur is not None:
                d = dict(d)
                d['text'] = fix_h(d['text'])
                cur.append(d)
        if cur: sessions.append(cur)
    return sessions


# ── core: Draft + Improve gates ──
def cmd_core():
    sessions = sessions_from_trajectories()
    examples = []
    n_draft = n_imp = 0
    for s in sessions:
        if len(s) != 5: continue
        r0 = s[0]
        # DRAFT: sold + rating >= 6 (OpenRSI: "Draft endpoints require a positive score")
        if r0['sold'] and r0['rating'] >= 6:
            examples.append({'operator': 'draft', 'round': 0, 'designer': r0['designer'],
                             'messages': [{'role': 'system', 'content': SYSTEM},
                                          {'role': 'user', 'content': user_msg(0, [])},
                                          {'role': 'assistant', 'content': r0['text'].strip()}]})
            n_draft += 1
        # IMPROVE: reused capital + sold + beat round-0 revenue ("Improve must beat parent")
        for r in s[1:]:
            if r['reused'] and r['sold'] and r['revenue'] > r0['revenue']:
                capital_ids = [f'r{i+1}' for i in range(r['round'])]
                examples.append({'operator': 'improve', 'round': r['round'], 'designer': r['designer'],
                                 'messages': [{'role': 'system', 'content': SYSTEM},
                                              {'role': 'user', 'content': user_msg(r['round'], capital_ids)},
                                              {'role': 'assistant', 'content': r['text'].strip()}]})
                n_imp += 1
    (OUT / 'sft_v2_core.jsonl').write_text(
        '\n'.join(json.dumps(e, ensure_ascii=False) for e in examples) + '\n')
    print(f'core: draft={n_draft} improve={n_imp} total={len(examples)} -> sft_v2_core.jsonl')


# ── debug: mine real failures, generate repairs, CAD-validate ──
DEBUG_SYS = SYSTEM + '\nYou are repairing a broken design. Fix ONLY the reported errors; keep working parts.'


def session_dirs():
    """Money Bench v5 session folders with r{k}_a{att} subfolders (SSD + local)."""
    roots = [Path('/media/exuber/Elements/DataFlux/MechanogenesisBenchDEV/money_bench_v5'),
             ROOT / 'runs' / 'control_experiments']
    out = []
    for base in roots:
        if not base.exists(): continue
        for model_dir in sorted(base.iterdir()):
            if not model_dir.is_dir(): continue
            for sess in sorted(model_dir.iterdir()):
                if sess.is_dir() and any(sess.glob('r*_a*')):
                    out.append((f'{model_dir.name}/{sess.name.split("_")[0]}', sess))
    return out


def rebuild_capital(sess_dir, upto_round):
    """Rebuild the capital dict from successful prior rounds' STEP files."""
    capital = {}
    for rd in range(upto_round):
        for att in ('a0', 'a1'):
            step = sess_dir / f'r{rd}_{att}' / 'cad' / 'design.step'
            if step.exists():
                capital[f'r{rd+1}'] = {'status': 'EXECUTED_CAD', 'step_path': str(step),
                                       'description': f'Round {rd+1} design', 'measurements': {}}
                break
    return capital


def cmd_debug(limit):
    key = zai_key()
    random.seed(41)
    examples, mined, repaired = [], 0, 0
    workdir = OUT / 'debug_gen'; workdir.mkdir(exist_ok=True)
    for designer, sess in session_dirs():
        if limit and len(examples) >= limit: break
        for att_dir in sorted(sess.glob('r*_a*')):
            if limit and len(examples) >= limit: break
            rd = int(att_dir.name.split('_')[0][1:])
            resp = att_dir / f'{att_dir.name}.json'
            if not resp.exists() or (att_dir / 'cad' / 'design.step').exists():
                continue  # success or no raw text — not a failure
            raw = json.loads(resp.read_text())
            broken = fix_h(raw.get('text', '')).strip()
            if not broken or len(broken) < 40: continue
            capital = rebuild_capital(sess, rd)
            tag = f'{designer.replace("/", "_")}_{sess.name}_{att_dir.name}'
            res = real_cad_eval(broken, capital, workdir / 'recheck' / tag)
            if res.get('metrics'):
                continue  # not actually broken (judge-only failure) — skip
            mined += 1
            err = res['error']
            prompt = json.dumps({'demand': DEMANDS[rd],
                                 'capital': [{'id': k, 'desc': v['description']} for k, v in capital.items()],
                                 'broken_design': broken[:6000],
                                 'error': err,
                                 'hint': 'Repair the broken design JSON so it passes validation. Return ONLY the fixed JSON.'},
                                ensure_ascii=False)
            try:
                fixed, _ = anthropic_call(GLM_BASE, key, 'glm-5.3', DEBUG_SYS, prompt, 16000, 0.3)
            except Exception as e:
                print(f'  glm call failed: {str(e)[:80]}'); continue
            fixed = fix_h(fixed.strip())
            chk = workdir / tag; chk.mkdir(parents=True, exist_ok=True)
            vres = real_cad_eval(fixed, capital, chk / 'cad')
            if vres.get('metrics'):
                examples.append({'operator': 'debug', 'round': rd, 'designer': designer,
                                 'messages': [{'role': 'system', 'content': DEBUG_SYS},
                                              {'role': 'user', 'content': prompt},
                                              {'role': 'assistant', 'content': fixed}]})
                repaired += 1
                print(f'  ✅ debug {tag} repaired ({repaired})')
            else:
                print(f'  ❌ debug {tag} still broken: {vres.get("error","")[:60]}')
    (OUT / 'sft_v2_debug.jsonl').write_text(
        '\n'.join(json.dumps(e, ensure_ascii=False) for e in examples) + '\n')
    print(f'debug: mined={mined} repaired={repaired} -> sft_v2_debug.jsonl')


# ── crossover: merge two sold parents, child must beat stronger parent ──
XOVER_SYS = SYSTEM + '\nYou are merging two parent designs for the same demand. Combine the best structure of both; the result must be valid JSON and satisfy the demand better than either parent.'
JUDGE_SYS = 'Rate the workstation design 0-10 for user satisfaction. Return ONLY JSON: {"rating":<n>,"accepted":<bool>,"feedback":"<t>"}'


def extract_json(s):
    """Pull the first valid JSON object out of a model response (fences/prose tolerant)."""
    if not s: return None
    clean = s.strip()
    if clean.startswith('```'):
        clean = clean.split('\n', 1)[-1].rsplit('```', 1)[0].strip()
    try:
        return json.loads(clean)
    except Exception:
        pass
    i, j = clean.find('{'), clean.rfind('}')
    if i >= 0 and j > i:
        try:
            return json.loads(clean[i:j+1])
        except Exception:
            return None
    return None


def cmd_crossover(limit):
    key = zai_key()
    random.seed(42)
    sessions = [s for s in sessions_from_trajectories() if len(s) == 5]
    # round-0 sold designs with rating >= 6, grouped by nothing (same demand across sessions)
    pool = [(s[0]['designer'], s[0]['text'], s[0]['rating']) for s in sessions
            if s[0]['sold'] and s[0]['rating'] >= 6]
    print(f'parent pool: {len(pool)} round-0 designs')
    workdir = OUT / 'xover_gen'; workdir.mkdir(exist_ok=True)
    examples, attempts = 0, 0
    pairs = []
    by_designer = defaultdict(list)
    for d, t, r in pool:
        by_designer[d].append((t, r))
    designers = sorted(by_designer)
    for i, da in enumerate(designers):
        for db in designers[i+1:]:
            for (ta, ra) in by_designer[da]:
                for (tb, rb) in by_designer[db]:
                    pairs.append((da, ta, ra, db, tb, rb))
    random.shuffle(pairs)
    for (da, ta, ra, db, tb, rb) in pairs:
        if limit and attempts >= limit: break
        attempts += 1
        prompt = json.dumps({'demand': DEMANDS[0], 'capital': [],
                             'parent_A': fix_h(ta)[:6000], 'parent_B': fix_h(tb)[:6000],
                             'hint': 'Merge both parents into one design better than either. Return ONLY the merged JSON.'},
                            ensure_ascii=False)
        try:
            child, _ = anthropic_call(GLM_BASE, key, 'glm-5.3', XOVER_SYS, prompt, 16000, 0.3)
        except Exception as e:
            print(f'  glm call failed: {str(e)[:80]}'); continue
        child = fix_h(child.strip())
        cj = extract_json(child)
        if cj is not None:
            child = json.dumps(cj, ensure_ascii=False)
        chk = workdir / f'x{attempts:03d}'; chk.mkdir(parents=True, exist_ok=True)
        vres = real_cad_eval(child, {}, chk / 'cad')
        if not vres.get('metrics'):
            # one repair round with the real CAD error (same loop as the bench itself)
            repair_prompt = prompt + f'\nPrevious merge failed validation: {vres.get("error","")}\nReturn the corrected JSON only.'
            try:
                child, _ = anthropic_call(GLM_BASE, key, 'glm-5.3', XOVER_SYS, repair_prompt, 16000, 0.3)
                child = fix_h(child.strip())
                cj = extract_json(child)
                if cj is not None:
                    child = json.dumps(cj, ensure_ascii=False)
                vres = real_cad_eval(child, {}, chk / 'cad2')
            except Exception as e:
                print(f'  repair call failed: {str(e)[:80]}'); continue
        if not vres.get('metrics'):
            print(f'  ❌ xover {attempts}: invalid CAD {vres.get("error","")[:60]}'); continue
        # judge gate: child must rate >= max(parents)
        try:
            jt, _ = anthropic_call(GLM_BASE, key, 'glm-5.3-flash', JUDGE_SYS,
                                   f'Demand: {DEMANDS[0]}\nDesign: {child[:6000]}', 4096, 0.2)
            rating = (extract_json(jt) or {}).get('rating', 0)
        except Exception:
            rating = 0
        gate = max(ra, rb)
        if rating >= gate and rating >= 6:
            examples += 1
            (OUT / 'sft_v2_crossover.jsonl').open('a').write(json.dumps(
                {'operator': 'crossover', 'round': 0, 'designer': f'{da}+{db}',
                 'messages': [{'role': 'system', 'content': XOVER_SYS},
                              {'role': 'user', 'content': prompt},
                              {'role': 'assistant', 'content': child}]}, ensure_ascii=False) + '\n')
            print(f'  ✅ xover {attempts}: child {rating} >= parents {ra}/{rb} ({examples})')
        else:
            print(f'  ❌ xover {attempts}: child {rating} < gate {gate}')
    print(f'crossover: attempts={attempts} kept={examples} -> sft_v2_crossover.jsonl')


# ── merge: dedup + finalize ──
def cmd_merge():
    all_ex, seen = [], set()
    for part in ('core', 'debug', 'crossover'):
        f = OUT / f'sft_v2_{part}.jsonl'
        if not f.exists(): continue
        for line in f.read_text().splitlines():
            if not line.strip(): continue
            e = json.loads(line)
            key = e['messages'][-1]['content']
            if key in seen: continue
            seen.add(key)
            all_ex.append(e)
    random.seed(7); random.shuffle(all_ex)
    (OUT / 'sft_v2_train.jsonl').write_text(
        '\n'.join(json.dumps(e, ensure_ascii=False) for e in all_ex) + '\n')
    from collections import Counter
    print(f'merge: {len(all_ex)} examples -> sft_v2_train.jsonl')
    print('operators:', dict(Counter(e['operator'] for e in all_ex)))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['core', 'debug', 'crossover', 'merge'])
    ap.add_argument('--limit', type=int, default=0)
    a = ap.parse_args()
    {'core': cmd_core, 'debug': lambda: cmd_debug(a.limit),
     'crossover': lambda: cmd_crossover(a.limit), 'merge': cmd_merge}[a.cmd]()
