#!/usr/bin/env python3
"""Evaluate a local Qwen model (zero-shot or LoRA) on PRSI Money Bench with full
commercial-baseline parity: real build123d CAD (via subprocess), mimo judge,
speed pricing, profit, and capital registry of real STEP files.

Main process needs torch/transformers/peft/litellm (dd_qwen9b venv).
CAD evaluation runs in the text-to-cad venv subprocess (build123d).

Usage:
  python tools/eval_local_model.py --model /home/exuber/models/qwen3.5-27b-bf16 --tag qwen27b-zeroshot
  python tools/eval_local_model.py --model .../9b --adapter .../prsi_lora/final --tag qwen9b-sft-v2
"""
import argparse, json, os, subprocess, sys, time
from pathlib import Path

os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
HERE = Path(__file__).resolve().parent

CAD_PY = '/home/exuber/CODE/CORE/pythonProject1/AUTORESEARCH/text-to-cad/.venv/bin/python'
CAD_ENV_PYTHONPATH = ('/home/exuber/CODE/CORE/pythonProject1/AUTORESEARCH/text-to-cad/packages/cadpy/src:'
                      '/home/exuber/CODE/CORE/pythonProject1/AUTORESEARCH/MechanogenesisBenchDEV/src')

RESULTS = HERE.parent / 'runs' / 'local_model_eval'

SYSTEM = '''Design a desk workstation. Return ONLY JSON with schema="workstation-csg/1".
Ops: box(size), cylinder(radius,height), union(inputs), difference(inputs), transform(input,xyz,rpy), capital(asset_id).
capital(asset_id) imports a PREVIOUSLY BUILT module from the capital list — it's FREE and FASTER than rebuilding.
If capital modules exist, USE THEM via capital nodes.
Parts: {"name","node","role(frame|module|tooling)","xyz","rpy"}. Max 64 nodes, 16 parts. mm, XY desk.
Example: {"schema":"workstation-csg/1","hypothesis":"reused+new","nodes":[{"id":"old","op":"capital","asset_id":"r1"},{"id":"n","op":"box","size":[60,40,40]},{"id":"u","op":"union","inputs":["old","n"]}],"parts":[{"name":"base","node":"old","role":"frame","xyz":[0,0,0],"rpy":[0,0,0]}]}'''

DEMANDS = [
    "Build a phone dock for 78x12x160mm phone. Desk 420x280mm. From scratch.",
    "Customer upgraded to 90x14x175mm phone. Adapt the dock. MUST reuse the base from round 1.",
    "Add earbuds bay (65x48x28mm). MUST keep the adapted dock and add to it.",
    "Add tablet stand (250x10x175mm) behind. Combine all modules. MUST reuse dock+earbuds.",
    "Desk shrank to 300x200mm! Shrink but keep ALL functions. MUST optimize accumulated design.",
]
PRICE = 100; ACCEPT = 5
# Hardened execution ruler: a round sells iff the design fits the round's desk,
# has no self-intersecting parts, and rounds 2-5 reuse capital (all demanded).
DESK = {0: (420, 280), 1: (420, 280), 2: (420, 280), 3: (420, 280), 4: (300, 200)}
JUDGE_SYS = 'Rate the workstation design 0-10 for user satisfaction. Return ONLY JSON: {"rating":<n>,"accepted":<bool>,"feedback":"<t>"}'


def speed_price(secs):
    if secs < 10: return 1.5
    if secs < 30: return 1.2
    if secs < 60: return 1.0
    if secs < 120: return 0.8
    return 0.5


