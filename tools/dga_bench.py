#!/usr/bin/env python3
"""DGA Bench v2.0 — Machine-Making Acceleration Score."""
import argparse, json, os, sys, time
from pathlib import Path

RESULTS = Path('/media/exuber/Elements/DataFlux/MechanogenesisBenchDEV/dga_bench_runs')

MODELS = {
    'glm-5.3-flash': {'model': 'glm-5.3-flash', 'api_base': 'https://api.z.ai/api/anthropic',
                       'protocol': 'anthropic', 'key_env': 'ZAI_KEY', 'max_tokens': 16000, 'temperature': 0.3},
    'glm-5.3': {'model': 'glm-5.3', 'api_base': 'https://api.z.ai/api/anthropic',
                'protocol': 'anthropic', 'key_env': 'ZAI_KEY', 'max_tokens': 32000, 'temperature': 0.6},
    'mimo-v2.6-pro': {'model': 'openai/mimo-v2.6-pro', 'api_base': 'https://api.xiaomimimo.com/v1',
                      'protocol': 'openai', 'key_env': 'MIMO_KEY', 'max_tokens': 32000, 'temperature': 0.6},
    'mimo-v2.6-flash': {'model': 'openai/mimo-v2.6-flash', 'api_base': 'https://api.xiaomimimo.com/v1',
                        'protocol': 'openai', 'key_env': 'MIMO_KEY', 'max_tokens': 32000, 'temperature': 0.6},
}

SYSTEM = '''You are a workstation product designer. Return ONLY a JSON object.
Ops: box(size), cylinder(radius,height), union(inputs), difference(inputs), transform(input,xyz,rpy), capital(asset_id).
Parts: {"name","node","role(frame|module|tooling)","xyz","rpy"}. Max 64 nodes, 16 parts. mm, XY desk plane.
Produce JSON immediately. Example:
{"schema":"workstation-csg/1","hypothesis":"base","nodes":[{"id":"b","op":"box","size":[200,150,10]},{"id":"r","op":"box","size":[60,40,40]}],"parts":[{"name":"base","node":"b","role":"frame","xyz":[0,0,0],"rpy":[0,0,0]},{"name":"riser","node":"r","role":"module","xyz":[0,-50,10],"rpy":[0,0,0]}]}'''

JUDGE_SYS = 'Rate the workstation design 0-10. Return ONLY JSON: {"rating": <n>, "accepted": <bool>, "feedback": "<text>", "next_request": "<text>"}'

DEMANDS = [
    "Phone (78×12×160mm) + earbuds (65×48×28mm) holder. Desk 420×280mm. Compact.",
    "Add tablet (250×10×175mm), storage left (left-handed). Reuse previous design. 420×280mm.",
    "Add screwdriver space + parts trays. Tablet shows instructions. Reuse modules. 420×280mm.",
]

def anthropic_call(base, key, model, system, user, mt, temp):
    import httpx
    body = {'model': model, 'max_tokens': mt, 'system': system,
            'messages': [{'role': 'user', 'content': user}], 'temperature': temp, 'stream': True}
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

def call(spec, system, user, folder, label, mt_override=None):
    folder = Path(folder); folder.mkdir(parents=True, exist_ok=True)
    key = os.environ.get(spec['key_env'], 'none') if spec.get('key_env') else 'none'
    mt = mt_override or spec['max_tokens']
    t0 = time.monotonic()
    if spec.get('protocol') == 'anthropic':
        raw, usage = anthropic_call(spec['api_base'], key, spec['model'], system, user, mt, spec['temperature'])
    else:
        from litellm import completion
        r = completion(model=spec['model'], api_base=spec['api_base'], api_key=key,
                      messages=[{'role': 'system', 'content': system}, {'role': 'user', 'content': user}],
                      max_tokens=mt, temperature=spec['temperature'], timeout=600)
        raw = r.choices[0].message.content or ''
        usage = {'input': r.usage.prompt_tokens or 0, 'output': r.usage.completion_tokens or 0}
    clean = raw.strip()
    if clean.startswith('\`\`\`') and clean.endswith('\`\`\`') and clean.count('\`\`\`') == 2:
        lines = clean.split('\n')
        if len(lines) >= 3: clean = '\n'.join(lines[1:-1]).strip()
    secs = round(time.monotonic() - t0, 1)
    (folder / f'{label}.json').write_text(json.dumps({'text': clean, 'usage': usage, 'seconds': secs}, ensure_ascii=False, indent=2))
    return clean, usage, secs

def evaluate(text):
    try:
        d = json.loads(text) if isinstance(text, str) else text
        if not d or not isinstance(d, dict): return None
        nodes, parts = d.get('nodes', []), d.get('parts', [])
        if not nodes or not parts: return None
        xs, ys = [], []
        for p in parts:
            xyz = p.get('xyz', [0, 0, 0])
            n = next((n for n in nodes if n.get('id') == p.get('node')), {})
            s = n.get('size', [100, 100, 50])
            xs += [xyz[0] - s[0] / 2, xyz[0] + s[0] / 2]
            ys += [xyz[1] - s[1] / 2, xyz[1] + s[1] / 2]
        if not xs: return None
        ex, ey = max(xs) - min(xs), max(ys) - min(ys)
        excess = max(0, ex - 420) + max(0, ey - 280)
        overlap = sum(1 for i, a in enumerate(parts) for b in parts[i + 1:]
                     if abs(a.get('xyz', [0, 0, 0])[0] - b.get('xyz', [0, 0, 0])[0]) < 50
                     and abs(a.get('xyz', [0, 0, 0])[1] - b.get('xyz', [0, 0, 0])[1]) < 50)
        return {'quality': excess / 100 + overlap * 50, 'excess_mm': round(excess, 1),
                'overlap_mm3': overlap * 50000, 'extent': [round(ex), round(ey)]}
    except: return None

