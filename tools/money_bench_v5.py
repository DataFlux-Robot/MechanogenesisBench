#!/usr/bin/env python3
"""PRSI Money Bench v5 — real build123d CAD + multi-LLM judges.

Key upgrades from v4:
  - Real geometry: build123d B-rep build → STEP export → re-import → precise intersection volumes
  - Real capital: exported STEP files accumulate as importable assets across rounds
  - Multi-judge: 3 LLMs from different vendors independently score each design
  - Designed to run with text-to-cad venv (build123d 0.11.1)

Usage (must use text-to-cad venv for build123d):
  /path/to/text-to-cad/.venv/bin/python tools/money_bench_v5.py \
      --designer glm-5.3-flash --judge mimo-v2.6-pro
"""
import argparse, json, os, sys, time
from pathlib import Path

# ── Direct build123d imports (text-to-cad venv: build123d + httpx + litellm) ──
DEV_SRC = Path('/home/exuber/CODE/CORE/pythonProject1/AUTORESEARCH/MechanogenesisBenchDEV/src')
sys.path.insert(0, str(DEV_SRC))
from oura_prsi_next.workstation_cad import validate_design, make_assembly, measure_export
from oura_prsi_next.workstation_rsi import occupied_geometry_metrics
from build123d import export_step

RESULTS = Path('/media/exuber/Elements/DataFlux/MechanogenesisBenchDEV/money_bench_v5')
PRICE = 100; ACCEPT = 5; TOKEN_PRICE = 0.008 / 1000

def speed_price(secs):
    if secs < 10: return 1.5
    if secs < 30: return 1.2
    if secs < 60: return 1.0
    if secs < 120: return 0.8
    return 0.5

MODELS = {
    'glm-5.2': {'model': 'glm-5.2', 'api_base': 'https://api.z.ai/api/anthropic',
               'protocol': 'anthropic', 'key_env': 'ZAI_KEY', 'max_tokens': 32000, 'temp': 0.6},
    'glm-5.1': {'model': 'glm-5.1', 'api_base': 'https://api.z.ai/api/anthropic',
               'protocol': 'anthropic', 'key_env': 'ZAI_KEY', 'max_tokens': 32000, 'temp': 0.6},
    'glm-5.3': {'model': 'glm-5.3', 'api_base': 'https://api.z.ai/api/anthropic',
               'protocol': 'anthropic', 'key_env': 'ZAI_KEY', 'max_tokens': 32000, 'temp': 0.6},
    'glm-5.3-flash': {'model': 'glm-5.3-flash', 'api_base': 'https://api.z.ai/api/anthropic',
                       'protocol': 'anthropic', 'key_env': 'ZAI_KEY', 'max_tokens': 16000, 'temp': 0.3},
    'mimo-v2.6-flash': {'model': 'openai/mimo-v2.6-flash', 'api_base': 'https://api.xiaomimimo.com/v1',
                        'protocol': 'openai', 'key_env': 'MIMO_KEY', 'max_tokens': 32000, 'temp': 0.6},
    'mimo-v2.6-pro': {'model': 'openai/mimo-v2.6-pro', 'api_base': 'https://api.xiaomimimo.com/v1',
                      'protocol': 'openai', 'key_env': 'MIMO_KEY', 'max_tokens': 32000, 'temp': 0.6},
    'deepseek-v3': {'model': 'openai/deepseek-chat', 'api_base': 'https://api.deepseek.com/v1',
                     'protocol': 'openai', 'key_env': 'DEEPSEEK_API_KEY', 'max_tokens': 16000, 'temp': 0.3},
    'deepseek-flash': {'model': 'openai/deepseek-flash', 'api_base': 'https://api.deepseek.com/v1',
                       'protocol': 'openai', 'key_env': 'DEEPSEEK_API_KEY', 'max_tokens': 8000, 'temp': 0.3},
    'deepseek-v4-pro': {'model': 'deepseek-v4-pro', 'api_base': 'https://api.deepseek.com/v1',
                        'protocol': 'openai-stream', 'key_env': 'DEEPSEEK_API_KEY',
                        'max_tokens': 16000, 'temp': 0.3},
}


def openai_stream_call(base, key, model, sys_, user, mt, tp):
    """OpenAI-compatible streaming (long non-stream requests get cut mid-connection)."""
    import httpx
    content = ''
    with httpx.Client(timeout=httpx.Timeout(900, connect=30), trust_env=False) as c:
        with c.stream('POST', base.rstrip('/') + '/chat/completions',
                      headers={'Authorization': f'Bearer {key}'},
                      json={'model': model,
                            'messages': [{'role': 'system', 'content': sys_},
                                         {'role': 'user', 'content': user}],
                            'max_tokens': mt, 'temperature': tp, 'stream': True}) as r:
            if r.status_code != 200:
                raise RuntimeError(f'HTTP {r.status_code}')
            for line in r.iter_lines():
                if not line.startswith('data:'):
                    continue
                d = line[5:].strip()
                if d == '[DONE]':
                    break
                try:
                    delta = json.loads(d)['choices'][0].get('delta', {})
                    content += delta.get('content') or ''
                except Exception:
                    pass
    return content

