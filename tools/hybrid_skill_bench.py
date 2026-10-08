#!/usr/bin/env python3
"""Hybrid Skill-Motor Architecture: model decides WHAT, skills execute HOW.

The model (V1.0 / FluxEidosV1.0-9B) reads the demand and outputs:
  {"skill": "<skill_name>", "params": {<skill-specific parameters>}}
The skill library then deterministically generates the CAD design.

This combines:
- Model's demand understanding + creative parameter selection
- Skill library's speed (0.000s) + CAD reliability + 1.5x pricing

The model makes ONE small decision (skill + params, ~50 tokens) instead of
generating a full design (~1500 tokens). If the model fails to select a
valid skill/params, fall back to pure model generation.
"""
import argparse, json, os, random, re, statistics, sys, time
from pathlib import Path

os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
HERE = Path(__file__).resolve().parent
BENCH = HERE.parent
sys.path.insert(0, str(HERE))
import money_bench_v5 as mb
from rsi_night_loop import cad_eval, judge, speed_price, ACCEPT

OUT = BENCH / 'runs' / 'hybrid_skill'
BASE = '/home/exuber/models/qwen3.5-9b-bf16'
ADAPTER = '/home/exuber/models/prsi_rl_v3/iter6'  # V1.0

# ═══ Skill Library (deterministic, CAD-verified parametric functions) ═══

def _dock(pw, pd, ph, dw, dd, margin=4, base_scale=0.4, back_ratio=0.55):
    m = margin
    bw, bd, bh = min(dw*base_scale+40, pw+50), min(dd*.5+20, pd+35), 8
    back_h, bt = ph*back_ratio, 6
    sw, sd, sh = pw+m, pd+m, 15
    nodes = [
        {"id":"base","op":"box","size":[bw,bd,bh]},
        {"id":"back","op":"box","size":[sw,bt,back_h]},
        {"id":"back_t","op":"transform","input":"back","xyz":[0,-bd/2+bt/2,bh+back_h/2],"rpy":[0,0,0]},
        {"id":"sl","op":"box","size":[3,sd,sh]},
        {"id":"sl_t","op":"transform","input":"sl","xyz":[-sw/2-1.5,0,bh+sh/2],"rpy":[0,0,0]},
        {"id":"sr","op":"box","size":[3,sd,sh]},
        {"id":"sr_t","op":"transform","input":"sr","xyz":[sw/2+1.5,0,bh+sh/2],"rpy":[0,0,0]},
        {"id":"cbl","op":"cylinder","radius":4,"height":bh+1},
        {"id":"cbl_t","op":"transform","input":"cbl","xyz":[0,bd/4,bh/2],"rpy":[0,0,0]},
        {"id":"asm","op":"union","inputs":["base","back_t","sl_t","sr_t","cbl_t"]},
    ]
    parts = [
        {"name":"base_plate","node":"base","role":"frame","xyz":[0,0,0],"rpy":[0,0,0]},
        {"name":"back_support","node":"back_t","role":"module","xyz":[0,0,0],"rpy":[0,0,0]},
        {"name":"slot_left","node":"sl_t","role":"module","xyz":[0,0,0],"rpy":[0,0,0]},
        {"name":"slot_right","node":"sr_t","role":"module","xyz":[0,0,0],"rpy":[0,0,0]},
        {"name":"cable_hole","node":"cbl_t","role":"tooling","xyz":[0,0,0],"rpy":[0,0,0]},
    ]
    return {"schema":"workstation-csg/1","hypothesis":"parametric_dock","nodes":nodes,"parts":parts}

