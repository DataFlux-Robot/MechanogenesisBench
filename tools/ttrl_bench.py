#!/usr/bin/env python3
"""TTRL: Test-Time Reinforcement Learning for Money Bench.

Unlike JitRL (which only modulates logits via memory), TTRL actually UPDATES
LoRA weights during the bench session. Each round:
  1. Sample N candidates
  2. Execute ALL in real CAD (ground-truth reward, no judge needed)
  3. Online GRPO update of LoRA weights using execution rewards
  4. Next round uses the UPDATED weights

The model gets better AT THE TASK while being evaluated on it.

Key advantage over original TTRL (majority voting pseudo-rewards): our CAD
execution provides ground-truth rewards, not noisy consensus.

Usage: MIMO_KEY=... python tools/ttrl_bench.py --sessions 5
"""
import argparse, json, os, random, statistics, sys, time, re
from pathlib import Path

os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
HERE = Path(__file__).resolve().parent
BENCH = HERE.parent
sys.path.insert(0, str(HERE))
import money_bench_v5 as mb
from rsi_night_loop import cad_eval, judge, speed_price, ACCEPT

BASE = '/home/exuber/models/qwen3.5-9b-bf16'
INIT_ADAPTER = '/home/exuber/models/prsi_rl_v3/iter6'  # V1.0 starting point
RESULTS = BENCH / 'runs' / 'ttrl'
N_CAND = 4  # candidates per round for GRPO signal


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sessions', type=int, default=5)
    ap.add_argument('--lr', type=float, default=2e-6, help='low LR for test-time stability')
    a = ap.parse_args()

    import torch
    import torch.nn.functional as F
    from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
    from peft import PeftModel

    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / 'cad').mkdir(exist_ok=True)
    tok = AutoTokenizer.from_pretrained(BASE, trust_remote_code=True)
    if tok.pad_token is None: tok.pad_token = tok.eos_token
    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4',
                             bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True)
    model = AutoModelForCausalLM.from_pretrained(BASE, quantization_config=bnb,
                                                 device_map='cuda', trust_remote_code=True)
    model = PeftModel.from_pretrained(model, INIT_ADAPTER, is_trainable=True)
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant': False})
    model.config.use_cache = False
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=a.lr)
    model.print_trainable_parameters()

    def gen_and_maybe_train(demand, capital, do_train=True):
        """Sample N candidates, CAD-execute all, optionally GRPO-update weights."""
        user = json.dumps({'demand': demand,
                           'capital': [{'id': k, 'desc': v.get('description', '')} for k, v in capital.items()],
                           'hint': 'Use capital(asset_id) to import previous modules.' if capital else None})
        prompt = tok.apply_chat_template(
            [{'role': 'system', 'content': mb.SYSTEM}, {'role': 'user', 'content': user}],
            tokenize=False, add_generation_prompt=True, enable_thinking=False)
        ids_base = tok(prompt, return_tensors='pt', truncation=True, max_length=3500)

        candidates = []
        model.eval()
        for j in range(N_CAND):
            torch.manual_seed(42 + j + len(candidates))
            t0 = time.monotonic()
            with torch.no_grad():
                ids = {k: v.to(model.device) for k, v in ids_base.items()}
                out = model.generate(**ids, max_new_tokens=1500, temperature=0.7,
                                     do_sample=True, top_p=0.95,
                                     pad_token_id=tok.pad_token_id)
            text = tok.decode(out[0][ids['input_ids'].shape[1]:], skip_special_tokens=True).strip()
            text = re.sub(r'<think>.*?</think>', '', text, flags=re.S).strip()
            if '"h":' in text and '"hypothesis":' not in text:
                text = text.replace('"h":', '"hypothesis":')
            secs = round(time.monotonic() - t0, 1)
            if len(text) > 40:
                candidates.append({'text': text, 'secs': secs, 'j': j})

        if not candidates:
            return None, 0

        # Execute ALL candidates in CAD (ground-truth reward)
        for c in candidates:
            cad = cad_eval(c['text'], capital, RESULTS / 'cad' / f"r{len(os.listdir(RESULTS / 'cad'))}_{c['j']}", (420, 280))
            valid = bool(cad.get('metrics'))
            # Execution reward: valid design that fits desk = high reward
            # This is GROUND TRUTH, not pseudo-reward
            if valid:
                metrics = cad.get('metrics', {})
                overlap = metrics.get('overlap_mm3', 0)
                excess = metrics.get('occupied_envelope_excess_mm', 0)
                # Composite execution reward: validity + low overlap + low excess + speed
                exec_reward = 1.0  # base for valid
                exec_reward -= min(0.5, overlap / 10000.0)  # penalize overlap
                exec_reward -= min(0.3, excess / 100.0)  # penalize envelope excess
                exec_reward += min(0.2, 30.0 / max(c['secs'], 1) * 0.2)  # speed bonus
                c['reward'] = max(0.0, exec_reward)
                c['valid'] = True
                c['cad'] = cad
            else:
                c['reward'] = 0.0
                c['valid'] = False
                c['cad'] = None

        # Pick best candidate for this round (highest execution reward)
        valid_pool = [c for c in candidates if c['valid']]
        best = max(valid_pool or candidates, key=lambda c: c['reward'])

        # GRPO update using execution rewards (this IS test-time RL)
        if do_train and len(candidates) >= 2:
            rewards = [c['reward'] for c in candidates]
            r_mean = statistics.mean(rewards)
            r_sd = statistics.pstdev(rewards)
            if r_sd > 1e-6:
                model.train()
                for c in candidates:
                    adv = (c['reward'] - r_mean) / r_sd
                    adv = max(-2, min(2, adv))
                    f_ids = tok(prompt + c['text'], add_special_tokens=False,
                                return_tensors='pt', truncation=True, max_length=2200)['input_ids'].to(model.device)
                    p_len = len(tok(prompt, add_special_tokens=False)['input_ids'])
                    if p_len >= f_ids.shape[1] or f_ids.shape[1] < 20:
                        continue
                    logits = model(input_ids=f_ids).logits[0, :-1]
                    targets = f_ids[0, 1:]
                    lps = []
                    for i in range(0, targets.shape[0], 512):
                        lg = logits[i:i+512].float()
                        lp = F.log_softmax(lg, dim=-1).gather(1, targets[i:i+512].unsqueeze(1)).squeeze(1)
                        lps.append(lp)
                    lp = torch.cat(lps)
                    mask = torch.zeros_like(lp); mask[p_len-1:] = 1.0
                    loss = -(adv * (lp * mask).sum() / mask.sum().clamp(min=1))
                    opt.zero_grad(); loss.backward(); opt.step()
                model.eval()

        return best, len(candidates)

    all_runs = []
    for si in range(a.sessions):
        sess_dir = RESULTS / f'sess{si+1}'
        sess_dir.mkdir(parents=True, exist_ok=True)
        capital, rounds = {}, []
        total = 0.0
        total_cad = 0
        print(f"\n=== [TTRL] session {si+1}/{a.sessions} ===", flush=True)
        for rd in range(5):
            demand = mb.DEMANDS[rd]
            best, n_cand = gen_and_maybe_train(demand, capital, do_train=True)
            total_cad += n_cand
            if best is None or not best.get('valid'):
                rounds.append({'rd': rd, 'rating': 0, 'sold': False, 'rev': 0, 'secs': 0})
                print(f"  R{rd+1}: ✗ no valid (from {n_cand} candidates)", flush=True)
                continue
            # Judge the best design
            rating = judge(demand, best['text'], best['cad'].get('metrics'))
            sold = rating >= ACCEPT
            rev = round(100 * speed_price(best['secs'])) if sold else 0
            total += rev
            try:
                reused = any(n.get('op') == 'capital' for n in json.loads(best['text']).get('nodes', []))
            except: reused = False
            if sold or rating >= 3:
                capital[f'r{rd+1}'] = {'status': 'EXECUTED_CAD', 'step_path': best['cad']['step_path'],
                                       'description': f'Round {rd+1} design', 'measurements': {}}
            rounds.append({'rd': rd, 'rating': rating, 'sold': sold, 'rev': rev,
                           'reused': reused, 'secs': best['secs'],
                           'exec_reward': best.get('reward'), 'n_candidates': n_cand})
            print(f"  R{rd+1}: {'✅' if sold else '❌'} {rating}/10 {'♻️' if reused else '🔧'} "
                  f"{best['secs']:.0f}s ¥{rev} | exec={best.get('reward',0):.2f} | {n_cand}cand",
                  flush=True)
        run = {'profit': total, 'rounds': rounds, 'cad_execs': total_cad,
               'sold': f"{sum(1 for r in rounds if r['sold'])}/5",
               'reuse': f"{sum(1 for r in rounds if r.get('reused'))}/4"}
        all_runs.append(run)
        print(f"  => ¥{total} | sold {run['sold']} | CAD execs {total_cad}", flush=True)

    profits = [r['profit'] for r in all_runs]
    print(f"\n[TTRL] profit mean ¥{statistics.mean(profits):.0f} runs={[round(p) for p in profits]}")
    # Save updated weights (the model improved during testing!)
    model.save_pretrained(str(RESULTS / 'ttrl_final_adapter'))
    print(f"Updated adapter saved -> {RESULTS / 'ttrl_final_adapter'}")
    (RESULTS / 'results.json').write_text(json.dumps(all_runs, indent=2))


if __name__ == '__main__':
    main()
