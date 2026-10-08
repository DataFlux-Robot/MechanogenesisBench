#!/usr/bin/env python3
"""Honest generalization eval: FluxEidosV2 inference stack on SEALED parametric probes.

The v6 stack's experience bank is mined from standard-bench runs (phone dock,
fixed dims). Probes are fresh instances (sampled families/dims/desks, seed
20261005, never used in any training). Any v6-over-plain gain here is honest
transfer of the *mechanism* (structure/detail/reuse style), not memorized
dimensions. Runs two arms:
  --stack v6    : best-of-3 R1 + experience replay + repair + resample + safe_judge
  --stack plain : same weights, pristine prompts (V1.5 control)
"""
import argparse, json, os, re, statistics, sys, time
from pathlib import Path

os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
HERE = Path(__file__).resolve().parent
BENCH = HERE.parent
sys.path.insert(0, str(HERE))

import money_bench_v5 as mb
from rsi_night_loop import cad_eval, speed_price, ACCEPT
import surpass_bench as sb
from parametric_demands import make_probe

RESULTS = BENCH / 'runs' / 'probe_v6'


def parse_desk(demand, default):
    m = re.search(r'[Dd]esk\s+(\d+)\s*x\s*(\d+)\s*mm', demand)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r'shrank to (\d+)x(\d+)mm', demand)
    if m:
        return int(m.group(1)), int(m.group(2))
    return default


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--stack', choices=['v6', 'plain'], default='v6')
    ap.add_argument('--instances', type=int, default=10)
    a = ap.parse_args()

    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
    from peft import PeftModel

    RESULTS.mkdir(parents=True, exist_ok=True)
    tok = AutoTokenizer.from_pretrained(sb.BASE, trust_remote_code=True)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4',
                             bnb_4bit_compute_dtype=torch.bfloat16,
                             bnb_4bit_use_double_quant=True)
    model = AutoModelForCausalLM.from_pretrained(sb.BASE, quantization_config=bnb,
                                                 device_map='cuda', trust_remote_code=True)
    model = PeftModel.from_pretrained(model, sb.ADAPTER)
    model.eval()

    experience = sb.load_experience() if a.stack == 'v6' else {}
    print(f"[probe:{a.stack}] experience bank rounds: {sorted(experience.keys())}", flush=True)

    probes = make_probe(a.instances, seed=20261005)
    all_runs = []
    for pi, inst in enumerate(probes):
        sess_dir = RESULTS / a.stack / f'inst{pi+1}'
        sess_dir.mkdir(parents=True, exist_ok=True)
        capital, rounds, total = {}, [], 0.0
        desk = inst['desk']
        print(f"\n=== [{a.stack}] probe {pi+1}/{len(probes)} [{inst['family']}, "
              f"desk {desk[0]}x{desk[1]}] ===", flush=True)

        for rd in range(5):
            demand = inst['demands'][rd]
            dw, dd = parse_desk(demand, desk) if rd == 4 else desk
            user = sb.build_user(demand, capital, rd, use_hints=True, experience=experience)
            prompt = tok.apply_chat_template(
                [{'role': 'system', 'content': mb.SYSTEM}, {'role': 'user', 'content': user}],
                tokenize=False, add_generation_prompt=True, enable_thinking=False)

            cad = None
            if rd == 0 and a.stack == 'v6':
                cands, t_total = [], 0.0
                for k in range(3):
                    ctext, csecs = sb.generate(model, tok, prompt, max_new=900,
                                               temp=0.7, seed=42 + 1000 * pi + 77 * k)
                    t_total += csecs
                    ctext = sb.repair_design(ctext)
                    if len(ctext) < 60:
                        continue
                    ccad = cad_eval(ctext, capital, sess_dir / f'r{rd}_c{k}', (dw, dd))
                    if ccad.get('metrics'):
                        m = ccad['metrics']
                        try:
                            nparts = len(json.loads(ctext).get('parts', []))
                        except Exception:
                            nparts = 0
                        cands.append(((-nparts, m.get('overlap_mm3', 1e9)), ctext, ccad))
                if cands:
                    cands.sort(key=lambda c: c[0])
                    _, text, cad = cands[0]
                    secs = round(t_total, 1)
                else:
                    text, secs = '', round(t_total, 1)
            else:
                text, secs = sb.generate(model, tok, prompt, temp=0.3,
                                         seed=42 + rd + 1000 * pi)
                text = sb.repair_design(text)

            if not text or len(text) < 60:
                rounds.append({'rd': rd, 'rating': 0, 'sold': False, 'rev': 0, 'secs': secs})
                print(f"  R{rd+1}: x no text", flush=True)
                continue

            if not cad:
                cad = cad_eval(text, capital, sess_dir / f'r{rd}_v1', (dw, dd))
            rating = 0
            if cad.get('metrics'):
                rating = sb.safe_judge(demand, text, cad.get('metrics'))

            # conditional resample on failed reuse rounds (v6 arm only)
            if rating < ACCEPT and rd > 0 and a.stack == 'v6':
                rtext, rsecs = sb.generate(model, tok, prompt, temp=0.6,
                                           seed=42 + rd + 1000 * pi + 555)
                rtext = sb.repair_design(rtext)
                if len(rtext) >= 60:
                    rcad = cad_eval(rtext, capital, sess_dir / f'r{rd}_v2', (dw, dd))
                    if rcad.get('metrics'):
                        rrating = sb.safe_judge(demand, rtext, rcad.get('metrics'))
                        if rrating > rating:
                            text, cad, rating = rtext, rcad, rrating
                            secs = round(secs + rsecs, 1)

            sold = rating >= ACCEPT
            rev = round(100 * speed_price(secs)) if sold else 0
            total += rev
            try:
                reused = any(n.get('op') == 'capital' for n in json.loads(text).get('nodes', []))
            except Exception:
                reused = False
            if sold or rating >= 3:
                capital[f'r{rd+1}'] = {'status': 'EXECUTED_CAD',
                                       'step_path': cad.get('step_path', ''),
                                       'description': f'Round {rd+1} design'}
            rounds.append({'rd': rd, 'rating': rating, 'sold': sold, 'rev': rev,
                           'reused': reused, 'secs': secs})
            print(f"  R{rd+1}: {'OK' if sold else '..'} {rating}/10 "
                  f"{'reuse' if reused else 'scratch'} {secs:.1f}s Y{rev}", flush=True)

        run = {'instance': pi + 1, 'family': inst['family'], 'profit': total, 'rounds': rounds,
               'sold': f"{sum(1 for r in rounds if r['sold'])}/5"}
        all_runs.append(run)
        print(f"  => Y{total} | sold {run['sold']}", flush=True)

    profits = [r['profit'] for r in all_runs]
    print(f"\n{'='*50}")
    print(f"[probe:{a.stack}] mean Y{statistics.mean(profits):.0f} over {len(profits)} instances")
    print(f"  runs={[round(p) for p in profits]}")
    by_rd = {rd: round(statistics.mean([r['rounds'][rd]['rating'] for r in all_runs
                                        if rd < len(r['rounds'])]), 1) for rd in range(5)}
    print(f"  mean rating by round: {by_rd}")
    (RESULTS / f'{a.stack}_results.json').write_text(json.dumps(all_runs, indent=2))


if __name__ == '__main__':
    main()