def repair_design(text):
    """Syntax normalization (same as the training loop): cross-wired
    input/inputs, duplicate node ids renamed, invalid/duplicate parts dropped."""
    try:
        d = json.loads(text)
    except Exception:
        return text
    changed = False
    for n in d.get('nodes', []):
        if n.get('op') == 'transform' and 'input' not in n and 'inputs' in n:
            v = n.pop('inputs')
            n['input'] = v[0] if isinstance(v, list) else v
            changed = True
        elif n.get('op') in ('union', 'difference') and 'inputs' not in n and 'input' in n:
            v = n.pop('input')
            n['inputs'] = v if isinstance(v, list) else [v]
            changed = True
    seen = set()
    for n in d.get('nodes', []):
        nid = n.get('id')
        if not nid:
            continue
        if nid in seen:
            k = 2
            while f'{nid}__{k}' in seen:
                k += 1
            n['id'] = f'{nid}__{k}'
            seen.add(n['id'])
            changed = True
        else:
            seen.add(nid)
    node_ids = {n.get('id') for n in d.get('nodes', [])}
    kept, names = [], set()
    for part in d.get('parts', []):
        if part.get('node') not in node_ids or part.get('name') in names:
            changed = True
            continue
        names.add(part.get('name'))
        kept.append(part)
    if len(kept) != len(d.get('parts', [])):
        d['parts'] = kept
    return json.dumps(d, ensure_ascii=False) if changed else text


def cad_eval(text, capital, folder):
    """Run real CAD evaluation in the text-to-cad venv subprocess."""
    folder = Path(folder); folder.mkdir(parents=True, exist_ok=True)
    job_in, job_out = folder / '_job_in.json', folder / '_job_out.json'
    job_in.write_text(json.dumps({'text': text, 'capital': capital, 'folder': str(folder)}))
    env = dict(os.environ, PYTHONPATH=CAD_ENV_PYTHONPATH)
    r = subprocess.run([CAD_PY, str(HERE / 'cad_eval_worker.py'), str(job_in), str(job_out)],
                       env=env, capture_output=True, text=True, timeout=300)
    if job_out.exists():
        return json.loads(job_out.read_text())
    return {'error': (r.stderr or r.stdout or 'worker failed')[:200], 'metrics': None}


def judge_call(jname, demand, text, cad, tries=3):
    """Call a commercial judge via litellm; returns rating 0-10.
    Retries on empty/unparseable responses (judge-0 ambiguity: an API zero and a
    genuine 0 must not be conflated — same policy as surpass_bench.safe_judge)."""
    from litellm import completion
    specs = {
        'mimo-v2.6-pro': ('openai/mimo-v2.6-pro',
                          os.environ.get('MIMO_BASE_URL', 'https://api.xiaomimimo.com/v1'), 'MIMO_KEY'),
        'glm-5.3-flash': ('openai/glm-5.3-flash', 'https://api.z.ai/api/anthropic/v1', 'ZAI_KEY_LITELLM'),
    }
    model, base, keyenv = specs[jname]
    key = os.environ.get(keyenv, 'none')
    if keyenv == 'ZAI_KEY_LITELLM' and key == 'none':
        cfg = json.loads(Path(os.path.expanduser('~/.config/fluxkernel/model.json')).read_text())
        key = cfg.get('api_key', '')
    ev = cad.get('metrics') or {}
    prompt = (f"Demand: {demand}\nDesign: {text[:6000]}\n"
              f"CAD facts: {json.dumps({'envelope_excess_mm': ev.get('occupied_envelope_excess_mm'), 'overlap_mm3': ev.get('overlap_mm3')})}")
    for att in range(tries):
        try:
            resp = completion(model=model, api_base=base, api_key=key,
                              messages=[{'role': 'system', 'content': JUDGE_SYS},
                                        {'role': 'user', 'content': prompt}],
                              max_tokens=1500, temperature=0.2, timeout=300)
            raw = resp.choices[0].message.content or ''
            clean = raw.strip()
            if clean.startswith('```'):
                clean = clean.split('\n', 1)[-1].rsplit('```', 1)[0].strip()
            rating = json.loads(clean).get('rating', 0)
            return rating
        except Exception as e:
            print(f"    judge {jname} retry {att+1}/{tries}: {str(e)[:70]}")
    return 0


def load_model(path, adapter=None):
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                             bnb_4bit_compute_dtype=torch.bfloat16,
                             bnb_4bit_use_double_quant=True)
    tokenizer = AutoTokenizer.from_pretrained(path, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(path, quantization_config=bnb,
                                                 device_map="cuda", trust_remote_code=True)
    if adapter:
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, adapter)
        print(f"adapter: {adapter}")
    model.eval()
    return model, tokenizer