SYSTEM = '''Design a desk workstation. Return ONLY JSON with schema="workstation-csg/1".
Ops: box(size), cylinder(radius,height), union(inputs), difference(inputs), transform(input,xyz,rpy), capital(asset_id).
capital(asset_id) imports a PREVIOUSLY BUILT module from the capital list — it's FREE and FASTER than rebuilding.
If capital modules exist, USE THEM via capital nodes.
Parts: {"name","node","role(frame|module|tooling)","xyz","rpy"}. Max 64 nodes, 16 parts. mm, XY desk.
Example: {"schema":"workstation-csg/1","hypothesis":"reused+new","nodes":[{"id":"old","op":"capital","asset_id":"r1"},{"id":"n","op":"box","size":[60,40,40]},{"id":"u","op":"union","inputs":["old","n"]}],"parts":[{"name":"base","node":"old","role":"frame","xyz":[0,0,0],"rpy":[0,0,0]}]}'''

DEMANDS = [
    "Build a phone dock for 78x12x160mm phone. Desk 420x280mm. From scratch.",
    "Customer upgraded to 90x14x175mm phone. Adapt the dock. MUST reuse the base from round 1.",
    "Add earbuds bay (65x48x28mm). MUST keep the adapted dock and add to it.",
    "Add tablet stand (250x10x175mm) behind. Combine all modules. MUST reuse dock+earbuds.",
    "Desk shrank to 300x200mm! Shrink but keep ALL functions. MUST optimize accumulated design.",
]

JUDGE_SYS = 'Rate the workstation design 0-10 for user satisfaction. Return ONLY JSON: {"rating":<n>,"accepted":<bool>,"feedback":"<t>"}'





def anthropic_call(base, key, model, sys_, user, mt, tp):
    import httpx
    body = {'model': model, 'max_tokens': mt, 'system': sys_,
            'messages': [{'role': 'user', 'content': user}], 'temperature': tp, 'stream': True}
    blocks, usage, done = {}, {}, False
    with httpx.Client(timeout=httpx.Timeout(600, connect=30), trust_env=False) as c:
        with c.stream('POST', base.rstrip('/') + '/v1/messages',
                      headers={'x-api-key': key, 'anthropic-version': '2023-06-01'}, json=body) as r:
            if r.status_code != 200: raise RuntimeError(f'HTTP {r.status_code}')
            for line in r.iter_lines():
                if not line.startswith('data:'): continue
                d = line[5:].strip()
                if d == '[DONE]': break
                try: item = json.loads(d)
                except: continue
                k = item.get('type')
                if k == 'content_block_start': blocks[item['index']] = dict(item['content_block'])
                elif k == 'content_block_delta':
                    b = blocks.setdefault(item['index'], {'type': 'text', 'text': ''})
                    for key in ('text', 'thinking'):
                        if key in item['delta']: b[key] = b.get(key, '') + item['delta'][key]
                elif k == 'message_delta': usage.update(item.get('usage') or {})
                elif k == 'message_stop': done = True; break
    text = ''.join(blocks[i].get('text', '') for i in sorted(blocks) if blocks[i].get('type') == 'text')
    return text, {'input': usage.get('input_tokens', 0), 'output': usage.get('output_tokens', 0)}

def call(spec, sys_, user, folder, label):
    folder = Path(folder); folder.mkdir(parents=True, exist_ok=True)
    key = os.environ.get(spec['key_env'], 'none') if spec.get('key_env') else 'none'
    t0 = time.monotonic()
    if spec.get('protocol') == 'anthropic':
        raw, usage = anthropic_call(spec['api_base'], key, spec['model'], sys_, user, spec['max_tokens'], spec['temp'])
    elif spec.get('protocol') == 'openai-stream':
        raw = openai_stream_call(spec['api_base'], key, spec['model'], sys_, user, spec['max_tokens'], spec['temp'])
        usage = {'input': 0, 'output': 0}
    else:
        from litellm import completion
        r = completion(model=spec['model'], api_base=spec['api_base'], api_key=key,
                      messages=[{'role': 'system', 'content': sys_}, {'role': 'user', 'content': user}],
                      max_tokens=spec['max_tokens'], temperature=spec['temp'], timeout=600)
        raw = r.choices[0].message.content or ''
        usage = {'input': r.usage.prompt_tokens or 0, 'output': r.usage.completion_tokens or 0}
    clean = raw.strip()
    if clean.startswith('```') and clean.endswith('```') and clean.count('```') == 2:
        lines = clean.split('\n')
        if len(lines) >= 3: clean = '\n'.join(lines[1:-1]).strip()
    secs = round(time.monotonic() - t0, 1)
    (folder / f'{label}.json').write_text(json.dumps({'text': clean, 'usage': usage, 'seconds': secs}, ensure_ascii=False, indent=2))
    return clean, usage, secs


