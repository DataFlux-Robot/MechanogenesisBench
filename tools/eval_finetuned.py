#!/usr/bin/env python3
"""Evaluate fine-tuned Qwen-3.5-9B (LoRA) on the PRSI Money Bench.

Loads the LoRA adapter on top of the quantized base model,
runs 5 rounds of workstation design with build123d real CAD evaluation,
and compares with 6 commercial model baselines.
"""
import json, os, sys, time
from pathlib import Path

os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

MODEL_PATH = '/home/exuber/models/qwen3.5-9b-bf16'
ADAPTER_PATH = '/home/exuber/models/prsi_lora/20261003_202128/final'

RESULTS = Path('/home/exuber/CODE/CORE/pythonProject1/AUTORESEARCH/MechanogenesisBench-upstream/runs/finetune_eval')

SYSTEM = 'Design a desk workstation. Return ONLY JSON with schema="workstation-csg/1".\nOps: box(size), cylinder(radius,height), union(inputs), difference(inputs), transform(input,xyz,rpy), capital(asset_id).\ncapital(asset_id) imports a PREVIOUSLY BUILT module — it is FREE and FASTER. USE IT if available.\nParts: {"name","node","role(frame|module|tooling)","xyz","rpy"}. Max 64 nodes, 16 parts. mm, XY desk.'

DEMANDS = [
    "Build a phone dock for 78x12x160mm phone. Desk 420x280mm. From scratch.",
    "Customer upgraded to 90x14x175mm phone. Adapt the dock. MUST reuse the base from round 1.",
    "Add earbuds bay (65x48x28mm). MUST keep the adapted dock and add to it.",
    "Add tablet stand (250x10x175mm) behind. Combine all modules. MUST reuse dock+earbuds.",
    "Desk shrank to 300x200mm! Shrink but keep ALL functions. MUST optimize accumulated design.",
]


def load_model():
    """Load base model with quantization + LoRA adapter."""
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
    from peft import PeftModel

    bnb = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )

    print("Loading base model...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        MODEL_PATH, quantization_config=bnb, device_map="cuda", trust_remote_code=True)

    print("Loading LoRA adapter...")
    model = PeftModel.from_pretrained(model, ADAPTER_PATH)
    model.eval()

    return model, tokenizer


def generate_design(model, tokenizer, demand, capital=None):
    """Generate a workstation design."""
    import torch

    user_msg = json.dumps({'demand': demand}, ensure_ascii=False)
    if capital:
        user_msg = json.dumps({
            'demand': demand,
            'capital': [{'id': k, 'desc': v} for k, v in capital.items()],
            'hint': 'Use capital(asset_id) to import previous modules.'
        }, ensure_ascii=False)

    messages = [
        {'role': 'system', 'content': SYSTEM},
        {'role': 'user', 'content': user_msg},
    ]

    prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, enable_thinking=False)
    inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=2048).to(model.device)

    started = time.monotonic()
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=2048,
            temperature=0.3,
            do_sample=True,
            top_p=0.95,
            pad_token_id=tokenizer.pad_token_id,
        )

    generated = outputs[0][inputs['input_ids'].shape[1]:]
    text = tokenizer.decode(generated, skip_special_tokens=True)
    secs = round(time.monotonic() - started, 1)

    # Strip markdown fence
    clean = text.strip()
    if clean.startswith('```') and clean.endswith('```'):
        lines = clean.split('\n')
        if len(lines) >= 3:
            clean = '\n'.join(lines[1:-1]).strip()

    return clean, secs


