#!/usr/bin/env python3
"""Self-play v2.1: V0-Self at temp 0.3 (bench temperature) for pure JSON output.

Key insight: V0-Self produces pure JSON at temp 0.3 (proven by ¥132 bench score)
but drifts into reasoning mode at temp 0.7. Using bench temperature ensures
format consistency while the self-play flywheel accumulates quality data.

STRICT FILTER: only accept designs starting with {"schema" — zero tolerance.
"""
import json, os, random, statistics, subprocess, sys, time, re
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

HERE = Path(__file__).resolve().parent
BENCH = HERE.parent
sys.path.insert(0, str(HERE))
import money_bench_v5 as mb
from rsi_night_loop import cad_eval, judge, ACCEPT

MERGED = '/home/exuber/models/qwen9b-self-rft-merged'  # V0-Self merged
OUT = BENCH / 'runs' / 'self_rft_v21'
PORT = 8100
VLLM = '/home/exuber/.venvs/vllm_serve/bin/python'
MIN_RATING = 3
N_ATTEMPTS = 400
TEMP = 0.3  # bench temperature — pure JSON output


def phase1_generate():
    """vLLM server generates designs at temp 0.3."""
    OUT.mkdir(parents=True, exist_ok=True)
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(MERGED, trust_remote_code=True)

    print(f"Starting vLLM (V0-Self, temp={TEMP})...", flush=True)
    log = open(OUT / 'vllm.log', 'a')
    srv = subprocess.Popen(
        [VLLM, '-m', 'vllm.entrypoints.openai.api_server', '--model', MERGED,
         '--served-model-name', 'v0-self', '--port', str(PORT),
         '--max-model-len', '4096', '--gpu-memory-utilization', '0.90',
         '--enforce-eager', '--max-num-seqs', '4', '--max-num-batched-tokens', '4096'],
        stdout=log, stderr=subprocess.STDOUT)

    import httpx
    for _ in range(60):
        try:
            with httpx.Client(timeout=5, trust_env=False) as c:
                if c.get(f'http://127.0.0.1:{PORT}/v1/models').status_code == 200:
                    break
        except: pass
        time.sleep(5)

    designs = []
    t0 = time.time()
    for i in range(N_ATTEMPTS):
        rd = i % 5
        demand = mb.DEMANDS[rd]
        # Vary capital context
        if rd > 0 and i % 3 == 0:
            caps = [{'id': f'r{j+1}', 'desc': f'Round {j+1} design'} for j in range(rd)]
            hint = 'Use capital(asset_id) to import previous modules.'
        else:
            caps = []
            hint = None
        user = json.dumps({'demand': demand, 'capital': caps, 'hint': hint})
        prompt = tok.apply_chat_template(
            [{'role': 'system', 'content': mb.SYSTEM}, {'role': 'user', 'content': user}],
            tokenize=False, add_generation_prompt=True, enable_thinking=False)

        try:
            with httpx.Client(timeout=httpx.Timeout(120, connect=20), trust_env=False) as c:
                r = c.post(f'http://127.0.0.1:{PORT}/v1/completions',
                          headers={'Authorization': 'Bearer none'},
                          json={'model': 'v0-self', 'prompt': prompt, 'max_tokens': 1500,
                                'temperature': TEMP, 'top_p': 0.95, 'seed': 2000 + i})
            text = r.json()['choices'][0]['text'].strip()

            # STRICT FILTER: must start with {"schema" — zero tolerance for reasoning
            if not text.startswith('{"schema"'):
                continue

            if '"h":' in text and '"hypothesis":' not in text:
                text = text.replace('"h":', '"hypothesis":')

            # Validate JSON structure
            try:
                d = json.loads(text)
                if len(d.get('nodes', [])) < 3 or len(d.get('parts', [])) < 2:
                    continue
            except:
                continue

            designs.append({'i': i, 'rd': rd, 'demand': demand,
                           'user': user, 'text': text})
        except Exception:
            pass

        if (i + 1) % 50 == 0:
            pure_pct = len(designs) / (i + 1) * 100
            print(f"  gen {i+1}/{N_ATTEMPTS}: {len(designs)} pure JSON ({pure_pct:.0f}%) "
                  f"[{(time.time()-t0)/60:.0f}min]", flush=True)

    srv.terminate()
    try: srv.wait(timeout=30)
    except: srv.kill()
    time.sleep(5)

    print(f"Phase 1: {len(designs)} pure JSON designs from {N_ATTEMPTS} attempts", flush=True)
    (OUT / 'generated.jsonl').write_text('\n'.join(json.dumps(d) for d in designs) + '\n')
    return designs


def phase2_evaluate(designs):
    """CAD eval + judge, strict pure JSON already guaranteed."""
    def eval_one(d):
        cad = cad_eval(d['text'], {}, OUT / 'cad' / f"att{d['i']}", (420, 280))
        valid = bool(cad.get('metrics'))
        if not valid:
            return None
        rating = judge(d['demand'], d['text'], cad.get('metrics'))
        if rating >= MIN_RATING:
            return {'operator': 'self-rft-v21',
                    'messages': [
                        {'role': 'system', 'content': mb.SYSTEM},
                        {'role': 'user', 'content': d['user']},
                        {'role': 'assistant', 'content': d['text']}
                    ],
                    'rating': rating, 'round': d['rd']}
        return None

    with ThreadPoolExecutor(max_workers=4) as ex:
        results = list(ex.map(eval_one, designs))

    accepted = [r for r in results if r]
    from collections import Counter
    ratings = Counter(e['rating'] for e in accepted)
    print(f"Phase 2: {len(accepted)} accepted (rating >= {MIN_RATING})", flush=True)
    print(f"Rating distribution: {dict(sorted(ratings.items()))}", flush=True)

    out_f = OUT / 'v21_data.jsonl'
    out_f.write_text('\n'.join(json.dumps(e, ensure_ascii=False) for e in accepted) + '\n')
    print(f"Saved -> {out_f}", flush=True)
    return accepted


def main():
    print("=== Self-Play v2.1 (strict JSON, temp 0.3) ===", flush=True)
    print(f"Model: V0-Self | Attempts: {N_ATTEMPTS} | Temp: {TEMP} | Min rating: {MIN_RATING}", flush=True)

    designs = phase1_generate()
    accepted = phase2_evaluate(designs)

    # Combine with V0's pure examples
    v0_pure = []
    for line in (BENCH / 'runs/self_rft/self_rft_data.jsonl').read_text().splitlines():
        if not line.strip(): continue
        e = json.loads(line)
        if e['messages'][2]['content'].strip().startswith('{"schema"'):
            v0_pure.append(e)

    combined = v0_pure + accepted
    print(f"\nV0.2 combined: {len(v0_pure)} (V0 pure) + {len(accepted)} (V2.1) = {len(combined)} examples", flush=True)

    out_f = OUT / 'v02_combined.jsonl'
    out_f.write_text('\n'.join(json.dumps(e, ensure_ascii=False) for e in combined) + '\n')
    print(f"Saved -> {out_f}", flush=True)


if __name__ == '__main__':
    main()
