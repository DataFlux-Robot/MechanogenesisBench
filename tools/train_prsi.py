#!/usr/bin/env python3
"""Phase 2: Fine-tune Qwen-3.5-9B with LoRA on PRSI trajectories (v2, using HF Trainer)."""
import json, os, sys, time
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
from pathlib import Path

TRAIN_DATA = Path('/home/exuber/CODE/CORE/pythonProject1/AUTORESEARCH/MechanogenesisBench-upstream/runs/training_data')
MODEL_PATH = '/home/exuber/models/qwen3.5-9b-bf16'
OUTPUT_DIR = '/home/exuber/models/prsi_lora'

SYSTEM = 'Design a desk workstation. Return ONLY JSON with schema="workstation-csg/1".\nOps: box(size), cylinder(radius,height), union(inputs), difference(inputs), transform(input,xyz,rpy), capital(asset_id).\ncapital(asset_id) imports a PREVIOUSLY BUILT module — it is FREE and FASTER. USE IT if available.\nParts: {"name","node","role(frame|module|tooling)","xyz","rpy"}. Max 64 nodes, 16 parts. mm, XY desk.'

DEMANDS = [
    "Build a phone dock for 78x12x160mm phone. Desk 420x280mm. From scratch.",
    "Customer upgraded to 90x14x175mm phone. Adapt the dock. MUST reuse the base from round 1.",
    "Add earbuds bay (65x48x28mm). MUST keep the adapted dock and add to it.",
    "Add tablet stand (250x10x175mm) behind. Combine all modules. MUST reuse dock+earbuds.",
    "Desk shrank to 300x200mm! Shrink but keep ALL functions. MUST optimize accumulated design.",
]

def main():
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM, TrainingArguments, Trainer, DataCollatorWithPadding
    from peft import LoraConfig, get_peft_model, TaskType

    # Load data
    trajectories = json.loads((TRAIN_DATA / 'all_trajectories.json').read_text())
    # Keep only positive samples
    positive = [t for t in trajectories if t.get('sold') or (t.get('reused') and t.get('rating', 0) >= 4)]
    print(f"Training on {len(positive)} positive samples")

    # Load model and tokenizer
    print(f"Loading model from {MODEL_PATH}...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    from transformers import BitsAndBytesConfig
    bnb = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_PATH, quantization_config=bnb, device_map="cuda", trust_remote_code=True)

    # LoRA
    lora = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=32, lora_alpha=64, lora_dropout=0.0,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
    )
    from peft import prepare_model_for_kbit_training
    model = prepare_model_for_kbit_training(model)
    model = get_peft_model(model, lora)
    model.print_trainable_parameters()

    # Build dataset
    def build_text(t):
        rd = t['round']
        demand = DEMANDS[rd] if rd < len(DEMANDS) else DEMANDS[-1]
        user = json.dumps({'demand': demand}, ensure_ascii=False)
        return {
            'messages': [
                {'role': 'system', 'content': SYSTEM},
                {'role': 'user', 'content': user},
                {'role': 'assistant', 'content': t['text']},
            ]
        }

    # Tokenize with assistant-only labels
    def tokenize(sample):
        msgs = sample['messages']
        # Build full conversation text
        prompt_parts = []
        for m in msgs[:-1]:
            prompt_parts.append(f"<|im_start|>{m['role']}\n{m['content']}<||im_end|>")
        prompt_text = "\n".join(prompt_parts)
        assistant_text = f"<|im_start|>assistant\n{msgs[-1]['content']}<|im_end|>"
        full_text = prompt_text + "\n" + assistant_text

        # Tokenize
        full_ids = tokenizer.encode(full_text, add_special_tokens=False)
        prompt_ids = tokenizer.encode(prompt_text, add_special_tokens=False)

        # Labels: mask prompt tokens with -100
        labels = [-100] * len(prompt_ids) + full_ids[len(prompt_ids):]
        labels = labels[:len(full_ids)]

        return {
            'input_ids': full_ids[:2048],
            'attention_mask': [1] * min(len(full_ids), 4096),
            'labels': labels[:2048],
        }

    from datasets import Dataset
    texts = [build_text(t) for t in positive]
    dataset = Dataset.from_list(texts)
    dataset = dataset.map(tokenize, remove_columns=['messages'], desc="Tokenizing")

    # Split
    dataset = dataset.train_test_split(test_size=0.1, seed=42)
    print(f"Train: {len(dataset['train'])}, Eval: {len(dataset['test'])}")

    # Training arguments
    output_dir = Path(OUTPUT_DIR) / time.strftime('%Y%m%d_%H%M%S')
    args = TrainingArguments(
        output_dir=str(output_dir),
        num_train_epochs=3,
        per_device_train_batch_size=1,
        per_device_eval_batch_size=1,
        gradient_accumulation_steps=8,
        learning_rate=1e-4,
        warmup_steps=10,
        logging_steps=5,
        eval_strategy="steps",
        eval_steps=20,
        save_strategy="epoch",
        bf16=True,
        gradient_checkpointing=True,
        report_to=[],  # no wandb
        remove_unused_columns=False,
    )

    # Custom data collator for variable-length sequences
    from dataclasses import dataclass
    @dataclass
    class Collator:
        tokenizer: object
        def __call__(self, features):
            max_len = max(len(f['input_ids']) for f in features)
            batch = {
                'input_ids': [],
                'attention_mask': [],
                'labels': [],
            }
            for f in features:
                ids = f['input_ids']
                mask = f['attention_mask']
                labels = f['labels']
                pad_len = max_len - len(ids)
                batch['input_ids'].append(ids + [self.tokenizer.pad_token_id] * pad_len)
                batch['attention_mask'].append(mask + [0] * pad_len)
                batch['labels'].append(labels + [-100] * pad_len)
            return {k: torch.tensor(v) for k, v in batch.items()}

    collator = Collator(tokenizer)

    # Trainer
    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=dataset['train'],
        eval_dataset=dataset['test'],
        data_collator=collator,
    )

    # Train
    print(f"\nStarting training: {args.num_train_epochs} epochs, {len(dataset['train'])} samples")
    trainer.train()

    # Save final model
    final_dir = output_dir / 'final'
    model.save_pretrained(final_dir, safe_serialization=True)
    tokenizer.save_pretrained(final_dir)
    print(f"\nTraining complete. Model saved: {final_dir}")

if __name__ == '__main__':
    main()
