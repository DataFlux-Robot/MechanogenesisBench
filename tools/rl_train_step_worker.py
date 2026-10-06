#!/usr/bin/env python3
"""RL train-step worker: REINFORCE (group-normalized advantage) + SFT anchor.
Runs in its own process so GPU memory fully releases before the next vLLM server start.

Input JSON: {adapter, out_adapter, samples: [{prompt, text, adv}], core_path, lr, anchor_w, max_len}
"""
import json, random, statistics, sys
from pathlib import Path

os_env = __import__('os')
os_env.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
BASE = '/home/exuber/models/qwen3.5-9b-bf16'


def main():
    job = json.loads(Path(sys.argv[1]).read_text())
    import torch
    import torch.nn.functional as F
    from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
    from peft import PeftModel

    tok = AutoTokenizer.from_pretrained(BASE, trust_remote_code=True)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4',
                             bnb_4bit_compute_dtype=torch.bfloat16,
                             bnb_4bit_use_double_quant=True)
    model = AutoModelForCausalLM.from_pretrained(BASE, quantization_config=bnb,
                                                 device_map='cuda', trust_remote_code=True)
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant': False})
    model.config.use_cache = False
    if job.get('adapter') in (None, '', 'none'):
        from peft import LoraConfig, get_peft_model, TaskType
        _r = int(job.get('lora_r', 16))
        _tg = job.get('lora_targets') or ['q_proj', 'k_proj', 'v_proj', 'o_proj']
        model = get_peft_model(model, LoraConfig(task_type=TaskType.CAUSAL_LM, r=_r, lora_alpha=_r * 2,
                                                  lora_dropout=0.0, target_modules=_tg))
    else:
        model = PeftModel.from_pretrained(model, job['adapter'], is_trainable=True)
    model.train()

    def token_logp(logits, targets, p_len):
        outs, CH = [], 512
        for i in range(0, targets.shape[0], CH):
            lg = logits[i:i+CH].float()
            outs.append(F.log_softmax(lg, dim=-1).gather(1, targets[i:i+CH].unsqueeze(1)).squeeze(1))
        lp = torch.cat(outs)
        mask = torch.zeros_like(lp); mask[p_len-1:] = 1.0
        return lp, mask

    max_len = job.get('max_len', 2300)
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=job.get('lr', 3e-5))

    stats = {'pg': 0.0, 'n_pg': 0, 'ce': 0.0, 'n_ce': 0}
    samples = job['samples']
    random.seed(41); random.shuffle(samples)
    for s in samples:
        f_ids = tok(s['prompt'] + s['text'], add_special_tokens=False, return_tensors='pt',
                    truncation=True, max_length=max_len)['input_ids'].to(model.device)
        if f_ids.shape[1] < 20 or f_ids.shape[1] >= max_len:
            continue
        p_len = len(tok(s['prompt'], add_special_tokens=False)['input_ids'])
        if p_len >= f_ids.shape[1]:
            continue
        lp, mask = token_logp(model(input_ids=f_ids).logits[0, :-1], f_ids[0, 1:], p_len)
        loss = -(s['adv'] * (lp * mask).sum() / mask.sum().clamp(min=1))
        opt.zero_grad(); loss.backward(); opt.step()
        stats['pg'] += loss.item(); stats['n_pg'] += 1

    core = [json.loads(l) for l in Path(job['core_path']).read_text().splitlines() if l.strip()]
    if job.get('anchor_w', 0.3) > 0:
        for e in random.sample(core, min(8, len(core))):
            pr = tok.apply_chat_template(e['messages'][:2], tokenize=False, add_generation_prompt=True, enable_thinking=False)
            f_ids = tok(pr + e['messages'][2]['content'] + tok.eos_token, add_special_tokens=False,
                        return_tensors='pt', truncation=True, max_len=max_len)['input_ids'].to(model.device)
            p_len = len(tok(pr, add_special_tokens=False)['input_ids'])
            if p_len >= f_ids.shape[1]:
                continue
            lp, mask = token_logp(model(input_ids=f_ids).logits[0, :-1], f_ids[0, 1:], p_len)
            loss = -(lp * mask).sum() / mask.sum().clamp(min=1)
            opt.zero_grad(); (job.get('anchor_w', 0.3) * loss).backward(); opt.step()
            stats['ce'] += loss.item(); stats['n_ce'] += 1

    out = Path(job['out_adapter']); out.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(out))
    tok.save_pretrained(str(out))
    print(json.dumps({'status': 'ok', 'pg': stats['pg'] / max(stats['n_pg'], 1),
                      'n_pg': stats['n_pg'], 'ce': stats['ce'] / max(stats['n_ce'], 1),
                      'n_ce': stats['n_ce']}))


if __name__ == '__main__':
    main()