def _add_bay(design, bay_w=60, bay_d=45, bay_h=25):
    d = json.loads(json.dumps(design))  # deep copy
    nodes = [n for n in d['nodes'] if n['id'] != 'asm']
    # find base width from the base node
    bw = next((n['size'][0] for n in nodes if n['id']=='base'), 100)
    by = bw/2 + bay_w/2 + 5
    # append bay nodes AFTER all existing nodes (correct ordering for boolean)
    new_ids = []
    bay_nodes = [
        ("bay_base", "box", [bay_w, bay_d, 5], [by, 0, 2.5]),
        ("bay_w1", "box", [bay_w, 3, bay_h], [by, bay_d/2-1.5, 5+bay_h/2]),
        ("bay_w2", "box", [3, bay_d, bay_h], [by+bay_w/2-1.5, 0, 5+bay_h/2]),
        ("bay_w3", "box", [3, bay_d, bay_h], [by-bay_w/2+1.5, 0, 5+bay_h/2]),
    ]
    for nid, op, size, xyz in bay_nodes:
        nodes.append({"id":nid, "op":op, "size":size})
        nodes.append({"id":f"{nid}_t", "op":"transform", "input":nid, "xyz":xyz, "rpy":[0,0,0]})
        new_ids.append(f"{nid}_t")
    all_ids = [n['id'] for n in nodes if n['op'] != 'union'] + new_ids
    # deduplicate while preserving order
    seen = set(); ordered = []
    for x in all_ids:
        if x not in seen: seen.add(x); ordered.append(x)
    nodes.append({"id":"asm","op":"union","inputs":ordered})
    d['nodes'] = nodes
    d['parts'] += [
        {"name":"bay_base","node":"bay_base_t","role":"module","xyz":[0,0,0],"rpy":[0,0,0]},
        {"name":"bay_front","node":"bay_w1_t","role":"module","xyz":[0,0,0],"rpy":[0,0,0]},
        {"name":"bay_side","node":"bay_w2_t","role":"module","xyz":[0,0,0],"rpy":[0,0,0]},
    ]
    d['hypothesis'] = 'dock+bay'
    return d

def _add_stand(design, tw=220, td=8, th=170):
    d = json.loads(json.dumps(design))
    nodes = [n for n in d['nodes'] if n['id'] != 'asm']
    # find base depth
    bd = next((n['size'][1] for n in nodes if n['id']=='base'), 100)
    sy = -bd/2 - 15
    new_ids = []
    stand_nodes = [
        ("ts_base", "box", [tw, td, 5], [0, sy, 2.5]),
        ("ts_lip", "box", [tw, 10, 12], [0, sy-5, 6]),
    ]
    for nid, op, size, xyz in stand_nodes:
        nodes.append({"id":nid, "op":op, "size":size})
        nodes.append({"id":f"{nid}_t", "op":"transform", "input":nid, "xyz":xyz, "rpy":[0,0,0]})
        new_ids.append(f"{nid}_t")
    all_ids = [n['id'] for n in nodes if n['op'] != 'union'] + new_ids
    seen = set(); ordered = []
    for x in all_ids:
        if x not in seen: seen.add(x); ordered.append(x)
    nodes.append({"id":"asm","op":"union","inputs":ordered})
    d['nodes'] = nodes
    d['parts'] += [
        {"name":"stand_base","node":"ts_base_t","role":"module","xyz":[0,0,0],"rpy":[0,0,0]},
        {"name":"stand_lip","node":"ts_lip_t","role":"module","xyz":[0,0,0],"rpy":[0,0,0]},
    ]
    d['hypothesis'] += '+stand'
    return d

def _compact(design, new_w, new_d):
    """Scale all dimensions to fit new desk while maintaining structure."""
    d = json.loads(json.dumps(design))
    for n in d['nodes']:
        if n.get('size'):
            n['size'] = [min(s, new_w if i==0 else new_d if i==1 else s) for i, s in enumerate(n['size'])]
        if n.get('xyz'):
            n['xyz'] = [x * 0.7 for x in n['xyz']]  # scale positions inward
    d['hypothesis'] += '_compact'
    return d


