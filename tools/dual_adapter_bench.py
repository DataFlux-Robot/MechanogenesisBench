#!/usr/bin/env python3
"""Dual-adapter Money Bench: generation (CARE-v3) + prediction screening (CAD World Model).

Pipeline per round:
  1. GENERATE: sample N candidates using the generation adapter (FluxEidosV1.0)
  2. PREDICT: score each candidate using the prediction adapter (CAD world model)
  3. SELECT: pick the candidate with highest predicted rating
  4. EXECUTE: run real build123d CAD on ONLY the selected candidate
  5. JUDGE: LLM judge on the executed design

This saves CAD executions (N-1 of N skipped) and picks better candidates.
Both adapters share the same Qwen3.5-9B base — loaded once, switched via PEFT.

Usage (dd_qwen9b venv):
  MIMO_KEY=... python tools/dual_adapter_bench.py --n-candidates 4 --sessions 5
"""
import argparse, json, os, statistics, sys, time, re
from pathlib import Path

os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import money_bench_v5 as mb
from rsi_night_loop import cad_eval, judge, speed_price, ACCEPT

BASE = '/home/exuber/models/qwen3.5-9b-bf16'
GEN_ADAPTER = '/home/exuber/models/prsi_rl_v3/iter6'      # FluxEidosV1.0-9B
PRED_ADAPTER = '/home/exuber/models/prsi_cwm_pred/epoch5'  # CAD world model
RESULTS = HERE.parent / 'runs' / 'dual_adapter'

PREDICT_SYS = '''You are a CAD geometry oracle. Given a workstation CSG design JSON, predict what build123d will compute when it executes this design. Return ONLY JSON:
{"valid": <true|false>, "overlap_mm3": <float>, "envelope_excess_mm": <float>, "rating": <0-10>}'''