INTENT_SYS = ('You are a workstation designer. Read the WORKSPACE (customer demand '
              'plus available capital assets). State ONE design concept in a single '
              'sentence: the layout, the key modules, and how you will reuse capital. '
              'No JSON. No preamble.')


def generate_intent(model, tokenizer, demand, capital):
    """Fork-and-Flush stage 1: flush history, re-derive intent from the workspace only."""
    import torch
    user_msg = json.dumps({'demand': demand,
                           'capital': [{'id': k, 'desc': v.get('description', '')} for k, v in capital.items()],
                           'hint': ('capital(asset_id) imports a previously built module — '
                                    'free and faster than rebuilding.') if capital else None},
                          ensure_ascii=False)
    prompt = tokenizer.apply_chat_template([{'role': 'system', 'content': INTENT_SYS},
                                            {'role': 'user', 'content': user_msg}],
                                           tokenize=False, add_generation_prompt=True,
                                           enable_thinking=False)
    inputs = tokenizer(prompt, return_tensors='pt', truncation=True, max_length=4096).to(model.device)
    t0 = time.monotonic()
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=120, temperature=0.95, top_p=0.95,
                             do_sample=True, pad_token_id=tokenizer.pad_token_id)
    intent = tokenizer.decode(out[0][inputs['input_ids'].shape[1]:], skip_special_tokens=True).strip()[:300]
    return intent, round(time.monotonic() - t0, 1)


