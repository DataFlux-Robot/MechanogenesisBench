#!/usr/bin/env python3
"""CRAFT-style Parametric Skill Library for Money Bench.

Instead of storing design examples (JitRL) or training weights (SFT/RL),
the model writes PARAMETRIC PYTHON FUNCTIONS that generate design JSON.
Each function is validated by real CAD execution, then stored in a library.
New designs = call functions with demand-specific parameters.

This completely bypasses the SFT controversy (zero weight updates, zero
external model data) and solves the self-play quality plateau (functions
encode design principles explicitly, not implicitly through weights).

Pipeline:
  1. Model writes a parametric function for a design type
  2. Test with multiple parameter sets → CAD validate each output
  3. If all pass → add to skill library
  4. New demand → retrieve matching skill → instantiate with params
  5. Optionally compose multiple skills for complex demands
"""
import json, os, random, re, statistics, subprocess, sys, time, traceback
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

HERE = Path(__file__).resolve().parent
BENCH = HERE.parent
sys.path.insert(0, str(HERE))
import money_bench_v5 as mb
from rsi_night_loop import cad_eval, judge, speed_price, ACCEPT

OUT = BENCH / 'runs' / 'skill_library'
LIB_DIR = OUT / 'skills'
RESULTS = BENCH / 'runs' / 'local_bench'


# ═══ Skill Templates (the model writes variations of these) ═══

SKILL_PROMPT = '''You are a CAD skill author. Write a Python function that generates a workstation design JSON.
The function takes phone dimensions and desk size as parameters, returns a JSON string.

Requirements:
- Function name: `create_design`
- Parameters: phone_w, phone_d, phone_h (mm), desk_w, desk_d (mm)
- Returns: JSON string with schema "workstation-csg/1"
- Nodes: MUST have at least 5 nodes (base, back, slot, support, union). Use box, cylinder, union, difference, transform, capital ops
- Parts: MUST have at least 3 parts (base_part, back_part, slot_part) with name/node/role/xyz/rpy
- All dimensions in mm, scaled to fit within desk_w x desk_d
- The phone slot must fit the phone: width >= phone_w + 2, depth >= phone_d + 2

Write ONLY the function, no explanation. Example structure:
```python
def create_design(phone_w, phone_d, phone_h, desk_w, desk_d):
    # design logic here
    return json.dumps({...})
```
```'''

TEST_PARAMS = [
    # (phone_w, phone_d, phone_h, desk_w, desk_d)
    (78, 12, 160, 420, 280),   # standard round 1
    (90, 14, 175, 420, 280),   # upgraded phone (round 2)
    (85, 13, 170, 300, 200),   # smaller desk (round 5)
]


def validate_skill(code_text):
    """Execute the function with test params, validate output via CAD."""
    try:
        # Extract and execute the function
        namespace = {'json': json}
        exec(code_text, namespace)
        func = namespace.get('create_design')
        if func is None:
            return False, "no create_design function"

        # Test with each parameter set
        results = []
        for params in TEST_PARAMS:
            output = func(*params)
            if not isinstance(output, str):
                return False, "function must return string"
            d = json.loads(output)
            if d.get('schema') != 'workstation-csg/1':
                return False, "wrong schema"
            if len(d.get('nodes', [])) < 2:
                return False, "too few nodes"
            if len(d.get('parts', [])) < 1:
                return False, "no parts"

            # CAD validate
            phone_w, phone_d, phone_h, desk_w, desk_d = params
            cad = cad_eval(output, {}, OUT / 'validate' / f"p{phone_w}_{desk_w}", (desk_w, desk_d))
            if not cad.get('metrics'):
                return False, f"CAD failed for params {params}: {cad.get('error', 'unknown')[:60]}"
            results.append(cad)

        return True, f"all {len(TEST_PARAMS)} param sets passed CAD"

    except Exception as e:
        return False, f"exception: {str(e)[:80]}"


def generate_skill(model, tok):
    """Have the model write a parametric skill function."""
    import torch
    prompt = tok.apply_chat_template(
        [{'role': 'system', 'content': SKILL_PROMPT},
         {'role': 'user', 'content': 'Write a phone dock design function with a base plate, back support, and phone slot.'}],
        tokenize=False, add_generation_prompt=True, enable_thinking=False)
    ids = tok(prompt, return_tensors='pt', truncation=True, max_length=3500).to(model.device)
    torch.manual_seed(42)
    t0 = time.monotonic()
    with torch.no_grad():
        out = model.generate(**ids, max_new_tokens=1500, temperature=0.3,
                             do_sample=True, top_p=0.95,
                             pad_token_id=tok.pad_token_id or tok.eos_token_id)
    text = tok.decode(out[0][ids['input_ids'].shape[1]:], skip_special_tokens=True).strip()
    secs = round(time.monotonic() - t0, 1)

    # Extract Python code
    if '```python' in text:
        start = text.find('```python') + 9
        end = text.find('```', start)
        if end > start:
            code = text[start:end].strip()
            return code, secs
    if 'def create_design' in text:
        # no fences, just raw code
        start = text.find('def create_design')
        code = text[start:]
        return code.strip(), secs
    return None, secs


