#!/usr/bin/env python3
"""Self-generated RFT (Rejection Fine-Tuning): eliminate SFT from other models' data.

Process:
  1. Start from raw Qwen3.5-9B (no SFT, no other model's data)
  2. Few-shot prompt the base model to generate designs on Money Bench demands
  3. Execute in real CAD → filter for valid designs
  4. Judge rating ≥4 → accept as training data
  5. Save accepted (prompt, design, reward) triples for LoRA RFT

This is entirely SELF-GENERATED data: the model teaches itself from its own
exploration, guided only by execution feedback (CAD) and task rubric (judge).

Usage: MIMO_KEY=... python tools/self_rft_gen.py --n-attempts 200
"""
import argparse, json, os, random, statistics, sys, time, re
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
HERE = Path(__file__).resolve().parent
BENCH = HERE.parent
sys.path.insert(0, str(HERE))
import money_bench_v5 as mb
from rsi_night_loop import cad_eval, judge, speed_price, ACCEPT

BASE = '/home/exuber/models/qwen3.5-9b-bf16'
OUT = BENCH / 'runs' / 'self_rft'
MIN_RATING = 4  # acceptance threshold


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n-attempts', type=int, default=200)
    ap.add_argument('--temp', type=float, default=0.8)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig

    tok = AutoTokenizer.from_pretrained(BASE, trust_remote_code=True)
    if tok.pad_token is None: tok.pad_token = tok.eos_token
    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4',
                             bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True)
    model = AutoModelForCausalLM.from_pretrained(BASE, quantization_config=bnb,
                                                 device_map='cuda', trust_remote_code=True)
    model.eval()

    # Generate designs for all 5 demands, cycling through rounds
    accepted = []
    total_valid = 0
    print(f"Generating {a.n_attempts} self-play attempts...", flush=True)

    for i in range(a.n_attempts):
        rd = i % 5
        demand = mb.DEMANDS[rd]
        user = json.dumps({'demand': demand, 'capital': [], 'hint': None})
        prompt = tok.apply_chat_template(
            [{'role': 'system', 'content': mb.SYSTEM}, {'role': 'user', 'content': user}],
            tokenize=False, add_generation_prompt=True, enable_thinking=False)
        ids = tok(prompt, return_tensors='pt', truncation=True, max_length=3500).to(model.device)

        torch.manual_seed(1000 + i)
        t0 = time.monotonic()
        with torch.no_grad():
            out = model.generate(**ids, max_new_tokens=1500, temperature=a.temp,
                                 do_sample=True, top_p=0.95, pad_token_id=tok.pad_token_id)
        text = tok.decode(out[0][ids['input_ids'].shape[1]:], skip_special_tokens=True).strip()
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.S).strip()
        if '"h":' in text and '"hypothesis":' not in text:
            text = text.replace('"h":', '"hypothesis":')
        secs = round(time.monotonic() - t0, 1)

        if len(text) < 40:
            continue

        # CAD execution (ground truth validity check)
        cad = cad_eval(text, {}, OUT / 'cad' / f'att{i}', (420, 280))
        valid = bool(cad.get('metrics'))
        if not valid:
            continue
        total_valid += 1

        # Judge rating (task rubric)
        rating = judge(demand, text, cad.get('metrics'))
        if rating >= MIN_RATING:
            accepted.append({
                'operator': 'self-rft',
                'messages': [
                    {'role': 'system', 'content': mb.SYSTEM},
                    {'role': 'user', 'content': user},
                    {'role': 'assistant', 'content': text}
                ],
                'rating': rating, 'secs': secs
            })
            print(f"  [{i+1}/{a.n_attempts}] ✓ rating {rating} (accepted {len(accepted)})", flush=True)

        if (i + 1) % 20 == 0:
            print(f"  [{i+1}/{a.n_attempts}] valid={total_valid} accepted={len(accepted)} "
                  f"({len(accepted)/max(total_valid,1):.0%} of valid)", flush=True)

    print(f"\nSelf-RFT complete: {total_valid}/{a.n_attempts} valid, "
          f"{len(accepted)} accepted (rating ≥{MIN_RATING})", flush=True)

    out_f = OUT / 'self_rft_data.jsonl'
    out_f.write_text('\n'.join(json.dumps(e, ensure_ascii=False) for e in accepted) + '\n')
    print(f"Saved -> {out_f}")

    # Rating distribution
    ratings = [e['rating'] for e in accepted]
    if ratings:
        from collections import Counter
        print(f"Rating distribution: {dict(sorted(Counter(ratings).items()))}")


if __name__ == '__main__':
    main()
