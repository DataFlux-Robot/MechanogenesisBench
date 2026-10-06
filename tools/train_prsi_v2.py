#!/usr/bin/env python3
"""QLoRA v2: train on OpenRSI-style four-operator SFT data (sft_v2_train.jsonl).

Differences vs v1 (train_prsi.py):
  - messages-format data with operator tags (draft/improve/debug/crossover)
  - exact money_bench_v5 system prompt (train/eval parity)
  - assistant-only loss masking
  - cosine LR + more epochs on the small gated corpus
"""
import json, os, sys, time
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
from pathlib import Path

TRAIN_DATA = Path('/home/exuber/CODE/CORE/pythonProject1/AUTORESEARCH/MechanogenesisBench-upstream/runs/training_data')
MODEL_PATH = os.environ.get('PRSI_BASE', '/home/exuber/models/qwen3.5-9b-bf16')
OUTPUT_DIR = os.environ.get('PRSI_OUT', '/home/exuber/models/prsi_lora_v2')
MAX_LEN = int(os.environ.get("PRSI_MAX_LEN", "2048"))
EPOCHS = int(os.environ.get('PRSI_EPOCHS', '8'))
LR = float(os.environ.get('PRSI_LR', '1e-4'))


def main():
    import torch
    from torch.utils.data import Dataset
    from transformers import (AutoTokenizer, AutoModelForCausalLM, TrainingArguments,
                              Trainer, BitsAndBytesConfig)
    from peft import LoraConfig, get_peft_model, TaskType, prepare_model_for_kbit_training

    data_file = Path(os.environ.get('PRSI_DATA', str(TRAIN_DATA / 'sft_v2_train.jsonl')))
    examples = [json.loads(l) for l in data_file.read_text().splitlines() if l.strip()]
    print(f"training on {len(examples)} four-operator examples")
    from collections import Counter
    print("operators:", dict(Counter(e['operator'] for e in examples)))

    tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    if os.environ.get('PRSI_PREQUANT'):
        # already-4bit bnb checkpoint: load as-is (its config carries quantization_config)
        model = AutoModelForCausalLM.from_pretrained(MODEL_PATH, device_map="cuda",
                                                     trust_remote_code=True)
    else:
        bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                                 bnb_4bit_compute_dtype=torch.bfloat16,
                                 bnb_4bit_use_double_quant=True)
        model = AutoModelForCausalLM.from_pretrained(MODEL_PATH, quantization_config=bnb,
                                                     device_map="cuda", trust_remote_code=True)
    import os as _os
    _r = int(_os.environ.get("PRSI_LORA_R", "32"))
    lora = LoraConfig(task_type=TaskType.CAUSAL_LM, r=_r, lora_alpha=_r*2, lora_dropout=0.0,
                      target_modules=["q_proj", "k_proj", "v_proj", "o_proj"])
    model = prepare_model_for_kbit_training(model)
    model = get_peft_model(model, lora)
    model.print_trainable_parameters()

    class MsgDS(Dataset):
        def __init__(self, items):
            self.items = []
            for it in items:
                prompt = tokenizer.apply_chat_template(
                    it['messages'][:2], tokenize=False, add_generation_prompt=True, enable_thinking=False)
                full = prompt + it['messages'][2]['content'] + tokenizer.eos_token
                p_ids = tokenizer(prompt, add_special_tokens=False)['input_ids']
                f_ids = tokenizer(full, add_special_tokens=False)['input_ids']
                if len(f_ids) > MAX_LEN:
                    continue
                labels = [-100] * len(p_ids) + f_ids[len(p_ids):]
                self.items.append((f_ids, labels))

        def __len__(self):
            return len(self.items)

        def __getitem__(self, i):
            ids, labels = self.items[i]
            return {'input_ids': ids, 'labels': labels,
                    'attention_mask': [1] * len(ids)}

    ds = MsgDS(examples)
    print(f"tokenized: {len(ds)} (dropped {len(examples)-len(ds)} over {MAX_LEN} tokens)")

    def collate(batch):
        mx = max(len(b['input_ids']) for b in batch)
        pad = tokenizer.pad_token_id
        return {'input_ids': torch.tensor([b['input_ids'] + [pad] * (mx - len(b['input_ids'])) for b in batch]),
                'labels': torch.tensor([b['labels'] + [-100] * (mx - len(b['labels'])) for b in batch]),
                'attention_mask': torch.tensor([b['attention_mask'] + [0] * (mx - len(b['attention_mask'])) for b in batch])}

    out = Path(OUTPUT_DIR) / time.strftime('%Y%m%d_%H%M%S')
    args = TrainingArguments(
        output_dir=str(out), num_train_epochs=EPOCHS, per_device_train_batch_size=1,
        gradient_accumulation_steps=8, learning_rate=LR, lr_scheduler_type='cosine',
        warmup_steps=10, logging_steps=5, save_strategy='epoch', bf16=True,
        gradient_checkpointing=True, report_to=[], seed=41)
    trainer = Trainer(model=model, args=args, train_dataset=ds, data_collator=collate)
    trainer.train()
    model.save_pretrained(str(out / 'final'))
    tokenizer.save_pretrained(str(out / 'final'))
    print(f"saved adapter -> {out / 'final'}")


if __name__ == '__main__':
    main()
