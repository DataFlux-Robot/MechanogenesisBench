#!/usr/bin/env python3
"""Phase 3: cross-generation capital inheritance (the PRSI mechanism demo).

Question: does capital (STEP assets) produced by the IMPROVED generation (gen4)
accelerate design work more than capital from the BASE generation (gen0)?

Protocol: build two capital chains by running each adapter on one canonical
instance (same seed), then measure fresh improve-round performance with each
chain as the available capital: 3 parametric instances x 6 samples each,
profit + rating + reuse. Matched everything except the capital source.
"""
import json, os, random, statistics, subprocess, sys, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import money_bench_v5 as mb
from rsi_night_loop import (merge_adapter, start_server, wait_server, stop_server,
                            cad_eval, judge, speed_price, rollout, score_all, ACCEPT, OUT)
import parametric_demands as PD

BASE_ADAPTER = '/home/exuber/models/prsi_rl_v3/iter6'
GEN4_ADAPTER = str(OUT / 'rsi' / 'adapter_gen4')
CHAIN_INSTANCE_SEED = 777  # canonical instance used to grow each lineage's capital


def grow_chain(adapter, dest):
    """Run rounds on canonical instances with this adapter; RETRY with fresh
    instances until a chain with >=2 assets forms (v1 died on unlucky R2s)."""
    from transformers import AutoTokenizer
    import httpx
    tok = AutoTokenizer.from_pretrained('/home/exuber/models/qwen3.5-9b-bf16', trust_remote_code=True)
    if not merge_adapter(adapter):
        raise RuntimeError(f'merge failed for {adapter}')
    srv = start_server()
    if not wait_server():
        raise RuntimeError('server failed')
    capital = {}
    try:
        for attempt in range(3):
            rng = random.Random(CHAIN_INSTANCE_SEED + attempt * 17)
            inst = PD.gen_instance(rng)
            capital = {}
            for rd in range(4):
                demand = inst['demands'][rd]
                user = json.dumps({'demand': demand,
                                   'capital': [{'id': k, 'desc': v['description']} for k, v in capital.items()],
                                   'hint': 'Use capital(asset_id) to import previous modules.' if capital else None})
                prompt = tok.apply_chat_template([{'role': 'system', 'content': mb.SYSTEM},
                                                  {'role': 'user', 'content': user}],
                                                 tokenize=False, add_generation_prompt=True, enable_thinking=False)
                text, secs, cad = None, 0, None
                for att in range(3):
                    body = {'model': 'rsi-policy', 'prompt': prompt, 'max_tokens': 2000,
                            'temperature': 0.3, 'seed': att + attempt * 5}
                    t0 = time.monotonic()
                    try:
                        with httpx.Client(timeout=httpx.Timeout(420, connect=20), trust_env=False) as c:
                            r = c.post(f'http://127.0.0.1:8100/v1/completions', json=body,
                                       headers={'Authorization': 'Bearer none'})
                        t = r.json()['choices'][0]['text'].strip()
                    except Exception:
                        continue
                    if '"h":' in t and '"hypothesis":' not in t:
                        t = t.replace('"h":', '"hypothesis":')
                    cc = cad_eval(t, capital, dest / f'a{attempt}_r{rd}_{att}', inst['desk'])
                    if cc.get('metrics'):
                        text, secs, cad = t, round(time.monotonic() - t0, 1), cc
                        break
                if cad is None:
                    break
                rating = judge(demand, text, cad.get('metrics'))
                print(f"  chain {dest.name} attempt{attempt} R{rd+1}: rating {rating}", flush=True)
                if rating >= 3:
                    capital[f'r{rd+1}'] = {'status': 'EXECUTED_CAD', 'step_path': cad['step_path'],
                                           'description': f'Round {rd+1} design', 'measurements': {}}
            if len(capital) >= 2:
                break
            print(f"  chain {dest.name} attempt{attempt} too short ({list(capital)}); retrying", flush=True)
    finally:
        stop_server()
    return capital