def real_cad_eval(text, capital, folder, desk=(420, 280)):
    """Execute design with build123d: build -> STEP export -> re-import -> precise measurement."""
    folder = Path(folder); folder.mkdir(parents=True, exist_ok=True)
    try:
        design = json.loads(text)
        validate_design(design, capital)
        asm, consumed = make_assembly(design, capital)
        step_path = folder / 'design.step'
        export_step(asm, step_path)
        facts = measure_export(step_path, design)
        metrics = occupied_geometry_metrics(facts, {'desk_mm': list(desk)})
        return {'metrics': metrics, 'step_path': str(step_path), 'consumed': consumed,
                'facts_summary': {'extent': facts.get('occupied_extent_mm'),
                                  'intersections': len(facts.get('intersections', []))}}
    except Exception as e:
        return {'error': str(e)[:200], 'metrics': None}

def check_real_reuse(text, capital_ids):
    """Check if design actually imports a capital asset that was consumed by build123d."""
    try:
        d = json.loads(text)
        return any(n.get('op') == 'capital' and n.get('asset_id') in capital_ids for n in d.get('nodes', []))
    except: return False

# ── Multi-judge scoring ──
JUDGE_SYS = 'Rate the workstation design 0-10 for user satisfaction. Return ONLY JSON: {"rating":<n>,"accepted":<bool>,"feedback":"<t>"}'

def multi_judge(judges, demand, text, cad_result, folder, rd):
    """Get scores from multiple LLM judges. Returns list of ratings."""
    scores = []
    ev = cad_result.get('metrics') or {}
    ev_summary = json.dumps({'envelope_excess_mm': ev.get('occupied_envelope_excess_mm'),
                             'overlap_mm3': ev.get('overlap_mm3')})
    for jname, jspec in judges.items():
        if jspec.get('key_env') and not os.environ.get(jspec['key_env']):
            continue  # skip if key not available
        try:
            p = (f'Demand: {demand}\nCAD measurements: {ev_summary}\n'
                 f'Design (truncated): {text[:1200]}\nRate satisfaction 0-10.')
            resp, _, _ = call(jspec, JUDGE_SYS, p, folder, f'judge_{jname}_r{rd}')
            parsed = json.loads(resp)
            scores.append({'judge': jname, 'rating': parsed.get('rating', 0),
                          'accepted': parsed.get('accepted', False),
                          'feedback': parsed.get('feedback', '')[:50]})
        except Exception as e:
            scores.append({'judge': jname, 'rating': 0, 'accepted': False,
                          'feedback': f'err:{str(e)[:30]}'})
    return scores

