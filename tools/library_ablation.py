#!/usr/bin/env python3
"""Capital-library size ablation: production profit vs library size.

Uses the persisted 20-asset library from the capital arm (seed 0 rebuilt via
seed 1's library if needed), serves the FROZEN gen0 model, runs production on
the fixed instances with sub-libraries of increasing size.
"""
import json, random, statistics, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import money_bench_v5 as mb
from rsi_night_loop import merge_adapter, start_server, wait_server, stop_server, cad_eval, judge, speed_price
from dual_loop_prsi import production_instances, user_msg, N_ROUNDS, ACCEPT, DUAL
import httpx

BASE = '/home/exuber/models/qwen3.5-9b-bf16'
ADAPTER = '/home/exuber/models/prsi_rl_v3/iter6'
SIZES = [0, 3, 6, 12, 24]


def prod_pass(tok, library, tag):
    insts = production_instances()
    stats = []
    for ii, inst in enumerate(insts):
        cap = dict(library)
        for rd in range(N_ROUNDS):
            prompt = tok.apply_chat_template(
                [{'role': 'system', 'content': mb.SYSTEM}, {'role': 'user', 'content': user_msg(inst['demands'][rd], cap)}],
                tokenize=False, add_generation_prompt=True, enable_thinking=False)
            best = None
            for att in range(2):
                body = {'model': 'rsi-policy', 'prompt': prompt, 'max_tokens': 2000,
                        'temperature': 0.3, 'seed': att}
                t0 = time.monotonic()
                try:
                    with httpx.Client(timeout=httpx.Timeout(420, connect=20), trust_env=False) as c:
                        r = c.post('http://127.0.0.1:8100/v1/completions', json=body,
                                   headers={'Authorization': 'Bearer none'})
                    text = r.json()['choices'][0]['text'].strip()
                    secs = round(time.monotonic() - t0, 1)
                except Exception:
                    continue
                if not text:
                    continue
                if '"h":' in text and '"hypothesis":' not in text:
                    text = text.replace('"h":', '"hypothesis":')
                cad = cad_eval(text, cap, DUAL / 'ablation' / tag / f'i{ii}_r{rd}_a{att}', inst['desk'])
                if cad.get('metrics'):
                    best = (text, secs, cad)
                    break
            if best is None:
                stats.append({'rev': 0, 'sold': False, 'reused': False})
                continue
            text, secs, cad = best
            rating = judge(inst['demands'][rd], text, cad.get('metrics'))
            sold = rating >= ACCEPT
            try:
                reused = any(n.get('op') == 'capital' for n in json.loads(text).get('nodes', []))
            except Exception:
                reused = False
            stats.append({'rev': round(100 * speed_price(secs)) if sold else 0,
                          'sold': sold, 'reused': reused, 'rating': rating})
            if rating >= 3:
                cap[f's{ii}r{rd+1}'] = {'status': 'EXECUTED_CAD', 'step_path': cad['step_path'],
                                         'description': f"{inst['family']} round {rd+1} module", 'measurements': {}}
    return stats


def main():
    # gather libraries from all capital seed runs (persisted by the patched loop)
    libs = []
    for d in sorted(DUAL.glob('capital*')):
        f = d / 'library.json'
        if f.exists():
            libs.append(json.loads(f.read_text()))
    if not libs:
        print('no persisted libraries; run patched capital arm first'); return
    merged = {}
    for l in libs:
        merged.update(l)
    items = sorted(merged.items(), key=lambda kv: -kv[1].get('rating', 0))
    print(f'pooled library: {len(items)} assets from {len(libs)} runs')

    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(BASE, trust_remote_code=True)
    if not merge_adapter(ADAPTER):
        print('merge failed'); return
    srv = start_server()
    if not wait_server():
        print('server failed'); return
    results = {}
    try:
        for n in SIZES:
            lib = dict(items[:n])
            tag = f'lib{n}'
            stats = prod_pass(tok, lib, tag)
            results[n] = {'profit': sum(s['rev'] for s in stats),
                          'sold': sum(1 for s in stats if s['sold']),
                          'reuse': sum(1 for s in stats if s.get('reused')),
                          'mean_rating': round(statistics.mean([s.get('rating', 0) for s in stats]), 2)}
            print(f"lib {n:>2}: profit ¥{results[n]['profit']} sold {results[n]['sold']}/12 "
                  f"reuse {results[n]['reuse']}/12 rating {results[n]['mean_rating']}", flush=True)
    finally:
        stop_server()
    (DUAL / 'ablation').mkdir(parents=True, exist_ok=True)
    (DUAL / 'ablation' / 'result.json').write_text(json.dumps(results, indent=2))
    print('\nsaved -> runs/dual_loop/ablation/result.json')


if __name__ == '__main__':
    main()
