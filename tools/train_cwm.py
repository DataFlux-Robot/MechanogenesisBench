#!/usr/bin/env python3
"""CAD World Model: train the model to PREDICT geometry outcomes from design JSON.

CWM-inspired (arXiv:2510.02387): instead of only learning to GENERATE designs,
the model learns what designs DO when executed — validity, overlap, envelope.
This internal "geometric imagination" should improve generation quality.

Two training tasks:
  1. Predict task: given design JSON, output {"valid": bool, "overlap": float, "excess": float, "rating": int}
  2. Generation task: standard design generation (our existing SFT data)

Mixed 50/50 so the model learns both to make and to evaluate.

Usage (dd_qwen9b venv):
  PRSI_PREQUANT=1 PRSI_BASE=... PRSI_DATA=... PRSI_OUT=... python tools/train_cwm.py
"""
import json, os, sys, time, random
from pathlib import Path

os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
HERE = Path(__file__).resolve().parent
BENCH = HERE.parent
sys.path.insert(0, str(HERE))
import money_bench_v5 as mb

def main():
    import torch
    from transformers import AutoTokenizer

    BASE = os.environ.get('PRSI_BASE', '/home/exuber/models/qwen3.5-9b-bf16')
    OUT = Path(os.environ.get('PRSI_OUT', '/home/exuber/models/prsi_cwm'))
    EPOCHS = int(os.environ.get('PRSI_EPOCHS', '6'))
    OUT.mkdir(parents=True, exist_ok=True)

    tok = AutoTokenizer.from_pretrained(BASE, trust_remote_code=True)

    # Load design-geometry pairs
    pairs = json.loads((BENCH / 'runs' / 'training_data' / 'world_model_pairs.json').read_text())
    print(f"world model pairs: {len(pairs)}")

    # Load standard SFT data
    sft = [json.loads(l) for l in (BENCH / 'runs' / 'training_data' / 'sft_v3_train.jsonl').read_text().splitlines() if l.strip()]
    print(f"SFT examples: {len(sft)}")

    PREDICT_SYS = '''You are a CAD geometry oracle. Given a workstation CSG design JSON, predict what build123d will compute when it executes this design. Return ONLY JSON:
{"valid": <true|false>, "overlap_mm3": <float>, "envelope_excess_mm": <float>, "rating": <0-10>}'''

    # Build mixed training samples
    all_samples = []
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
        all_samples.append({'prompt': prompt, 'text': outcome, 'adv': 1.0})

    for e in sft:
        pr = tok.apply_chat_template(e['messages'][:2], tokenize=False,
                                     add_generation_prompt=True, enable_thinking=False)
        all_samples.append({'prompt': pr, 'text': e['messages'][2]['content'], 'adv': 1.0})

    random.seed(41); random.shuffle(all_samples)
    print(f"total mixed samples: {len(all_samples)} (predict {len(pairs)} + generate {len(sft)})")

    # Train via the chunked-loss worker (memory-safe)
    adapter = 'none'
    t0 = time.time()
    for ep in range(1, EPOCHS + 1):
        out_a = str(OUT / f'epoch{ep}')
        job = {
            'adapter': adapter, 'out_adapter': out_a, 'samples': all_samples,
            'lora_r': 32,
            'lora_targets': ['q_proj', 'k_proj', 'v_proj', 'o_proj'],
            'core_path': '', 'lr': 8e-5, 'anchor_w': 0.0, 'max_len': 2048,
        }
        jf = OUT / f'job_ep{ep}.json'
        # core_path can't be empty for file read; use sft core
        job['core_path'] = str(BENCH / 'runs' / 'training_data' / 'sft_v2_core.jsonl')
        jf.write_text(json.dumps(job))
        import subprocess
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
