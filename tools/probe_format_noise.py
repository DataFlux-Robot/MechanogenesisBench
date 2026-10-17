#!/usr/bin/env python3
"""P1 probe: decompose the judge channel's noise into retest variance (irreducible
sampling noise) and format sensitivity (nuisance variance a JEPA-style latent
evaluator could filter out).

Designs are taken from archived CARE-v4 eval sessions (valid CAD, known ratings).
For each design we build semantically identical variants:
  v0 original, v1 part renaming, v2 compact JSON + parts order reversed,
  v3 node-id renaming + hypothesis change + indent change.
Every variant is judged REPS times by the same judge (mimo-v2.6-pro, temp 0.2,
same prompt as training). Geometry facts are unchanged, so any rating variance
across v1-v3 is pure nuisance; within-variant variance across reps is retest noise.
"""
import json, os, random, re, statistics as st, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
BENCH = HERE.parent
EVAL = BENCH / 'runs' / 'local_model_eval'
OUT = BENCH / 'runs' / 'probes' / 'format_noise.json'
MIMO_BASE = os.environ.get('MIMO_BASE_URL', 'https://token-plan-cn.xiaomimimo.com/v1')
JUDGE_SYS = ('Rate the workstation design 0-10 for user satisfaction. Return ONLY '
             'JSON: {"rating":<n>,"accepted":<bool>,"feedback":"<t>"}')
DEMANDS = [
    "Build a phone dock for 78x12x160mm phone. Desk 420x280mm. From scratch.",
    "Customer upgraded to 90x14x175mm phone. Adapt the dock. MUST reuse the base from round 1.",
    "Add earbuds bay (65x48x28mm). MUST keep the adapted dock and add to it.",
    "Add tablet stand (250x10x175mm) behind. Combine all modules. MUST reuse dock+earbuds.",
    "Desk shrank to 300x200mm! Shrink but keep ALL functions. MUST optimize accumulated design.",
]
REPS = 3
N_DESIGNS = 12