SKILLS = {
    'dock': lambda p: _dock(p['phone_w'], p['phone_d'], p['phone_h'], p['desk_w'], p['desk_d']),
    'dock_bay': lambda p: _add_bay(_dock(p['phone_w'], p['phone_d'], p['phone_h'], p['desk_w'], p['desk_d']),
                                    bay_w=p.get('bay_w', 60), bay_d=p.get('bay_d', 45)),
    'dock_bay_stand': lambda p: _add_stand(_add_bay(_dock(p['phone_w'], p['phone_d'], p['phone_h'],
                                    p['desk_w'], p['desk_d'])), tw=p.get('tw', 220)),
    'compact': lambda p: _compact(_dock(p['phone_w'], p['phone_d'], p['phone_h'],
                               p['desk_w'], p['desk_d']), p['desk_w'], p['desk_d']),
}

SKILL_SELECT_SYS = '''You are a design architect. Given a workstation demand, select the best skill and parameters.
Available skills: dock, dock_bay, dock_bay_stand, compact.
Return ONLY JSON: {"skill": "<name>", "params": {"phone_w": <n>, "phone_d": <n>, "phone_h": <n>, "desk_w": <n>, "desk_d": <n>, ...optional params}}'''


def parse_dims(text):
    return [int(x) for x in re.findall(r'\d+', text)]