def parse_json_out(t):
    t = re.sub(r'<think>.*?</think>', '', t, flags=re.S).strip()
    if t.startswith('```') and t.count('```') >= 2:
        lines = t.split('\n')
        if len(lines) >= 3: t = '\n'.join(lines[1:-1]).strip()
    i, j = t.find('{'), t.rfind('}')
    if i >= 0 and j > i:
        try: return json.loads(t[i:j+1])
        except: return None
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n-candidates', type=int, default=4, help='candidates per round')
    ap.add_argument('--sessions', type=int, default=5)
    ap.add_argument('--screen', action='store_true', help='use prediction screening (off = control)')
    a = ap.parse_args()

    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
    from peft import PeftModel

    RESULTS.mkdir(parents=True, exist_ok=True)
    tok = AutoTokenizer.from_pretrained(BASE, trust_remote_code=True)
    if tok.pad_token is None: tok.pad_token = tok.eos_token
    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4',
                             bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True)
    print("Loading base + both adapters...", flush=True)
    model = AutoModelForCausalLM.from_pretrained(BASE, quantization_config=bnb,
                                                 device_map='cuda', trust_remote_code=True)
    # Load both adapters; default active = generation
    model = PeftModel.from_pretrained(model, GEN_ADAPTER, adapter_name='gen')
    model.load_adapter(PRED_ADAPTER, adapter_name='pred')
    model.set_adapter('gen')
    model.eval()
    print("Both adapters loaded (gen + pred)", flush=True)

    tag = f"screen{a.n_candidates}" if a.screen else f"control{a.n_candidates}"
    all_runs = []
    for si in range(a.sessions):
        sess_dir = RESULTS / tag / f'sess{si+1}'
        sess_dir.mkdir(parents=True, exist_ok=True)
        capital, rounds = {}, []
        total = 0.0
        cad_execs = 0
        print(f"\n=== [{tag}] session {si+1}/{a.sessions} ===", flush=True)
        for rd in range(5):
            demand = mb.DEMANDS[rd]
            user = json.dumps({'demand': demand,
                               'capital': [{'id': k, 'desc': v.get('description', '')} for k, v in capital.items()],
                               'hint': 'Use capital(asset_id) to import previous modules.' if capital else None})
            gen_prompt = tok.apply_chat_template(
                [{'role': 'system', 'content': mb.SYSTEM}, {'role': 'user', 'content': user}],
                tokenize=False, add_generation_prompt=True, enable_thinking=False)

            candidates = []
            model.set_adapter('gen')
            for ci in range(a.n_candidates):
                ids = tok(gen_prompt, return_tensors='pt', truncation=True, max_length=3600).to(model.device)
                t0 = time.monotonic()
                torch.manual_seed(42 + ci)
                with torch.no_grad():
                    out = model.generate(**ids, max_new_tokens=2000, temperature=0.4,
                                         do_sample=True, top_p=0.95,
                                         pad_token_id=tok.pad_token_id)
                text = tok.decode(out[0][ids['input_ids'].shape[1]:], skip_special_tokens=True).strip()
                secs = round(time.monotonic() - t0, 1)
                if '"h":' in text and '"hypothesis":' not in text:
                    text = text.replace('"h":', '"hypothesis":')
                if len(text) > 60:
                    candidates.append({'text': text, 'secs': secs, 'ci': ci})

            if not candidates:
                rounds.append({'rd': rd, 'rating': 0, 'sold': False, 'rev': 0, 'secs': 0})
                print(f"  R{rd+1}: ✗ no candidates", flush=True); continue

            # SCREEN: use prediction adapter to pick the best candidate
            if a.screen and len(candidates) > 1:
                model.set_adapter('pred')
                for c in candidates:
                    pp = tok.apply_chat_template(
                        [{'role': 'system', 'content': PREDICT_SYS}, {'role': 'user', 'content': c['text'][:3500]}],
                        tokenize=False, add_generation_prompt=True, enable_thinking=False)
                    ids = tok(pp, return_tensors='pt', truncation=True, max_length=3600).to(model.device)
                    with torch.no_grad():
                        out = model.generate(**ids, max_new_tokens=120, do_sample=False,
                                             pad_token_id=tok.pad_token_id)
                    pt = tok.decode(out[0][ids['input_ids'].shape[1]:], skip_special_tokens=True)
                    pred = parse_json_out(pt) or {}
                    c['pred_valid'] = pred.get('valid', False)
                    c['pred_rating'] = pred.get('rating', 0)
                # pick highest predicted rating among predicted-valid candidates
                valid_pool = [c for c in candidates if c.get('pred_valid')]
                pool = valid_pool if valid_pool else candidates
                best = max(pool, key=lambda c: c.get('pred_rating', 0))
                model.set_adapter('gen')
            else:
                best = candidates[0]  # control: first candidate

            # EXECUTE: only the selected candidate goes to real CAD
            cad = cad_eval(best['text'], capital, sess_dir / f'r{rd}_best', (420, 280))
            cad_execs += 1
            if not cad.get('metrics'):
                rounds.append({'rd': rd, 'rating': 0, 'sold': False, 'rev': 0, 'secs': best['secs']})
                print(f"  R{rd+1}: ✗ CAD failed (screened pick)", flush=True); continue

            rating = judge(demand, best['text'], cad.get('metrics'))
            sold = rating >= ACCEPT
            rev = round(100 * speed_price(best['secs'])) if sold else 0
            total += rev
            try:
                reused = any(n.get('op') == 'capital' for n in json.loads(best['text']).get('nodes', []))
            except: reused = False
            if sold or rating >= 3:
                capital[f'r{rd+1}'] = {'status': 'EXECUTED_CAD', 'step_path': cad['step_path'],
                                       'description': f'Round {rd+1} design', 'measurements': {}}
            rounds.append({'rd': rd, 'rating': rating, 'sold': sold, 'rev': rev,
                           'reused': reused, 'secs': best['secs'],
                           'pred_rating': best.get('pred_rating'), 'n_candidates': len(candidates)})
            print(f"  R{rd+1}: {'✅' if sold else '❌'} {rating}/10 {'♻️' if reused else '🔧'} "
                  f"{best['secs']:.0f}s ¥{rev} | pred={best.get('pred_rating','?')} | {len(candidates)}cand {cad_execs}exec",
                  flush=True)
        run = {'profit': total, 'rounds': rounds, 'cad_execs': cad_execs,
               'sold': f"{sum(1 for r in rounds if r['sold'])}/5",
               'reuse': f"{sum(1 for r in rounds if r.get('reused'))}/4"}
        all_runs.append(run)
        print(f"  => ¥{total} | sold {run['sold']} | CAD execs: {cad_execs}/5 rounds", flush=True)

    profits = [r['profit'] for r in all_runs]
    execs = [r['cad_execs'] for r in all_runs]
    print(f"\n[{tag}] profit mean ¥{statistics.mean(profits):.0f} runs={[round(p) for p in profits]}")
    print(f"[{tag}] CAD execs per session: {execs} (vs {5*a.n_candidates} without screening)")
    (RESULTS / f'{tag}_results.json').write_text(json.dumps(all_runs, indent=2))


if __name__ == '__main__':
    main()