def judge(jspec, demand, text, ev, folder, gen):
    try:
        p = f'Demand: {demand}\nCAD: {json.dumps(ev)}\nDesign: {text[:1200]}\nRate 0-10.'
        resp, _, _ = call(jspec, JUDGE_SYS, p, folder, f'user_g{gen}')
        parsed = json.loads(resp)
        return parsed if 'rating' in parsed else {'rating': 0, 'accepted': False, 'feedback': 'parse_err', 'next_request': ''}
    except Exception as e:
        return {'rating': 0, 'accepted': False, 'feedback': f'err:{str(e)[:40]}', 'next_request': ''}

def run(dspec, jspec, dn, jn, root):
    root = Path(root); root.mkdir(parents=True, exist_ok=True)
    capital, gens = [], []
    for gen in range(3):
        best_t, best_ev, fails = None, None, 0
        usage_t, secs_t = {'input': 0, 'output': 0}, 0.0
        for cand in range(2):
            label = f'g{gen}_c{cand}'
            msg = json.dumps({'demand': DEMANDS[gen], 'operator': 'Draft' if gen == 0 else 'Improve',
                              'capital': [{'id': c['id'], 'desc': c['desc']} for c in capital],
                              'parent_feedback': (gens[-1].get('user') or {}).get('feedback') if gens else None})
            try:
                mt = min(dspec['max_tokens'] * 2, 64000) if cand > 0 else None
                text, u, s = call(dspec, SYSTEM, msg, root / label, label, mt_override=mt)
                usage_t['input'] += u['input']; usage_t['output'] += u['output']; secs_t += s
                if not text.strip(): fails += 1; continue
                ev = evaluate(text)
                if ev and (best_ev is None or ev['quality'] < best_ev['quality']):
                    best_t, best_ev = text, ev
                    capital.append({'id': label, 'desc': f'Gen{gen}: {ev["extent"]}'})
            except: fails += 1
        if best_t is None:
            gens.append({'gen': gen, 'loss': 99.9, 'S': 0, 'user': None, 'ev': None}); continue
        u = judge(jspec, DEMANDS[gen], best_t, best_ev, root, gen)
        cost = secs_t / 600 + usage_t['output'] / 10000 + 2.0 * fails
        gens.append({'gen': gen, 'loss': round(best_ev['quality'] + cost, 2), 'S': u['rating'],
                     'user': u, 'ev': best_ev})
        print(f'  G{gen}: S={u["rating"]}/10 ℓ={gens[-1]["loss"]} excess={best_ev["excess_mm"]}mm', flush=True)
    return {'designer': dn, 'judge': jn, 'generations': gens}

def display(d):
    print('\n┌' + '─' * 52 + '┐')
    print(f'│  🏭 机器造机加速评分                                  │')
    print(f'│  设计者: {d["designer"]:20s} 评委: {d["judge"][:16]:16s}    │')
    print('├──────┬──────────┬──────────┬──────────┤')
    print(f'│      │ 用户满意度│ 生产成本ℓ │ 性价比S/ℓ │')
    print('├──────┼──────────┼──────────┼──────────┤')
    spc_vals = []
    for g in d['generations']:
        lbl = f'第{g["gen"] + 1}代 '
        if g['loss'] >= 99.9 or g['S'] is None:
            print(f'│ {lbl} │    —     │    —     │    —     │'); spc_vals.append(None)
        else:
            spc = g['S'] / g['loss'] if g['loss'] else 0
            spc_vals.append(spc)
            acc = '✓' if (g.get('user') or {}).get('accepted') else '✗'
            print(f'│ {lbl} │  {g["S"]:.0f}/10 {acc}  │ {g["loss"]:8.1f} │ {spc:8.3f} │')
    print('├──────┴──────────┴──────────┴──────────┤')
    valid = [(i, v) for i, v in enumerate(spc_vals) if v is not None and v > 0]
    if len(valid) >= 2:
        chg = (valid[-1][1] - valid[0][1]) / valid[0][1] * 100
        icon = '🚀 加速中' if chg > 10 else ('➡️ 稳定' if chg > -10 else '📉 减速中')
        print(f'│  加速率: {chg:+.1f}%  {icon:12s}                    │')
    else:
        print(f'│  加速率: 数据不足                                    │')
    reused = any(k in str((g.get('user') or {}).get('feedback', '')).lower()
                 for g in d['generations'] for k in ('capital', 'reuse', 'reused', '上代'))
    print(f'│  复用行为: {"✓ 使用了继承资产" if reused else "— 未检测到":20s}             │')
    print('└' + '─' * 52 + '┘')

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--designer', required=True, choices=list(MODELS))
    p.add_argument('--judge', required=True, choices=list(MODELS))
    a = p.parse_args()
    ds, js = MODELS[a.designer], MODELS[a.judge]
    for s, n in [(ds, a.designer), (js, a.judge)]:
        if s.get('key_env') and not os.environ.get(s['key_env']):
            print(f'FATAL: {s["key_env"]} not set'); sys.exit(1)
    root = RESULTS / f'{a.designer}_by_{a.judge}' / time.strftime('%Y%m%d_%H%M%S')
    print(f'\nDGA v2.0: {a.designer} × {a.judge}\n')
    r = run(ds, js, a.designer, a.judge, root)
    (root / 'result.json').write_text(json.dumps(r, indent=2, ensure_ascii=False) + '\n')
    display(r)

if __name__ == '__main__':
    main()