def eval_with_capital(capital, desk_map, tag):
    """6 samples x 3 fresh instances: improve-round performance given this capital."""
    from transformers import AutoTokenizer
    import httpx
    tok = AutoTokenizer.from_pretrained('/home/exuber/models/qwen3.5-9b-bf16', trust_remote_code=True)
    caps_desc = [{'id': k, 'desc': v['description']} for k, v in capital.items()]
    rows = []
    srv = start_server()
    if not wait_server():
        raise RuntimeError('server failed')
    try:
        for i in range(3):
            rng = random.Random(900 + i)
            inst = PD.sample_train(rng)
            user = json.dumps({'demand': inst['demands'][2], 'capital': caps_desc,
                               'hint': 'Use capital(asset_id) to import previous modules.'})
            prompt = tok.apply_chat_template([{'role': 'system', 'content': mb.SYSTEM},
                                              {'role': 'user', 'content': user}],
                                             tokenize=False, add_generation_prompt=True, enable_thinking=False)
            for j in range(6):
                body = {'model': 'rsi-policy', 'prompt': prompt, 'max_tokens': 1800,
                        'temperature': 0.3, 'seed': j}
                t0 = time.monotonic()
                try:
                    with httpx.Client(timeout=httpx.Timeout(420, connect=20), trust_env=False) as c:
                        r = c.post(f'http://127.0.0.1:8100/v1/completions', json=body,
                                   headers={'Authorization': 'Bearer none'})
                    text = r.json()['choices'][0]['text'].strip()
                    secs = round(time.monotonic() - t0, 1)
                except Exception:
                    continue
                if '"h":' in text and '"hypothesis":' not in text:
                    text = text.replace('"h":', '"hypothesis":')
                cad = cad_eval(text, capital, OUT / 'cap_demo' / tag / f'i{i}_s{j}', inst['desk'])
                valid = bool(cad.get('metrics'))
                rating = judge(inst['demands'][2], text, cad.get('metrics')) if valid else 0
                sold = rating >= ACCEPT
                rev = round(100 * speed_price(secs)) if sold else 0
                try:
                    reused = any(n.get('op') == 'capital' for n in json.loads(text).get('nodes', []))
                except Exception:
                    reused = False
                rows.append({'valid': valid, 'rating': rating, 'sold': sold, 'rev': rev, 'reused': reused})
    finally:
        stop_server()
    return rows


def main():
    (OUT / 'cap_demo').mkdir(parents=True, exist_ok=True)
    print('growing BASE (gen0) capital chain...', flush=True)
    cap_base = grow_chain(BASE_ADAPTER, OUT / 'cap_demo' / 'chain_base')
    print(f'base chain: {sorted(cap_base)}', flush=True)
    print('growing GEN4 capital chain...', flush=True)
    cap_g4 = grow_chain(GEN4_ADAPTER, OUT / 'cap_demo' / 'chain_g4')
    print(f'gen4 chain: {sorted(cap_g4)}', flush=True)
    if not cap_base or not cap_g4:
        print('chain growth failed after retries; aborting demo'); return

    print('\nevaluating with BASE capital...', flush=True)
    rows_base = eval_with_capital(cap_base, None, 'with_base')
    print('evaluating with GEN4 capital...', flush=True)
    rows_g4 = eval_with_capital(cap_g4, None, 'with_g4')

    def summ(rows):
        return {'n': len(rows),
                'valid': round(statistics.mean([1.0*r['valid'] for r in rows]), 3),
                'sold': round(statistics.mean([1.0*r['sold'] for r in rows]), 3),
                'mean_rev': round(statistics.mean([r['rev'] for r in rows]), 1),
                'reuse': round(statistics.mean([1.0*r['reused'] for r in rows]), 3),
                'rating_valid': round(statistics.mean([r['rating'] for r in rows if r['valid']] or [0]), 2)}

    result = {'base_capital': summ(rows_base), 'gen4_capital': summ(rows_g4),
              'rows_base': rows_base, 'rows_g4': rows_g4}
    (OUT / 'cap_demo' / 'result.json').write_text(json.dumps(result, indent=2))
    print('\nCAPITAL INHERITANCE DEMO:')
    print(f"  base(gen0) capital: {result['base_capital']}")
    print(f"  gen4 capital:       {result['gen4_capital']}")


if __name__ == '__main__':
    main()
