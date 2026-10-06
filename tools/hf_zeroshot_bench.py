#!/usr/bin/env python3
"""HF-transformers zero-shot bench for exotic-architecture models (Ouro looped etc.)
that neither vLLM nor llama.cpp can serve. Same Money Bench protocol."""
import argparse, json, os, statistics, sys, time
from pathlib import Path

os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import money_bench_v5 as mb
from rsi_night_loop import cad_eval, judge, speed_price, ACCEPT

RESULTS = HERE.parent / 'runs' / 'local_bench'


def run_session(model, tokenizer, sess_dir, tag):
    sess_dir.mkdir(parents=True, exist_ok=True)
    import torch
    capital, rounds = {}, []
    total = 0.0
    for rd in range(5):
        demand = mb.DEMANDS[rd]
        best = None
        for att in range(2):
            user = json.dumps({'demand': demand,
                               'capital': [{'id': k, 'desc': v.get('description', '')} for k, v in capital.items()],
                               'hint': 'Use capital(asset_id) to import previous modules.' if capital else None})
            prompt = tokenizer.apply_chat_template([{'role': 'system', 'content': mb.SYSTEM},
                                                    {'role': 'user', 'content': user}],
                                                   tokenize=False, add_generation_prompt=True)
            ids = tokenizer(prompt, return_tensors='pt', truncation=True, max_length=3600).to(model.device)
            t0 = time.monotonic()
            with torch.no_grad():
                out = model.generate(**ids, max_new_tokens=3000, temperature=0.3, do_sample=True,
                                     top_p=0.95, pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id)
            text = tokenizer.decode(out[0][ids['input_ids'].shape[1]:], skip_special_tokens=True).strip()
            secs = round(time.monotonic() - t0, 1)
            # strip think blocks / fences
            import re
            text = re.sub(r'<think>.*?</think>', '', text, flags=re.S).strip()
            if text.startswith('```') and text.count('```') >= 2:
                lines = text.split('\n')
                if len(lines) >= 3:
                    text = '\n'.join(lines[1:-1]).strip() or text
            if '"h":' in text and '"hypothesis":' not in text:
                text = text.replace('"h":', '"hypothesis":')
            if len(text) < 40:
                continue
            cad = cad_eval(text, capital, sess_dir / f'r{rd}_a{att}', (420, 280))
            if cad.get('metrics'):
                best = (text, secs, cad)
                break
        if best is None:
            rounds.append({'rd': rd, 'rating': 0, 'sold': False, 'rev': 0, 'reused': False, 'secs': 0})
            print(f"  R{rd+1}: ✗", flush=True)
            continue
        text, secs, cad = best
        rating = judge(demand, text, cad.get('metrics'))
        sold = rating >= ACCEPT
        rev = round(100 * speed_price(secs)) if sold else 0
        total += rev
        try:
            reused = any(n.get('op') == 'capital' for n in json.loads(text).get('nodes', []))
        except Exception:
            reused = False
        if sold or rating >= 3:
            capital[f'r{rd+1}'] = {'status': 'EXECUTED_CAD', 'step_path': cad['step_path'],
                                   'description': f'Round {rd+1} design', 'measurements': {}}
        rounds.append({'rd': rd, 'rating': rating, 'sold': sold, 'rev': rev, 'reused': reused, 'secs': secs})
        print(f"  R{rd+1}: {'✅' if sold else '❌'} {rating}/10 {secs:.0f}s ¥{rev}", flush=True)
    return {'profit': total, 'rounds': rounds,
            'sold': f"{sum(1 for r in rounds if r['sold'])}/5",
            'reuse': f"{sum(1 for r in rounds if r.get('reused'))}/4"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', required=True)
    ap.add_argument('--tag', required=True)
    ap.add_argument('--n', type=int, default=3)
    ap.add_argument('--adapter', default=None)
    a = ap.parse_args()
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM
    tok = AutoTokenizer.from_pretrained(a.repo, trust_remote_code=True)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    import os
    if os.environ.get('HFZ_MATCH_TRAIN'):  # exact worker loading path (shape-parity for bnb prequants)
        model = AutoModelForCausalLM.from_pretrained(a.repo, device_map='cuda', trust_remote_code=True)
    else:
        model = AutoModelForCausalLM.from_pretrained(a.repo, dtype=torch.bfloat16, device_map='cuda',
                                                     trust_remote_code=True)
    if a.adapter:
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, a.adapter)
        print(f'adapter: {a.adapter}')
    model.eval()
    runs = []
    for i in range(a.n):
        print(f"\n=== [{a.tag}] session {i+1}/{a.n} ===", flush=True)
        r = run_session(model, tok, RESULTS / f'{a.tag}-zs-hf' / f'sess{i+1}', a.tag)
        runs.append(r)
        print(f"  => ¥{r['profit']}", flush=True)
    out = RESULTS / f'{a.tag}-zeroshot_all_runs.json'
    out.write_text(json.dumps(runs, ensure_ascii=False, indent=2))
    ps = [r['profit'] for r in runs]
    print(f"\n{a.tag}: n={a.n} mean {statistics.mean(ps):.0f} runs={ps}")


if __name__ == '__main__':
    main()
