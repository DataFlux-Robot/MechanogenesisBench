#!/usr/bin/env python3
"""GAR-RL v2: MiMo-style Groupwise Advantage Redistribution with HF direct inference.

Eliminates vLLM server entirely — uses transformers.generate() directly for rollouts.
Slower per-token but zero server management = zero infrastructure failures.

NO SFT from other models. Pure RL from self-generated rollouts.
"""
import argparse, json, os, random, statistics, subprocess, sys, time, re
from collections import defaultdict
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
HERE = Path(__file__).resolve().parent
BENCH = HERE.parent
sys.path.insert(0, str(HERE))
import money_bench_v5 as mb
from rsi_night_loop import cad_eval, judge, speed_price, ACCEPT
import parametric_demands as PD

BASE = '/home/exuber/models/qwen3.5-9b-bf16'
CKPT = Path('/home/exuber/models/prsi_gar2')
OUT = BENCH / 'runs' / 'gar_rl2'
N_CAND = 4  # candidates per prompt (fewer = faster with HF inference)
N_PROMPTS = 4


def build_prompts(rng):
    def msg(demand, capital):
        return json.dumps({'demand': demand,
                           'capital': [{'id': k, 'desc': v} for k, v in capital.items()],
                           'hint': 'Use capital(asset_id) to import previous modules.' if capital else None})

    sess = BENCH / 'runs' / 'control_experiments' / 'glm-5.3-flash' / 'treatment_20261003_145642'
    def cap_upto(n):
        c = {}
        for rd in range(n):
            for att in ('a0', 'a1'):
                p = sess / f'r{rd}_{att}' / 'cad' / 'design.step'
                if p.exists():
                    c[f'r{rd+1}'] = {'status': 'EXECUTED_CAD', 'step_path': str(p),
                                     'description': f'Round {rd+1} design', 'measurements': {}}
                    break
        return c

    instA, instB = PD.sample_train(rng), PD.sample_train(rng)
    return [
        {'op': 'draft', 'demand': instA['demands'][0], 'desk': instA['desk'], 'capital': {},
         'user': msg(instA['demands'][0], {})},
        {'op': 'draft', 'demand': instB['demands'][0], 'desk': instB['desk'], 'capital': {},
         'user': msg(instB['demands'][0], {})},
        {'op': 'improve', 'demand': instB['demands'][2], 'desk': instB['desk'], 'capital': cap_upto(2),
         'user': msg(instB['demands'][2], cap_upto(2))},
        {'op': 'improve', 'demand': instA['demands'][4], 'desk': instA['desk'], 'capital': cap_upto(4),
         'user': msg(instA['demands'][4], cap_upto(4))},
    ]