def select_designs():
    """Archived valid designs with recorded ratings, spread over rounds and quality."""
    picks = []
    sess_dirs = sorted(EVAL.glob('care-v4b-it8_2*'))
    rng = random.Random(7)
    by_round = {0: [], 2: [], 4: []}
    for sess in sess_dirs:
        res = sess / 'result.json'
        if not res.exists():
            continue
        run = json.loads(res.read_text())
        for rr in run['rounds']:
            rd = rr['rd']
            if rd not in by_round or not rr.get('sold') and rr['rating'] == 0:
                continue
            if not rr.get('cad'):
                continue
            d = sess / f'r{rd}_a0' / 'cad'
            ji, jo = d / '_job_in.json', d / '_job_out.json'
            if not (ji.exists() and jo.exists()):
                continue
            try:
                if not json.loads(jo.read_text()).get('metrics'):
                    continue
                txt = json.loads(ji.read_text())['text']
                json.loads(txt)
            except Exception:
                continue
            by_round[rd].append({'rd': rd, 'sess': sess.name, 'text': txt,
                                 'metrics': json.loads(jo.read_text())['metrics'],
                                 'recorded': rr['rating']})
    for rd, lst in by_round.items():
        rng.shuffle(lst)
        picks.extend(lst[:N_DESIGNS // 3])
    return picks


def variants(text, idx):
    d = json.loads(text)
    out = {'v0': text}
    # v1: rename parts
    d1 = json.loads(text)
    for i, p in enumerate(d1.get('parts', [])):
        p['name'] = f'component_{chr(65+i)}'
    out['v1'] = json.dumps(d1, ensure_ascii=False, indent=1)
    # v2: compact JSON + reversed parts order
    d2 = json.loads(text)
    d2['parts'] = list(reversed(d2.get('parts', [])))
    out['v2'] = json.dumps(d2, ensure_ascii=False, separators=(',', ':'))
    # v3: rename node ids (stable map) + hypothesis change + indent
    d3 = json.loads(text)
    mp = {}
    for i, n in enumerate(d3.get('nodes', [])):
        old = n.get('id')
        new = f'n{i:02d}'
        if old:
            mp[old] = new
        if 'input' in n and n['input'] in mp:
            n['input'] = mp[n['input']]
        if 'asset_id' in n:
            pass
    for n in d3.get('nodes', []):
        if 'id' in n:
            n['id'] = mp.get(n['id'], n['id'])
        if 'inputs' in n:
            n['inputs'] = [mp.get(x, x) for x in n['inputs']]
        if 'input' in n:
            n['input'] = mp.get(n['input'], n['input'])
    for p in d3.get('parts', []):
        if 'node' in p:
            p['node'] = mp.get(p['node'], p['node'])
    d3['hypothesis'] = 'dock_variant_revision'
    out['v3'] = json.dumps(d3, ensure_ascii=False, indent=2)
    return out


def judge_once(demand, text, metrics):
    import httpx
    key = os.environ.get('MIMO_KEY', 'none')
    prompt = (f"Demand: {demand}\nDesign: {text[:6000]}\nCAD facts: "
              f"{json.dumps({'envelope_excess_mm': (metrics or {}).get('occupied_envelope_excess_mm'), 'overlap_mm3': (metrics or {}).get('overlap_mm3')})}")
    for _ in range(3):
        try:
            with httpx.Client(timeout=httpx.Timeout(120, connect=15), trust_env=False) as c:
                r = c.post(f'{MIMO_BASE}/chat/completions',
                           headers={'Authorization': f'Bearer {key}'},
                           json={'model': 'mimo-v2.6-pro',
                                 'messages': [{'role': 'system', 'content': JUDGE_SYS},
                                              {'role': 'user', 'content': prompt}],
                                 'max_tokens': 512, 'temperature': 0.2})
            if r.status_code != 200:
                time.sleep(2); continue
            t = (r.json()['choices'][0]['message'].get('content') or '').strip()
            if t.startswith('```'):
                t = t.split('\n', 1)[-1].rsplit('```', 1)[0].strip()
            i, j = t.find('{'), t.rfind('}')
            return int(json.loads(t[i:j+1]).get('rating', 0))
        except Exception:
            time.sleep(2)
    return None


def main():
    designs = select_designs()
    print(f'[select] {len(designs)} archived designs', flush=True)
    tasks = []
    for di, des in enumerate(designs):
        vs = variants(des['text'], di)
        for vname, vtext in vs.items():
            for rep in range(REPS):
                tasks.append((di, vname, rep, des['rd'], vtext, des['metrics']))
    print(f'[judge] {len(tasks)} calls ({N_DESIGNS} designs x 4 variants x {REPS} reps)', flush=True)

    def work(t):
        di, vname, rep, rd, vtext, metrics = t
        r = judge_once(DEMANDS[rd], vtext, metrics)
        return {'di': di, 'variant': vname, 'rep': rep, 'rd': rd, 'rating': r}

    t0 = time.time()
    rows = []
    with ThreadPoolExecutor(max_workers=6) as ex:
        for r in ex.map(work, tasks):
            rows.append(r)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({'designs': designs, 'rows': rows}, indent=1, ensure_ascii=False))
    print(f'[judge] done in {time.time()-t0:.0f}s -> {OUT}', flush=True)

    # ── decomposition ──
    ok = [r for r in rows if r['rating'] is not None]
    print(f'[stats] valid calls {len(ok)}/{len(rows)}')
    per = {}
    for r in ok:
        per.setdefault(r['di'], {}).setdefault(r['variant'], []).append(r['rating'])
    retest, format_sd, struct_sd = [], [], []
    flips = 0
    for di, vs in per.items():
        if len(vs) < 4 or any(len(x) < 2 for x in vs.values()):
            continue
        means = {v: st.mean(x) for v, x in vs.items()}
        within = st.mean([st.pstdev(x) for x in vs.values()])
        across_variants = st.pstdev([means[v] for v in ('v1', 'v2', 'v3')])  # nuisance only
        retest.append(within)
        format_sd.append(across_variants)
        # threshold-crossing flips caused purely by format
        sold0 = means['v0'] >= 5
        if any((means[v] >= 5) != sold0 for v in ('v1', 'v2', 'v3')):
            flips += 1
    print(f'[stats] retest sd (within variant): {st.mean(retest):.3f}  '
          f'(n={len(retest)})')
    print(f'[stats] format sd (across variants): {st.mean(format_sd):.3f}')
    print(f'[stats] designs where pure format flipped the sale decision: {flips}/{len(retest)}')
    var_ratio = (st.mean(format_sd) ** 2) / max(st.mean(retest) ** 2, 1e-9)
    print(f'[stats] format-variance / retest-variance = {var_ratio:.2f}x  '
          f'-> share of channel noise a perfect format-invariant filter could remove: '
          f'{var_ratio/(1+var_ratio)*100:.0f}%')


if __name__ == '__main__':
    main()