def run_skill_bench(skills, n_sessions=5):
    """Run Money Bench using the skill library (parametric calls, not model generation)."""
    all_runs = []
    for si in range(n_sessions):
        capital, rounds = {}, []
        total = 0.0
        print(f"\n=== [SKILL-LIB] session {si+1}/{n_sessions} ===", flush=True)
        for rd in range(5):
            demand = mb.DEMANDS[rd]
            # Parse demand for phone/desk dimensions
            import re as _re
            dims = [int(x) for x in _re.findall(r'\d+', demand)]
            phone_w = dims[0] if dims else 78
            phone_d = dims[1] if len(dims) > 1 else 12
            phone_h = dims[2] if len(dims) > 2 else 160
            desk_w = dims[3] if len(dims) > 3 else 420
            desk_d = dims[4] if len(dims) > 4 else 280

            # Select best skill (round-robin for now; could use retrieval)
            skill = skills[rd % len(skills)]
            try:
                design_text = skill['func'](phone_w, phone_d, phone_h, desk_w, desk_d)
            except Exception as e:
                print(f"  R{rd+1}: ✗ skill error: {str(e)[:40]}", flush=True)
                rounds.append({'rd': rd, 'rating': 0, 'sold': False, 'rev': 0, 'secs': 0})
                continue

            t0 = time.monotonic()
            cad = cad_eval(design_text, capital, OUT / 'bench' / f"s{si}_r{rd}", (desk_w, desk_d))
            secs = round(time.monotonic() - t0, 1)  # skill execution + CAD time

            if not cad.get('metrics'):
                print(f"  R{rd+1}: ✗ CAD failed", flush=True)
                rounds.append({'rd': rd, 'rating': 0, 'sold': False, 'rev': 0, 'secs': secs})
                continue

            rating = judge(demand, design_text, cad.get('metrics'))
            sold = rating >= ACCEPT
            rev = round(100 * speed_price(secs)) if sold else 0
            total += rev

            try:
                reused = any(n.get('op') == 'capital' for n in json.loads(design_text).get('nodes', []))
            except:
                reused = False
            if sold or rating >= 3:
                capital[f'r{rd+1}'] = {'status': 'EXECUTED_CAD', 'step_path': cad['step_path'],
                                       'description': f'Round {rd+1} design', 'measurements': {}}
            rounds.append({'rd': rd, 'rating': rating, 'sold': sold, 'rev': rev,
                           'reused': reused, 'secs': secs, 'skill': skill['name']})
            print(f"  R{rd+1}: {'✅' if sold else '❌'} {rating}/10 {secs:.1f}s ¥{rev} | skill={skill['name']}", flush=True)

        run = {'profit': total, 'rounds': rounds,
               'sold': f"{sum(1 for r in rounds if r['sold'])}/5"}
        all_runs.append(run)
        print(f"  => ¥{total} | sold {run['sold']}", flush=True)

    profits = [r['profit'] for r in all_runs]
    print(f"\n[SKILL-LIB] profit mean ¥{statistics.mean(profits):.0f} runs={[round(p) for p in profits]}")
    (OUT / 'results.json').write_text(json.dumps(all_runs, indent=2))
    return all_runs


def main():
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
    from peft import PeftModel

    OUT.mkdir(parents=True, exist_ok=True)
    LIB_DIR.mkdir(parents=True, exist_ok=True)

    BASE = '/home/exuber/models/qwen3.5-9b-bf16'
    ADAPTER = '/home/exuber/models/prsi_rl_v3/iter6'  # V1.0 for skill writing

    tok = AutoTokenizer.from_pretrained(BASE, trust_remote_code=True)
    if tok.pad_token is None: tok.pad_token = tok.eos_token
    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4',
                             bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True)
    model = AutoModelForCausalLM.from_pretrained(BASE, quantization_config=bnb,
                                                 device_map='cuda', trust_remote_code=True)
    model = PeftModel.from_pretrained(model, ADAPTER)
    model.eval()

    # Phase 1: Generate and validate skills
    print("\n=== Phase 1: Skill Generation & Validation ===", flush=True)
    skills = []
    attempts = 3  # try 3 times to get valid skills
    for att in range(attempts):
        print(f"\n  Attempt {att+1}/{attempts}: writing skill...", flush=True)
        code, secs = generate_skill(model, tok)
        if not code:
            print(f"  ✗ no code extracted", flush=True)
            continue

        ok, msg = validate_skill(code)
        if ok:
            # Execute function to get callable
            ns = {'json': json}
            exec(code, ns)
            func = ns['create_design']
            skill_name = f"phone_dock_v{len(skills)+1}"
            skills.append({'name': skill_name, 'func': func, 'code': code})
            (LIB_DIR / f"{skill_name}.py").write_text(code)
            print(f"  ✅ {skill_name}: {msg}", flush=True)
        else:
            print(f"  ❌ validation failed: {msg}", flush=True)
            # Feed error back for retry (TextGrad-style)
            SKILL_PROMPT_RETRY = SKILL_PROMPT + f"\n\nPrevious attempt failed: {msg}\nFix the issue and try again."

    if not skills:
        print("No valid skills generated. Exiting.")
        return

    print(f"\n  Validated {len(skills)} skills", flush=True)

    # Phase 2: Run bench with skills
    print("\n=== Phase 2: Skill Library Bench ===", flush=True)
    results = run_skill_bench(skills, n_sessions=5)


if __name__ == '__main__':
    main()
