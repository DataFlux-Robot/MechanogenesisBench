#!/usr/bin/env python3
"""Supervised SFT via the chunked-loss RL worker (fits 27B-4bit on 24GB).

Each epoch is one worker subprocess over all samples with adv=+1.0, which makes
the policy-gradient loss exactly the CE loss. Model reload per epoch (~4 min
overhead) is accepted for guaranteed memory safety.
"""
import json, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BENCH = HERE.parent
BASE = '/home/exuber/models/qwen38-27b-bnb4'
OUT = Path('/home/exuber/models/prsi_lora_q38/worker_sft')
EPOCHS = 8
LR = 8e-5
MAX_LEN = 1750

examples = [json.loads(l) for l in (BENCH / 'runs' / 'training_data' / 'sft_v3_train.jsonl').read_text().splitlines() if l.strip()]
from transformers import AutoTokenizer
tok = AutoTokenizer.from_pretrained(BASE, trust_remote_code=True)

samples = []
for e in examples:
    pr = tok.apply_chat_template(e['messages'][:2], tokenize=False, add_generation_prompt=True, enable_thinking=False)
    samples.append({'prompt': pr, 'text': e['messages'][2]['content'], 'adv': 1.0})
print(f'{len(samples)} samples, {EPOCHS} epochs', flush=True)

OUT.mkdir(parents=True, exist_ok=True)
adapter = 'none'  # first epoch starts from the raw base
TARGETS = r'.*\.(self_attn\.(q_proj|k_proj|v_proj|o_proj)|linear_attn\.(in_proj_qkv|out_proj))$'
t0 = time.time()
for ep in range(1, EPOCHS + 1):
    out_a = str(OUT / f'epoch{ep}')
    job = {'adapter': adapter, 'out_adapter': out_a, 'samples': samples, 'lora_targets': TARGETS,
           'core_path': str(BENCH / 'runs' / 'training_data' / 'sft_v2_core.jsonl'), 'lr': LR, 'anchor_w': 0.0, 'max_len': MAX_LEN}
    jf = OUT / f'job_ep{ep}.json'
    jf.write_text(json.dumps(job))
    r = subprocess.run([sys.executable, '-W', 'ignore', str(HERE / 'rl_train_step_worker.py'), str(jf)],
                       capture_output=True, text=True, timeout=7200)
    line = [l for l in r.stdout.splitlines() if '"status"' in l]
    if not line:
        print(f'epoch {ep} FAILED: {(r.stderr or r.stdout)[-300:]}'); sys.exit(1)
    st = json.loads(line[-1])
    print(f'epoch {ep}: pg(CE)={st["pg"]:.4f} over {st["n_pg"]} [{(time.time()-t0)/60:.0f}min]', flush=True)
    adapter = out_a
print('DONE ->', adapter)
