#!/usr/bin/env python3
"""Self-play iteration v2: V0-Self generates 500 designs via vLLM (fast batch mode).

Two-phase approach for GPU efficiency:
  Phase 1: vLLM server generates all designs (fast, ~5s each) → save to disk → stop server
  Phase 2: CAD eval + judge each design (CPU/API only) → filter → save training data

The V0-Self model (¥132) should produce more valid + higher-rated designs
than the raw base model did (which only got 47/150 valid, 10 accepted).
"""
import argparse, json, os, random, statistics, subprocess, sys, time, re
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

HERE = Path(__file__).resolve().parent
BENCH = HERE.parent
sys.path.insert(0, str(HERE))
import money_bench_v5 as mb
from rsi_night_loop import cad_eval, judge, ACCEPT

MERGED = '/home/exuber/models/qwen9b-self-rft-merged'
OUT = BENCH / 'runs' / 'self_rft_v2'
PORT = 8100
VLLM = '/home/exuber/.venvs/vllm_serve/bin/python'
MIN_RATING = 3  # lower threshold to get more data
N_ATTEMPTS = 500


def phase1_generate():
    """Start vLLM, generate N designs, stop server."""
    OUT.mkdir(parents=True, exist_ok=True)
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(MERGED, trust_remote_code=True)

    # Start server
    print("Starting vLLM server...", flush=True)
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

    # Generate all designs
    designs = []
    t0 = time.time()
    for i in range(N_ATTEMPTS):
        rd = i % 5
        demand = mb.DEMANDS[rd]
        # Vary capital context: some rounds with capital, some without
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
                                'temperature': 0.7, 'top_p': 0.95, 'seed': i})
            text = r.json()['choices'][0]['text'].strip()
            text = re.sub(r'<think>.*?</think>', '', text, flags=re.S).strip()
            if '"h":' in text and '"hypothesis":' not in text:
                text = text.replace('"h":', '"hypothesis":')
            if len(text) > 40:
                designs.append({'i': i, 'rd': rd, 'demand': demand,
                               'user': user, 'text': text})
        except Exception as e:
            pass

        if (i + 1) % 50 == 0:
            print(f"  gen {i+1}/{N_ATTEMPTS}: {len(designs)} valid texts "
                  f"[{(time.time()-t0)/60:.0f}min]", flush=True)

    # Stop server
    srv.terminate()
    try: srv.wait(timeout=30)
    except: srv.kill()
    time.sleep(5)

    print(f"Phase 1 complete: {len(designs)} designs generated", flush=True)
    (OUT / 'generated.jsonl').write_text('\n'.join(json.dumps(d) for d in designs) + '\n')
    return designs


def phase2_evaluate(designs):
    """CAD eval + judge each design, filter by rating."""
    accepted = []
    valid_count = 0

    def eval_one(d):
        cad = cad_eval(d['text'], {}, OUT / 'cad' / f"att{d['i']}", (420, 280))
        valid = bool(cad.get('metrics'))
        if not valid:
            return None
        rating = judge(d['demand'], d['text'], cad.get('metrics'))
        if rating >= MIN_RATING:
            return {'operator': 'self-rft-v2',
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
    valid_count = sum(1 for r in results if r is not None or True) # approximate

    print(f"Phase 2: {len(accepted)} accepted (rating ≥{MIN_RATING})", flush=True)
    from collections import Counter
    ratings = Counter(e['rating'] for e in accepted)
    print(f"Rating distribution: {dict(sorted(ratings.items()))}", flush=True)

    out_f = OUT / 'self_rft_v2_data.jsonl'
    out_f.write_text('\n'.join(json.dumps(e, ensure_ascii=False) for e in accepted) + '\n')
    print(f"Saved -> {out_f}", flush=True)
    return accepted


def main():
    print("=== Self-Play Iteration v2 ===", flush=True)
    print(f"Model: V0-Self (¥132)", flush=True)
    print(f"Attempts: {N_ATTEMPTS}, Min rating: {MIN_RATING}", flush=True)

    designs = phase1_generate()
    accepted = phase2_evaluate(designs)

    # Combine with V0 data
    v0_data = []
    v0_f = BENCH / 'runs' / 'self_rft' / 'self_rft_data.jsonl'
    if v0_f.exists():
        v0_data = [json.loads(l) for l in v0_f.read_text().splitlines() if l.strip()]

    combined = v0_data + accepted
    print(f"\nCombined training data: {len(v0_data)} (V0) + {len(accepted)} (V2) = {len(combined)} examples", flush=True)

    out_f = OUT / 'combined_v01_data.jsonl'
    out_f.write_text('\n'.join(json.dumps(e, ensure_ascii=False) for e in combined) + '\n')
    print(f"Saved -> {out_f}", flush=True)


if __name__ == '__main__':
    main()