def gar_advantages(samples):
    """MiMo GAR: rank passing designs by quality, redistribute advantage."""
    groups = defaultdict(list)
    for s in samples:
        groups[s['ci']].append(s)
    train_samples = []
    for ci, ss in groups.items():
        R = [1.0 if s['rw']['sold'] else 0.0 for s in ss]
        R_bar = statistics.mean(R)
        A = [r - R_bar for r in R]
        P = [i for i, r in enumerate(R) if r == 1.0]
        if P:
            f = [max(0.1, ss[i]['rw'].get('quality', 0.5)) for i in P]
            fs = sum(f)
            pos_mass = sum(A[i] for i in P)
            for j, i in enumerate(P):
                A[i] = pos_mass * (f[j] / fs) * len(P)
        sd = statistics.pstdev(A)
        for i, s in enumerate(ss):
            adv = A[i] / sd if sd > 1e-6 else 0
            train_samples.append({'prompt': s['prompt'], 'text': s['text'],
                                  'adv': max(-2, min(2, adv))})
    return train_samples


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--iters', type=int, default=5)
    ap.add_argument('--init-adapter', default='/home/exuber/models/prsi_rl_v3/iter6')
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    CKPT.mkdir(parents=True, exist_ok=True)

    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
    from peft import PeftModel

    tok = AutoTokenizer.from_pretrained(BASE, trust_remote_code=True)
    if tok.pad_token is None: tok.pad_token = tok.eos_token

    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4',
                             bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True)
    model = AutoModelForCausalLM.from_pretrained(BASE, quantization_config=bnb,
                                                 device_map='cuda', trust_remote_code=True)
    if a.init_adapter:
        model = PeftModel.from_pretrained(model, a.init_adapter, is_trainable=True)
    else:
        from peft import LoraConfig, get_peft_model, TaskType
        model = get_peft_model(model, LoraConfig(
            task_type=TaskType.CAUSAL_LM, r=32, lora_alpha=64, lora_dropout=0.0,
            target_modules=['q_proj', 'k_proj', 'v_proj', 'o_proj']))
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant': False})
    model.config.use_cache = False
    model.print_trainable_parameters()

    rng = random.Random(888)
    adapter = a.init_adapter
    log = []

    for gen in range(1, a.iters + 1):
        t0 = time.time()
        print(f"\n===== GAR-RL gen {gen} =====", flush=True)

        # 1. ROLLOUT (HF direct inference — no server)
        model.eval()
        ctxs = build_prompts(rng)
        samples = []
        for ci, c in enumerate(ctxs):
            prompt = tok.apply_chat_template(
                [{'role': 'system', 'content': mb.SYSTEM}, {'role': 'user', 'content': c['user']}],
                tokenize=False, add_generation_prompt=True, enable_thinking=False)
            ids_base = tok(prompt, return_tensors='pt', truncation=True, max_length=3500)
            for j in range(N_CAND):
                torch.manual_seed(42 + ci * 10 + j + gen * 100)
                t_gen = time.monotonic()
                with torch.no_grad():
                    ids = {k: v.to(model.device) for k, v in ids_base.items()}
                    out = model.generate(**ids, max_new_tokens=1500, temperature=0.7,
                                         do_sample=True, top_p=0.95,
                                         pad_token_id=tok.pad_token_id)
                text = tok.decode(out[0][ids['input_ids'].shape[1]:], skip_special_tokens=True).strip()
                text = re.sub(r'<think>.*?</think>', '', text, flags=re.S).strip()
                if '"h":' in text and '"hypothesis":' not in text:
                    text = text.replace('"h":', '"hypothesis":')
                secs = round(time.monotonic() - t_gen, 1)
                samples.append({'ci': ci, 'op': c['op'], 'prompt': prompt,
                                'text': text, 'secs': secs, 'seed': j})
        valid_n = sum(1 for s in samples if len(s['text']) > 40)
        print(f"  rollout: {valid_n}/{len(samples)} non-empty", flush=True)

        # 2. SCORE (CAD + judge)
        import torch.nn.functional as F
        def score(s):
            c = ctxs[s['ci']]
            text = s['text']
            if len(text) < 40:
                s['rw'] = {'sold': False, 'valid': False, 'rating': 0, 'quality': 0}
                s['operator'] = c['op']; s['pi'] = s['ci']
                return s
            cad = cad_eval(text, c['capital'], OUT / f'gen{gen}' / f"p{s['ci']}_s{s['seed']}", c['desk'])
            valid = bool(cad.get('metrics'))
            if not valid:
                s['rw'] = {'sold': False, 'valid': False, 'rating': 0, 'quality': 0}
                s['operator'] = c['op']; s['pi'] = s['ci']
                return s
            rating = judge(c['demand'], text, cad.get('metrics'))
            sold = rating >= ACCEPT
            speed_eff = min(1.0, 30.0 / max(s['secs'], 1))
            quality = (rating / 10.0) * 0.7 + speed_eff * 0.3
            s['rw'] = {'sold': sold, 'valid': True, 'rating': rating, 'quality': round(quality, 4)}
            s['operator'] = c['op']; s['pi'] = s['ci']
            return s

        with ThreadPoolExecutor(max_workers=3) as ex:
            samples = list(ex.map(score, samples))
        sold_n = sum(1 for s in samples if s['rw']['sold'])
        valid_n = sum(1 for s in samples if s['rw']['valid'])
        print(f"  scored: {valid_n}/{len(samples)} valid, {sold_n}/{len(samples)} sold", flush=True)

        # 3. GAR advantages
        train_samples = gar_advantages(samples)
        if not train_samples:
            print("  no signal; skipping training"); continue

        # 4. TRAIN (in-process — no subprocess needed, model already loaded)
        model.train()
        opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=5e-6)
        random.shuffle(train_samples)
        n_trained = 0
        for s in train_samples[:16]:  # cap at 16 samples per gen for stability
            f_ids = tok(s['prompt'] + s['text'], add_special_tokens=False, return_tensors='pt',
                        truncation=True, max_length=2200)['input_ids'].to(model.device)
            if f_ids.shape[1] < 20 or f_ids.shape[1] >= 2200: continue
            p_len = len(tok(s['prompt'], add_special_tokens=False)['input_ids'])
            if p_len >= f_ids.shape[1]: continue
            with torch.no_grad():
                pass  # need gradients
            logits = model(input_ids=f_ids).logits[0, :-1]
            targets = f_ids[0, 1:]
            # chunked logprob
            lps = []
            for i in range(0, targets.shape[0], 512):
                lg = logits[i:i+512].float()
                lp = F.log_softmax(lg, dim=-1).gather(1, targets[i:i+512].unsqueeze(1)).squeeze(1)
                lps.append(lp)
            lp = torch.cat(lps)
            mask = torch.zeros_like(lp); mask[p_len-1:] = 1.0
            loss = -(s['adv'] * (lp * mask).sum() / mask.sum().clamp(min=1))
            opt.zero_grad(); loss.backward(); opt.step()
            n_trained += 1
        model.eval()
        print(f"  train: {n_trained} samples, lr=5e-6", flush=True)

        # 5. Save checkpoint
        ckpt = str(CKPT / f'gen{gen}')
        model.save_pretrained(ckpt)
        adapter = ckpt

        entry = {'gen': gen, 'valid': valid_n, 'sold': sold_n, 'n_trained': n_trained,
                'wall_min': round((time.time()-t0)/60, 1)}
        log.append(entry)
        (OUT / 'log.json').write_text(json.dumps(log, indent=2))
        print(f"  gen{gen}: {valid_n} valid, {sold_n} sold [{entry['wall_min']}min]", flush=True)

    print(f"\nGAR-RL v2 DONE: " + ' -> '.join(f"g{e['gen']}:{e['valid']}v/{e['sold']}s" for e in log))


if __name__ == '__main__':
    main()