# ── Main loop ──
def run(spec, judges, dn, root, n_rounds=5):
    root = Path(root); root.mkdir(parents=True, exist_ok=True)
    capital = {}  # real capital: {asset_id: {'status':'EXECUTED_CAD','step_path':...}}
    rounds = []
    total_rev, total_cost = 0.0, 0.0

    for rd in range(n_rounds):
        demand = DEMANDS[rd]
        best_text, best_usage, best_cad, best_secs = None, None, None, 0
        reused = False

        for att in range(2):
            label = f'r{rd}_a{att}'
            msg = json.dumps({
                'demand': demand,
                'capital': [{'id': k, 'desc': v.get('description', '')} for k, v in capital.items()],
                'hint': 'Use capital(asset_id) to import previous modules.' if capital else None})
            try:
                text, usage, secs = call(spec, SYSTEM, msg, root / label, label)
                if not text.strip(): continue
                cad = real_cad_eval(text, capital, root / label / 'cad')
                if cad.get('metrics'):
                    best_text, best_usage, best_cad, best_secs = text, usage, cad, secs
                    reused = check_real_reuse(text, set(capital.keys()))
                    break
            except: continue

        if best_cad is None:
            rounds.append({'rd': rd, 'rating': 0, 'sold': False, 'rev': 0, 'cost': 0,
                          'reused': False, 'secs': 0, 'cad': None})
            continue

        # Multi-judge scoring
        scores = multi_judge(judges, demand, best_text, best_cad, root, rd)
        ratings = [s['rating'] for s in scores if s['rating'] > 0]
        median_rating = sorted(ratings)[len(ratings)//2] if ratings else 0
        sold = median_rating >= ACCEPT
        sp = speed_price(best_secs)
        rev = round(PRICE * sp) if sold else 0
        tokens = best_usage['input'] + best_usage['output']
        cost = tokens * TOKEN_PRICE
        total_rev += rev; total_cost += cost

        # Register real capital (STEP file) for next round
        if sold or median_rating >= 3:
            capital[f'r{rd+1}'] = {
                'status': 'EXECUTED_CAD',
                'step_path': best_cad['step_path'],
                'description': f'Round {rd+1} design',
                'measurements': best_cad.get('metrics', {}),
            }

        rounds.append({'rd': rd, 'rating': median_rating, 'sold': sold, 'rev': rev,
                      'cost': round(cost, 3), 'reused': reused,
                      'secs': best_secs,
                      'cad': best_cad.get('facts_summary'),
                      'judge_scores': scores})
        ic = '✅' if sold else '❌'; ru = '♻️' if reused else '🔧'
        rd1 = rd + 1; mr = median_rating; secs = best_cad.get('secs', 0) if best_cad else 0; rev1 = rev
        print("  R%d: %s %d/10 %s %.0fs Y%.0f" % (rd+1, ic, median_rating, ru, best_cad.get("secs",0) if best_cad else 0, rev), flush=True)

    # Acceleration
    early = [r for r in rounds if r['rd'] < 2 and r.get('secs', 0) > 0]
    late = [r for r in rounds if r['rd'] >= 3 and r.get('secs', 0) > 0]
    et = sum(r['secs'] for r in early) / max(len(early), 1)
    lt = sum(r['secs'] for r in late) / max(len(late), 1)
    t_accel = round(et / lt, 2) if lt > 0 else None

    return {'designer': dn, 'rounds': rounds,
            'profit': round(total_rev - total_cost, 2),
            'revenue': total_rev, 'cost': round(total_cost, 2),
            'sold': f'{sum(1 for r in rounds if r["sold"])}/{n_rounds}',
            'reuse': f'{sum(1 for r in rounds if r.get("reused"))}/{n_rounds-1}',
            't_accel': t_accel}

def display(d):
    print(f'\n┌─────────────────────────────────────────┐')
    print(f'│  💰 PRSI v5 (real CAD): {d["designer"]:16s} │')
    print(f'├─────────────────────────────────────────┤')
    for r in d['rounds']:
        ic = '✅' if r['sold'] else '❌'; ru = '♻️' if r.get('reused') else '🔧'
        s = '卖出' if r['sold'] else '未售'
        print(f'│  R{r["rd"]+1} {ic} {r["rating"]:2.0f}/10 {ru} {r.get("secs",0):3.0f}s → {s} ¥{r["rev"]:3.0f}  │')
    p = d['profit']
    print(f'├─────────────────────────────────────────┤')
    if p > 0: print(f'│  💰 总利润: +¥{p:.2f}                  │')
    else: print(f'│  📉 总亏损: -¥{abs(p):.2f}                  │')
    print(f'│  售出: {d["sold"]}  复用: {d["reuse"]}          │')
    ta = d.get('t_accel')
    if ta and ta > 1.2: print(f'│  ⚡ 速度: {ta}x (后轮更快)             │')
    elif ta and ta < 0.8: print(f'│  🐌 速度: {ta}x (后轮更慢)             │')
    print(f'└─────────────────────────────────────────┘')

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--designer', required=True, choices=list(MODELS))
    p.add_argument('--judges', nargs='+', default=['mimo-v2.6-pro'],
                   help='Judge model names (space-separated for multi-judge)')
    a = p.parse_args()
    ds = MODELS[a.designer]
    judges = {j: MODELS[j] for j in a.judges if j in MODELS}
    for s, n in [(ds, a.designer)] + [(v, k) for k, v in judges.items()]:
        if s.get('key_env') and not os.environ.get(s['key_env']):
            print(f'FATAL: {s["key_env"]} not set for {n}'); sys.exit(1)
    root = RESULTS / a.designer / time.strftime('%Y%m%d_%H%M%S')
    jnames = '+'.join(a.judges)
    print(f'\n💰 PRSI v5 (real CAD): {a.designer} | judges: {jnames}\n')
    r = run(ds, judges, a.designer, root)
    (root / 'result.json').write_text(json.dumps(r, indent=2, ensure_ascii=False) + '\n')
    display(r)

if __name__ == '__main__':
    main()