def generate(model, tokenizer, demand, capital, max_new=2048, use_intent=False):
    import torch
    msg = {'demand': demand,
           'capital': [{'id': k, 'desc': v.get('description', '')} for k, v in capital.items()],
           'hint': 'Use capital(asset_id) to import previous modules.' if capital else None}
    intent_secs = 0.0
    if use_intent:
        intent, intent_secs = generate_intent(model, tokenizer, demand, capital)
        if intent:
            msg['intent'] = intent
            print(f'    intent: {intent[:100]}', flush=True)
    user_msg = json.dumps(msg, ensure_ascii=False)
    messages = [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': user_msg}]
    prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True,
                                           enable_thinking=False)
    inputs = tokenizer(prompt, return_tensors='pt', truncation=True, max_length=4096).to(model.device)
    t0 = time.monotonic()
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=max_new, temperature=0.3,
                             do_sample=True, top_p=0.95, pad_token_id=tokenizer.pad_token_id)
    text = tokenizer.decode(out[0][inputs['input_ids'].shape[1]:], skip_special_tokens=True).strip()
    if text.startswith('```') and text.count('```') >= 2:
        lines = text.split('\n')
        if len(lines) >= 3:
            text = '\n'.join(lines[1:-1]).strip() or text
    if '"h":' in text and '"hypothesis":' not in text:
        text = text.replace('"h":', '"hypothesis":')
    # the intent stage is part of deployment latency — count it in the price
    return text, round(time.monotonic() - t0 + intent_secs, 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model', required=True)
    ap.add_argument('--adapter', default=None)
    ap.add_argument('--tag', required=True)
    ap.add_argument('--judges', nargs='+', default=['mimo-v2.6-pro'])
    ap.add_argument('--n', type=int, default=1, help='number of sessions')
    ap.add_argument('--intent', action='store_true',
                    help='Fork-and-Flush deployment: flushed intent re-derivation, then design '
                         'conditioned on it (intent latency is priced)')
    ap.add_argument('--repair', action='store_true',
                    help='apply the syntax-repair layer before CAD evaluation')
    a = ap.parse_args()

    model, tokenizer = load_model(a.model, a.adapter)
    all_runs = []
    for sess_i in range(a.n):
        out_dir = RESULTS / f"{a.tag}_{time.strftime('%Y%m%d_%H%M%S')}"
        out_dir.mkdir(parents=True, exist_ok=True)
        capital, rounds = {}, []
        total_rev = 0.0
        hard_total = 0.0
        hard_count = 0
        print(f"\n=== session {sess_i+1}/{a.n}: {a.tag} ===")
        for rd in range(5):
            demand = DEMANDS[rd]
            best = None
            for att in range(2):
                text, secs = generate(model, tokenizer, demand, capital, use_intent=a.intent)
                if not text.strip():
                    continue
                if a.repair:
                    text = repair_design(text)
                cad = cad_eval(text, capital, out_dir / f'r{rd}_a{att}' / 'cad')
                if cad.get('metrics'):
                    best = (text, secs, cad)
                    break
            if best is None:
                rounds.append({'rd': rd, 'rating': 0, 'sold': False, 'rev': 0, 'reused': False,
                               'secs': 0, 'hard': False, 'hard_rev': 0})
                print(f"  R{rd+1}: ❌ no valid design")
                continue
            text, secs, cad = best
            ratings = [judge_call(j, demand, text, cad) for j in a.judges]
            ratings = [r for r in ratings if r > 0]
            med = sorted(ratings)[len(ratings)//2] if ratings else 0
            sold = med >= ACCEPT
            rev = round(PRICE * speed_price(secs)) if sold else 0
            total_rev += rev
            try:
                reused = any(n.get('op') == 'capital' for n in json.loads(text).get('nodes', []))
            except Exception:
                reused = False
            # v7 semantics (matches the paper protocol and the RL training env):
            # any EXECUTED design is a physical asset — gating on rating>=3 kills
            # the whole chain when R1 rates below it (capital(r1) then points at
            # nothing and every later round fails CAD)
            if cad.get('metrics'):
                capital[f'r{rd+1}'] = {'status': 'EXECUTED_CAD', 'step_path': cad['step_path'],
                                       'description': f'Round {rd+1} design',
                                       'measurements': cad.get('metrics', {})}
            facts = cad.get('facts_summary') or {}
            extent = facts.get('extent')
            inter = facts.get('intersections', 0)
            fit = bool(extent and extent[0] <= DESK[rd][0] + 0.01
                       and extent[1] <= DESK[rd][1] + 0.01)
            clean = (inter == 0)
            reuse_ok = (rd == 0) or reused
            hard_sold = bool(fit and clean and reuse_ok)
            hard_rev = round(PRICE * speed_price(secs)) if hard_sold else 0
            hard_total += hard_rev
            hard_count += hard_sold
            rounds.append({'rd': rd, 'rating': med, 'sold': sold, 'rev': rev,
                           'reused': reused, 'secs': secs,
                           'hard': hard_sold, 'hard_rev': hard_rev,
                           'cad': cad.get('facts_summary')})
            print(f"  R{rd+1}: {'✅' if sold else '❌'} {med}/10 {'♻️' if reused else '🔧'} "
                  f"{secs:.0f}s ¥{rev} | hard {'✅' if hard_sold else '❌'} ¥{hard_rev}")
        early = [r['secs'] for r in rounds[:2] if r['secs'] > 0]
        late = [r['secs'] for r in rounds[3:] if r['secs'] > 0]
        t_accel = round((sum(early)/max(len(early),1)) / (sum(late)/max(len(late),1)), 2) if late else None
        run = {'model': a.tag, 'rounds': rounds, 'profit': round(total_rev, 2),
               'revenue': total_rev, 'sold': f"{sum(1 for r in rounds if r['sold'])}/5",
               'reuse': f"{sum(1 for r in rounds if r.get('reused'))}/4", 't_accel': t_accel,
               'hard_profit': round(hard_total, 2), 'hard_sold': f"{hard_count}/5"}
        (out_dir / 'result.json').write_text(json.dumps(run, ensure_ascii=False, indent=2))
        all_runs.append(run)
        print(f"  => profit ¥{run['profit']} | sold {run['sold']} | reuse {run['reuse']} | t_accel {t_accel}")
    (RESULTS / f'{a.tag}_all_runs.json').write_text(json.dumps(all_runs, ensure_ascii=False, indent=2))
    print(f"\nsaved {len(all_runs)} runs -> {RESULTS / f'{a.tag}_all_runs.json'}")


if __name__ == '__main__':
    main()