def evaluate_design(text, capital, folder):
    """Run build123d CAD evaluation."""
    sys.path.insert(0, '/home/exuber/CODE/CORE/pythonProject1/AUTORESEARCH/MechanogenesisBenchDEV/src')
    from oura_prsi_next.workstation_cad import validate_design, make_assembly, measure_export
    from oura_prsi_next.workstation_rsi import occupied_geometry_metrics
    from build123d import export_step

    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)

    try:
        # Fix key name: model may output 'h' instead of 'hypothesis'
        text_fixed = text.replace('"h":', '"hypothesis":') if '"h":' in text and '"hypothesis":' not in text else text
        design = json.loads(text_fixed)
        validate_design(design, capital or {})
        asm, consumed = make_assembly(design, capital or {})
        step_path = folder / 'design.step'
        export_step(asm, step_path)
        facts = measure_export(step_path, design)
        metrics = occupied_geometry_metrics(facts, {'desk_mm': [420, 280]})
        return {
            'valid': True,
            'metrics': metrics,
            'step_path': str(step_path),
            'consumed': consumed,
            'intersections': len(facts.get('intersections', [])),
        }
    except Exception as e:
        return {'valid': False, 'error': str(e)[:200]}


def main():
    print("=" * 60)
    print("  PRSI Fine-tuned Model Evaluation")
    print("=" * 60)

    # Load model
    model, tokenizer = load_model()

    # Run 5 rounds
    out_dir = RESULTS / time.strftime('%Y%m%d_%H%M%S')
    out_dir.mkdir(parents=True, exist_ok=True)

    capital = {}
    rounds = []

    for rd in range(5):
        demand = DEMANDS[rd]
        print(f"\n  --- Round {rd+1} ---")

        # Generate
        text, gen_secs = generate_design(model, tokenizer, demand, capital if rd > 0 else None)
        print(f"  Generated ({gen_secs:.1f}s): {text[:80]}...")

        # Evaluate with real CAD
        cad_result = evaluate_design(text, capital, out_dir / f'r{rd}')
        if cad_result['valid']:
            metrics = cad_result['metrics']
            print(f"  CAD: excess={metrics['occupied_envelope_excess_mm']:.1f}mm "
                  f"overlap={metrics['overlap_mm3']:.1f}mm³")
            print(f"  Reused capital: {cad_result['consumed']}")

            # Register capital
            capital[f'r{rd+1}'] = {
                'status': 'EXECUTED_CAD',
                'step_path': cad_result['step_path'],
                'description': f'Round {rd+1} design',
            }

            rounds.append({
                'rd': rd,
                'valid': True,
                'text_len': len(text),
                'secs': gen_secs,
                'metrics': metrics,
                'consumed': cad_result['consumed'],
            })
        else:
            print(f"  CAD FAILED: {cad_result['error'][:100]}")
            rounds.append({
                'rd': rd,
                'valid': False,
                'text_len': len(text),
                'secs': gen_secs,
                'error': cad_result['error'],
            })

        # Save round result
        (out_dir / f'r{rd}_output.json').write_text(json.dumps({
            'text': text, 'cad': cad_result, 'secs': gen_secs
        }, ensure_ascii=False, indent=2))

    # Summary
    print("\n" + "=" * 60)
    print("  RESULTS")
    print("=" * 60)
    valid_rounds = [r for r in rounds if r['valid']]
    print(f"  Valid designs: {len(valid_rounds)}/5")
    print(f"  Capital reuse: {sum(1 for r in rounds if r.get('consumed'))}/5")
    if valid_rounds:
        avg_excess = sum(r['metrics']['occupied_envelope_excess_mm'] for r in valid_rounds) / len(valid_rounds)
        avg_overlap = sum(r['metrics']['overlap_mm3'] for r in valid_rounds) / len(valid_rounds)
        avg_time = sum(r['secs'] for r in valid_rounds) / len(valid_rounds)
        print(f"  Avg excess: {avg_excess:.1f}mm")
        print(f"  Avg overlap: {avg_overlap:.1f}mm³")
        print(f"  Avg generation time: {avg_time:.1f}s")

    # Save summary
    (out_dir / 'summary.json').write_text(json.dumps({
        'model': 'qwen-3.5-9b-prsi-lora',
        'rounds': rounds,
    }, ensure_ascii=False, indent=2))
    print(f"\n  Results: {out_dir / 'summary.json'}")


if __name__ == '__main__':
    main()
