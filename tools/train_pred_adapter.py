#!/usr/bin/env python3
"""Train a PREDICTION-ONLY LoRA adapter (CAD World Model, separated from generation).

Uses only the 621 design->geometry pairs. No generation data mixed in.
The generation adapter (FluxEidosV1.0 / CARE-v3) stays untouched — at inference
we load both adapters on the same base and switch between them:
  generation: adapter "gen" (CARE-v3)
  prediction: adapter "pred" (this file's output)

Usage: PRSI_EPOCHS=5 python tools/train_pred_adapter.py
"""
import json, os, random, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BENCH = HERE.parent
BASE = os.environ.get('PRSI_BASE', '/home/exuber/models/qwen3.5-9b-bf16')
OUT = Path(os.environ.get('PRSI_OUT', '/home/exuber/models/prsi_cwm_pred'))
EPOCHS = int(os.environ.get('PRSI_EPOCHS', '5'))

PREDICT_SYS = '''You are a CAD geometry oracle. Given a workstation CSG design JSON, predict what build123d will compute when it executes this design. Return ONLY JSON:
{"valid": <true|false>, "overlap_mm3": <float>, "envelope_excess_mm": <float>, "rating": <0-10>}'''


def main():
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(BASE, trust_remote_code=True)

    pairs = json.loads((BENCH / 'runs' / 'training_data' / 'world_model_pairs.json').read_text())
    print(f"prediction-only pairs: {len(pairs)}", flush=True)

    samples = []
    for p in pairs:
        outcome = json.dumps({
            'valid': p['valid'],
            'overlap_mm3': p['overlap_mm3'],
            'envelope_excess_mm': p['envelope_excess_mm'],
            'rating': p['rating'],
        })
        prompt = tok.apply_chat_template(
            [{'role': 'system', 'content': PREDICT_SYS},
             {'role': 'user', 'content': p['design']}],
            tokenize=False, add_generation_prompt=True, enable_thinking=False)
        samples.append({'prompt': prompt, 'text': outcome, 'adv': 1.0})

    random.seed(41); random.shuffle(samples)
    OUT.mkdir(parents=True, exist_ok=True)

    adapter = 'none'
    t0 = time.time()
    for ep in range(1, EPOCHS + 1):
        out_a = str(OUT / f'epoch{ep}')
        job = {
            'adapter': adapter, 'out_adapter': out_a, 'samples': samples,
            'lora_r': 32, 'lora_targets': ['q_proj', 'k_proj', 'v_proj', 'o_proj'],
            'core_path': str(BENCH / 'runs' / 'training_data' / 'sft_v2_core.jsonl'),
            'lr': 8e-5, 'anchor_w': 0.0, 'max_len': 3500,
        }
        jf = OUT / f'job_ep{ep}.json'
        jf.write_text(json.dumps(job))
        r = subprocess.run([sys.executable, '-W', 'ignore', str(HERE / 'rl_train_step_worker.py'), str(jf)],
                           capture_output=True, text=True, timeout=7200)
        line = [l for l in r.stdout.splitlines() if '"status"' in l]
        if not line:
            print(f'epoch {ep} FAILED: {(r.stderr or r.stdout)[-300:]}'); sys.exit(1)
        st = json.loads(line[-1])
        print(f'epoch {ep}: CE={st["pg"]:.4f} over {st["n_pg"]} [{(time.time()-t0)/60:.0f}min]', flush=True)
        adapter = out_a
    print(f'DONE -> {adapter}')


if __name__ == '__main__':
    main()