def main():
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
    from peft import PeftModel

    OUT.mkdir(parents=True, exist_ok=True)
    tok = AutoTokenizer.from_pretrained(BASE, trust_remote_code=True)
    if tok.pad_token is None: tok.pad_token = tok.eos_token
    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4',
                             bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True)
    model = AutoModelForCausalLM.from_pretrained(BASE, quantization_config=bnb,
                                                 device_map='cuda', trust_remote_code=True)
    model = PeftModel.from_pretrained(model, ADAPTER)
    model.eval()

    all_runs = []
    for si in range(5):
        capital, rounds = {}, []
        total = 0.0
        skill_used, fallback_used = 0, 0
        print(f"\n=== [HYBRID] session {si+1}/5 ===", flush=True)
        for rd in range(5):
            demand = mb.DEMANDS[rd]
            user = json.dumps({'demand': demand,
                               'capital': [{'id': k, 'desc': v.get('description', '')} for k, v in capital.items()],
                               'hint': None}, ensure_ascii=False)

            # Phase 1: model selects skill + params (~50 tokens, fast)
            sel_prompt = tok.apply_chat_template(
                [{'role': 'system', 'content': SKILL_SELECT_SYS}, {'role': 'user', 'content': demand}],
                tokenize=False, add_generation_prompt=True, enable_thinking=False)
            ids = tok(sel_prompt, return_tensors='pt', truncation=True, max_length=2000).to(model.device)
            t0 = time.monotonic()
            with torch.no_grad():
                out = model.generate(**ids, max_new_tokens=200, temperature=0.2,
                                     do_sample=True, pad_token_id=tok.pad_token_id)
            sel_text = tok.decode(out[0][ids['input_ids'].shape[1]:], skip_special_tokens=True).strip()
            gen_secs = round(time.monotonic() - t0, 2)

            # Phase 2: execute skill deterministically (0.000s)
            design = None
            try:
                i, j = sel_text.find('{'), sel_text.rfind('}')
                sel = json.loads(sel_text[i:j+1])
                skill_name = sel.get('skill', '')
                params = sel.get('params', {})
                # fill missing params from demand
                dims = parse_dims(demand)
                defaults = {'phone_w': dims[0] if dims else 78, 'phone_d': dims[1] if len(dims)>1 else 12,
                           'phone_h': dims[2] if len(dims)>2 else 160,
                           'desk_w': dims[3] if len(dims)>3 else 420, 'desk_d': dims[4] if len(dims)>4 else 280}
                for k, v in defaults.items():
                    params.setdefault(k, v)

                if skill_name in SKILLS:
                    design_obj = SKILLS[skill_name](params)
                    design = json.dumps(design_obj)
                    skill_used += 1
            except Exception as e:
                pass

            # Fallback: model generates design directly (slower but always works)
            if design is None:
                fallback_used += 1
                gen_prompt = tok.apply_chat_template(
                    [{'role': 'system', 'content': mb.SYSTEM}, {'role': 'user', 'content': user}],
                    tokenize=False, add_generation_prompt=True, enable_thinking=False)
                ids2 = tok(gen_prompt, return_tensors='pt', truncation=True, max_length=3500).to(model.device)
                t0 = time.monotonic()
                with torch.no_grad():
                    out2 = model.generate(**ids2, max_new_tokens=1500, temperature=0.3,
                                         do_sample=True, top_p=0.95, pad_token_id=tok.pad_token_id)
                design = tok.decode(out2[0][ids2['input_ids'].shape[1]:], skip_special_tokens=True).strip()
                gen_secs = round(time.monotonic() - t0, 2)
                # clean up
                design = re.sub(r'<think>.*?</think>', '', design, flags=re.S).strip()
                if not design.startswith('{'):
                    i, j = design.find('{'), design.rfind('}')
                    if i >= 0 and j > i:
                        try: json.loads(design[i:j+1]); design = design[i:j+1]
                        except: pass

            if not design or len(design) < 40:
                rounds.append({'rd': rd, 'rating': 0, 'sold': False, 'rev': 0, 'secs': gen_secs})
                print(f"  R{rd+1}: ✗ no design", flush=True)
                continue

            # CAD + judge
            dims = parse_dims(demand)
            dw = dims[3] if len(dims) > 3 else 420
            dd = dims[4] if len(dims) > 4 else 280
            cad = cad_eval(design, capital, OUT / f's{si}_r{rd}', (dw, dd))
            if not cad.get('metrics'):
                rounds.append({'rd': rd, 'rating': 0, 'sold': False, 'rev': 0, 'secs': gen_secs})
                print(f"  R{rd+1}: ✗ CAD {cad.get('error','?')[:30]}", flush=True)
                continue

            rating = judge(demand, design, cad.get('metrics'))
            sold = rating >= ACCEPT
            rev = round(100 * speed_price(gen_secs)) if sold else 0
            total += rev
            if sold or rating >= 3:
                capital[f'r{rd+1}'] = {'status': 'EXECUTED_CAD', 'step_path': cad['step_path'],
                                       'description': f'Round {rd+1} design', 'measurements': {}}
            method = 'skill' if skill_used > fallback_used else 'model'
            rounds.append({'rd': rd, 'rating': rating, 'sold': sold, 'rev': rev,
                           'secs': gen_secs, 'method': 'skill' if design.startswith('{"schema"') and gen_secs < 5 else 'model'})
            print(f"  R{rd+1}: {'✅' if sold else '❌'} {rating}/10 {gen_secs:.1f}s ¥{rev} | {'skill' if gen_secs < 5 else 'model'}", flush=True)

        run = {'profit': total, 'rounds': rounds,
               'sold': f"{sum(1 for r in rounds if r['sold'])}/5",
               'skill_calls': skill_used, 'model_fallbacks': fallback_used}
        all_runs.append(run)
        print(f"  => ¥{total} | sold {run['sold']} | skill:{skill_used} model:{fallback_used}", flush=True)

    profits = [r['profit'] for r in all_runs]
    total_skill = sum(r['skill_calls'] for r in all_runs)
    total_model = sum(r['model_fallbacks'] for r in all_runs)
    print(f"\n{'='*50}")
    print(f"[HYBRID] profit mean ¥{statistics.mean(profits):.0f} runs={[round(p) for p in profits]}")
    print(f"[HYBRID] skill calls: {total_skill}/25 | model fallbacks: {total_model}/25")
    (OUT / 'results.json').write_text(json.dumps(all_runs, indent=2))


if __name__ == '__main__':
    main()
