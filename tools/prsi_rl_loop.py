#!/usr/bin/env python3
"""PRSI-RL v1: on-policy REINFORCE with group-normalized advantages (GRPO-simplified)
+ SFT anchor, execution-grounded rewards (real build123d CAD + mimo judge + profit).

OpenRSI-style loop per iteration:
  1. merge current LoRA into base (GPU subprocess) -> rl_merged dir
  2. serve merged model with vLLM (subprocess, vllm_serve venv)
  3. rollout: 6 operator prompts (draft/improve/debug) x k samples
  4. reward each sample: CAD validity + judge rating + profit + reuse bonus
  5. train step: policy gradient on LoRA + SFT anchor on core replay
  6. checkpoint adapter; all rollouts logged as devready assets

Run (dd_qwen9b venv):
  MIMO_KEY=... python tools/prsi_rl_loop.py --iters 6
"""
import argparse, json, os, subprocess, sys, time, random, statistics
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
HERE = Path(__file__).resolve().parent
BENCH = HERE.parent
VLLM_PY = '/home/exuber/.venvs/vllm_serve/bin/python'
CAD_PY = '/home/exuber/CODE/CORE/pythonProject1/AUTORESEARCH/text-to-cad/.venv/bin/python'
CAD_ENV_PYTHONPATH = ('/home/exuber/CODE/CORE/pythonProject1/AUTORESEARCH/text-to-cad/packages/cadpy/src:'
                      '/home/exuber/CODE/CORE/pythonProject1/AUTORESEARCH/MechanogenesisBenchDEV/src')
BASE = '/home/exuber/models/qwen3.5-9b-bf16'
MERGED = '/home/exuber/models/qwen9b-prsi-rl-merged'
CKPT_ROOT = Path(os.environ.get('RL_CKPT', '/home/exuber/models/prsi_rl'))
OUT = BENCH / 'runs' / os.environ.get('RL_TAG', 'rl_v1')
PORT = 8100
MIMO_BASE = 'https://api.xiaomimimo.com/v1'

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

JUDGE_SYS = 'Rate the workstation design 0-10 for user satisfaction. Return ONLY JSON: {"rating":<n>,"accepted":<bool>,"feedback":"<t>"}'
ACCEPT = 5


def speed_price(secs):
    if secs < 10: return 1.5
    if secs < 30: return 1.2
    if secs < 60: return 1.0
    if secs < 120: return 0.8
    return 0.5


def build_env():
    """Frozen RL environment: operator-tagged prompts with real STEP capital."""
    sess = BENCH / 'runs' / 'control_experiments' / 'glm-5.3-flash' / 'treatment_20261003_145642'
    def cap_upto(n):  # capital {r1..rn} built from the frozen session chain
        c = {}
        for rd in range(n):
            for att in ('a0', 'a1'):
                p = sess / f'r{rd}_{att}' / 'cad' / 'design.step'
                if p.exists():
                    c[f'r{rd+1}'] = {'status': 'EXECUTED_CAD', 'step_path': str(p),
                                     'description': f'Round {rd+1} design', 'measurements': {}}
                    break
        return c

    def msg(demand, capital):
        return json.dumps({'demand': demand,
                           'capital': [{'id': k, 'desc': v['description']} for k, v in capital.items()],
                           'hint': 'Use capital(asset_id) to import previous modules.' if capital else None})

    prompts = [
        # draft x3: the eval demand plus dimension variants (R1 fails most in bench)
        {'op': 'draft', 'demand': DEMANDS[0], 'capital': {}, 'user': msg(DEMANDS[0], {})},
        {'op': 'draft', 'demand': 'Build a phone dock for 90x14x175mm phone. Desk 420x280mm. From scratch.',
         'capital': {}, 'user': msg('Build a phone dock for 90x14x175mm phone. Desk 420x280mm. From scratch.', {})},
        {'op': 'draft', 'demand': 'Build a phone dock for 160x9x78mm phone. Desk 300x200mm. From scratch.',
         'capital': {}, 'user': msg('Build a phone dock for 160x9x78mm phone. Desk 300x200mm. From scratch.', {})},
        # adapt + improve across capital depths
        {'op': 'improve', 'demand': DEMANDS[1], 'capital': cap_upto(1), 'user': msg(DEMANDS[1], cap_upto(1))},
        {'op': 'improve', 'demand': DEMANDS[2], 'capital': cap_upto(2), 'user': msg(DEMANDS[2], cap_upto(2))},
        {'op': 'improve', 'demand': DEMANDS[2], 'capital': cap_upto(1), 'user': msg(DEMANDS[2], cap_upto(1))},
        {'op': 'improve', 'demand': DEMANDS[3], 'capital': cap_upto(3), 'user': msg(DEMANDS[3], cap_upto(3))},
        # shrink (R5) x3 capital depths — R5 fails 10/10 in bench
        {'op': 'improve', 'demand': DEMANDS[4], 'capital': cap_upto(4), 'user': msg(DEMANDS[4], cap_upto(4))},
        {'op': 'improve', 'demand': DEMANDS[4], 'capital': cap_upto(3), 'user': msg(DEMANDS[4], cap_upto(3))},
        {'op': 'improve', 'demand': DEMANDS[4], 'capital': cap_upto(2), 'user': msg(DEMANDS[4], cap_upto(2))},
    ]
    # debug prompts reused verbatim from the gated debug corpus
    dbg = [json.loads(l) for l in (BENCH / 'runs' / 'training_data' / 'sft_v2_debug.jsonl').read_text().splitlines() if l.strip()]
    for e in dbg[:2]:
        u = json.loads(e['messages'][1]['content'])
        prompts.append({'op': 'debug', 'demand': u.get('demand', DEMANDS[0]), 'capital': {},
                        'user': e['messages'][1]['content'], 'system': e['messages'][0]['content']})
    for p in prompts:
        p.setdefault('system', SYSTEM)
    return prompts


# ── server lifecycle ──
def wait_server(timeout=420):
    import httpx
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            with httpx.Client(timeout=5, trust_env=False) as c:
                r = c.get(f'http://127.0.0.1:{PORT}/v1/models')
                if r.status_code == 200:
                    return True
        except Exception:
            pass
        time.sleep(5)
    return False


def merge_adapter(adapter, out_dir):
    """GPU merge: base BF16 + LoRA -> merged weights (subprocess so memory is reclaimed)."""
    script = f'''
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
m = AutoModelForCausalLM.from_pretrained("{BASE}", dtype=torch.bfloat16, device_map="cuda", trust_remote_code=True)
m = PeftModel.from_pretrained(m, "{adapter}")
m = m.merge_and_unload()
m.save_pretrained("{out_dir}")
AutoTokenizer.from_pretrained("{BASE}", trust_remote_code=True).save_pretrained("{out_dir}")
print("MERGED-OK")
'''
    r = subprocess.run([sys.executable, '-W', 'ignore', '-c', script],
                       capture_output=True, text=True, timeout=1200)
    ok = 'MERGED-OK' in r.stdout
    if not ok:
        print(r.stdout[-800:], r.stderr[-800:])
    return ok


def start_server():
    cmd = [VLLM_PY, '-m', 'vllm.entrypoints.openai.api_server',
           '--model', MERGED, '--served-model-name', 'rl-policy',
           '--port', str(PORT), '--max-model-len', '3072', '--gpu-memory-utilization', '0.93',
           '--enforce-eager', '--max-num-seqs', '6', '--max-num-batched-tokens', '4096',
           '--kv-cache-dtype', 'fp8']
    log = open(OUT / 'vllm.log', 'a')
    return subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT)


def rollout(prompts, k, temp=0.75):
    """Sample k completions per prompt via the completions API (exact training prompt format)."""
    import httpx
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(BASE, trust_remote_code=True)
    reqs = []
    for pi, p in enumerate(prompts):
        prompt = tok.apply_chat_template([{'role': 'system', 'content': p['system']},
                                          {'role': 'user', 'content': p['user']}],
                                         tokenize=False, add_generation_prompt=True, enable_thinking=False)
        for j in range(k):
            reqs.append({'pi': pi, 'op': p['op'], 'prompt': prompt, 'seed': j})

    def one(req):
        body = {'model': 'rl-policy', 'prompt': req['prompt'], 'max_tokens': 1800,
                'temperature': temp, 'top_p': 0.95, 'seed': req['seed']}
        t0 = time.monotonic()
        try:
            with httpx.Client(timeout=httpx.Timeout(420, connect=20), trust_env=False) as c:
                r = c.post(f'http://127.0.0.1:{PORT}/v1/completions', json=body,
                           headers={'Authorization': 'Bearer none'})
            dt = round(time.monotonic() - t0, 1)
            if r.status_code != 200:
                return {**req, 'text': '', 'secs': dt, 'tokens': 0}
            ch = r.json()['choices'][0]
            return {**req, 'text': ch['text'].strip(), 'secs': dt, 'tokens': r.json().get('usage', {}).get('completion_tokens', 0),
                    'finish': ch.get('finish_reason')}
        except Exception as e:
            return {**req, 'text': '', 'secs': round(time.monotonic() - t0, 1), 'tokens': 0, 'err': str(e)[:80]}

    with ThreadPoolExecutor(max_workers=6) as ex:
        return list(ex.map(one, reqs))


# ── execution-grounded reward ──
def cad_eval(text, capital, folder):
    folder = Path(folder); folder.mkdir(parents=True, exist_ok=True)
    ji, jo = folder / '_ji.json', folder / '_jo.json'
    ji.write_text(json.dumps({'text': text, 'capital': capital, 'folder': str(folder)}))
    env = dict(os.environ, PYTHONPATH=CAD_ENV_PYTHONPATH)
    try:
        subprocess.run([CAD_PY, str(HERE / 'cad_eval_worker.py'), str(ji), str(jo)],
                       env=env, capture_output=True, text=True, timeout=300)
        if jo.exists():
            return json.loads(jo.read_text())
    except Exception:
        pass
    return {'error': 'worker failed', 'metrics': None}


def judge(demand, text, metrics):
    import httpx
    key = os.environ.get('MIMO_KEY', 'none')
    prompt = (f"Demand: {demand}\nDesign: {text[:6000]}\nCAD facts: "
              f"{json.dumps({'envelope_excess_mm': (metrics or {}).get('occupied_envelope_excess_mm'), 'overlap_mm3': (metrics or {}).get('overlap_mm3')})}")
    for _ in range(2):
        try:
            with httpx.Client(timeout=httpx.Timeout(240, connect=20), trust_env=False) as c:
                r = c.post(f'{MIMO_BASE}/chat/completions',
                           headers={'Authorization': f'Bearer {key}'},
                           json={'model': 'mimo-v2.6-pro',
                                 'messages': [{'role': 'system', 'content': JUDGE_SYS},
                                              {'role': 'user', 'content': prompt}],
                                 'max_tokens': 2048, 'temperature': 0.2})
            if r.status_code != 200:
                continue
            t = (r.json()['choices'][0]['message'].get('content') or '').strip()
            if t.startswith('```'):
                t = t.split('\n', 1)[-1].rsplit('```', 1)[0].strip()
            i, j = t.find('{'), t.rfind('}')
            return json.loads(t[i:j+1]).get('rating', 0)
        except Exception:
            time.sleep(2)
    return 0


def reward_sample(s, p, workdir):
    """Collect reward COMPONENTS (no scalar yet — CARE assigns it per group)."""
    text = s['text']
    if not text or len(text) < 40:
        return {'r': 0.0, 'valid': False, 'rating': 0, 'sold': False, 'reused': False, 'rev': 0}
    if '"h":' in text and '"hypothesis":' not in text:
        text = text.replace('"h":', '"hypothesis":')
    cad = cad_eval(text, p['capital'], workdir)
    valid = bool(cad.get('metrics'))
    if p['op'] == 'debug':
        rating = judge(p['demand'], text, cad.get('metrics')) if valid else 0
        return {'r': round(0.5 * valid + 0.05 * rating, 4), 'valid': valid, 'rating': rating,
                'sold': False, 'reused': False, 'rev': 0, 'error': cad.get('error')}
    if not valid:
        return {'r': 0.0, 'valid': False, 'rating': 0, 'sold': False, 'reused': False, 'rev': 0,
                'error': cad.get('error')}
    rating = judge(p['demand'], text, cad.get('metrics'))
    sold = rating >= ACCEPT
    rev = round(100 * speed_price(s['secs'])) if sold else 0
    try:
        reused = any(n.get('op') == 'capital' and n.get('asset_id') in p['capital']
                     for n in json.loads(text).get('nodes', []))
    except Exception:
        reused = False
    return {'r': None, 'valid': True, 'rating': rating, 'sold': sold,
            'reused': reused, 'rev': rev}  # r filled by CARE


# ── CARE: Competence-Aware Reward-and-Advantage Engineering (arXiv:2609.29892) ──
# v3: efficiency refinement only near full saturation (p_high 0.9) with weaker
# token penalty — v2's p_high=0.75 entered efficiency too early and traded
# sold-rate for speed (bench ¥150 vs ¥280).
P_LOW, P_HIGH, LAMBDA_PROG, LAMBDA_EFF = 0.25, 0.9, 1.0, 0.3
MAX_TOK = 1800


def care_rewards(rollouts):
    """Per-prompt group: success rate s -> regime -> scalar reward.
    progress shaping (s<p_low): lambda_prog * R_prog (verified progress)
    outcome consolidation (mid): binary sold
    efficiency refinement (s>=p_high): sold - lambda_eff * e_i (token cost)."""
    groups = {}
    for s in rollouts:
        groups.setdefault(s['pi'], []).append(s)
    for pi, ss in groups.items():
        if ss[0]['operator'] == 'debug':
            for x in ss:
                x['rw']['regime'] = 'debug-static'
            continue
        s_rate = statistics.mean(1.0 * x['rw']['sold'] for x in ss)
        for x in ss:
            rw = x['rw']
            if s_rate < P_LOW:
                prog = 0.1 * rw['valid'] + 0.05 * rw['rating'] + (0.25 if rw['reused'] else 0.0)
                rw['r'] = round(LAMBDA_PROG * prog, 4)
                rw['regime'] = 'progress'
            elif s_rate < P_HIGH:
                # graded outcome: above-threshold ratings earn more (fights the
                # "just barely sell" equilibrium of a flat binary reward)
                rw['r'] = round(rw['sold'] * (0.6 + 0.04 * rw['rating']), 4)
                rw['regime'] = 'outcome'
            else:
                e = min(1.0, x.get('tokens', 0) / MAX_TOK)
                rw['r'] = round(rw['sold'] * (0.6 + 0.04 * rw['rating']) - LAMBDA_EFF * e, 4)
                rw['regime'] = 'efficiency'
            rw['group_s'] = round(s_rate, 3)


# ── training step ──
def train_step(adapter, rollouts, prompts, out_adapter, lr=3e-5, anchor_w=0.3, max_len=2600):
    """REINFORCE with group-normalized advantage + SFT anchor on core replay."""
    import torch
    import torch.nn.functional as F
    from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
    from peft import PeftModel, LoraConfig, TaskType, prepare_model_for_kbit_training

    # group-normalize advantages per prompt
    groups = {}
    for s in rollouts:
        groups.setdefault(s['pi'], []).append(s)
    train, n_skipped = [], 0
    for pi, ss in groups.items():
        rs = [x['rw']['r'] for x in ss]
        mu, sd = statistics.mean(rs), statistics.pstdev(rs)
        if sd < 1e-6:
            n_skipped += len(ss); continue
        for x in ss:
            train.append({'prompt': x['prompt'], 'text': x['text'], 'adv': (x['rw']['r'] - mu) / (sd + 1e-6)})
    if not train:
        print('  no signal groups; skipping train step')
        return False

    tok = AutoTokenizer.from_pretrained(BASE, trust_remote_code=True)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4',
                             bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True)
    model = AutoModelForCausalLM.from_pretrained(BASE, quantization_config=bnb,
                                                 device_map='cuda', trust_remote_code=True)
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant': False})
    model.config.use_cache = False
    model = PeftModel.from_pretrained(model, adapter, is_trainable=True)
    model.train()

    # SFT anchor replay
    core = [json.loads(l) for l in (BENCH / 'runs' / 'training_data' / 'sft_v2_core.jsonl').read_text().splitlines() if l.strip()]
    random.seed(41)

    def sft_batches():
        picks = random.sample(core, min(8, len(core)))
        out = []
        for e in picks:
            pr = tok.apply_chat_template(e['messages'][:2], tokenize=False, add_generation_prompt=True, enable_thinking=False)
            out.append((pr, e['messages'][2]['content']))
        return out

    def token_logp(logits, targets, p_len):
        """Chunked per-token logprob of targets (memory-safe: never floats the full vocab matrix)."""
        outs = []
        CH = 512
        for i in range(0, targets.shape[0], CH):
            lg = logits[i:i+CH].float()
            tg = targets[i:i+CH]
            lp = F.log_softmax(lg, dim=-1).gather(1, tg.unsqueeze(1)).squeeze(1)
            outs.append(lp)
        lp = torch.cat(outs)
        mask = torch.zeros_like(lp); mask[p_len-1:] = 1.0
        return lp, mask

    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=lr)
    random.shuffle(train)
    stats = {'pg': 0.0, 'n_pg': 0, 'ce': 0.0, 'n_ce': 0}
    for s in train:
        full = s['prompt'] + s['text']
        f_ids = tok(full, add_special_tokens=False, return_tensors='pt', truncation=True,
                    max_length=max_len)['input_ids'].to(model.device)
        if f_ids.shape[1] < 20 or f_ids.shape[1] >= max_len:
            continue
        p_len = len(tok(s['prompt'], add_special_tokens=False)['input_ids'])
        if p_len >= f_ids.shape[1]:
            continue
        out = model(input_ids=f_ids, labels=None)
        lp, mask = token_logp(out.logits[0, :-1], f_ids[0, 1:], p_len)
        loss = -(s['adv'] * (lp * mask).sum() / mask.sum().clamp(min=1))
        opt.zero_grad(); loss.backward(); opt.step()
        stats['pg'] += loss.item(); stats['n_pg'] += 1
    for pr, txt in sft_batches():
        full = pr + txt + tok.eos_token
        f_ids = tok(full, add_special_tokens=False, return_tensors='pt', truncation=True,
                    max_length=max_len)['input_ids'].to(model.device)
        p_len = len(tok(pr, add_special_tokens=False)['input_ids'])
        if p_len >= f_ids.shape[1]:
            continue
        out = model(input_ids=f_ids)
        lp, mask = token_logp(out.logits[0, :-1], f_ids[0, 1:], p_len)
        loss = -(lp * mask).sum() / mask.sum().clamp(min=1)
        opt.zero_grad(); (anchor_w * loss).backward(); opt.step()
        stats['ce'] += loss.item(); stats['n_ce'] += 1

    Path(out_adapter).mkdir(parents=True, exist_ok=True)
    model.save_pretrained(out_adapter)
    tok.save_pretrained(out_adapter)
    print(f"  train: pg_loss={stats['pg']/max(stats['n_pg'],1):.4f} over {stats['n_pg']} "
          f"| anchor_ce={stats['ce']/max(stats['n_ce'],1):.4f} over {stats['n_ce']} | skipped_groups={n_skipped}")
    del model
    import torch; torch.cuda.empty_cache()
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--iters', type=int, default=6)
    ap.add_argument('--k', type=int, default=6, help='samples per prompt')
    ap.add_argument('--init-adapter', default='/home/exuber/models/prsi_lora_v2/20261004_044136/final')
    a = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    CKPT_ROOT.mkdir(parents=True, exist_ok=True)
    prompts = build_env()
    print(f"RL env: {len(prompts)} prompts = " +
          str({op: sum(1 for p in prompts if p['op'] == op) for op in ('draft', 'improve', 'debug')}))
    adapter = a.init_adapter
    metrics_all = []
    assets = OUT / 'rollouts.jsonl'

    for it in range(1, a.iters + 1):
        t_it = time.monotonic()
        print(f"\n===== iteration {it} =====")
        if not merge_adapter(adapter, MERGED):
            print('merge failed; aborting'); break
        server = start_server()
        if not wait_server():
            print('server failed to start'); server.terminate(); break
        try:
            rollouts = rollout(prompts, a.k)
        finally:
            server.terminate()
            try: server.wait(timeout=60)
            except Exception: server.kill()
            subprocess.run(['pkill', '-f', 'vllm.entrypoints'], capture_output=True)
            time.sleep(8)

        # rewards (parallel judge+CAD)
        def score(s):
            p = prompts[s['pi']]
            wd = OUT / f'it{it}' / f"p{s['pi']}_s{s['seed']}"
            s['rw'] = reward_sample(s, p, wd)
            s['demand'] = p['demand']; s['operator'] = p['op']
            return s
        with ThreadPoolExecutor(max_workers=4) as ex:
            rollouts = list(ex.map(score, rollouts))
        care_rewards(rollouts)

        with assets.open('a') as f:
            for s in rollouts:
                f.write(json.dumps({k2: s.get(k2) for k2 in
                        ('operator', 'seed', 'secs', 'text', 'rw')}, ensure_ascii=False) + '\n')

        m = {'iter': it,
             'mean_r': round(statistics.mean(s['rw']['r'] for s in rollouts), 4),
             'valid': round(statistics.mean(1.0 * s['rw']['valid'] for s in rollouts), 3),
             'sold': round(statistics.mean(1.0 * s['rw']['sold'] for s in rollouts), 3),
             'reused_improve': round(statistics.mean([1.0 * s['rw']['reused'] for s in rollouts if s['operator'] == 'improve'] or [0]), 3),
             'mean_rating_valid': round(statistics.mean([s['rw']['rating'] for s in rollouts if s['rw']['valid']] or [0]), 2)}
        by_op = {}
        for op in ('draft', 'improve', 'debug'):
            rs = [s['rw']['r'] for s in rollouts if s['operator'] == op]
            if rs: by_op[op] = round(statistics.mean(rs), 4)
        m['mean_r_by_op'] = by_op
        from collections import Counter as _C
        m['care_regimes'] = dict(_C(s['rw'].get('regime', '?') for s in rollouts))
        m['wall_min'] = round((time.monotonic() - t_it) / 60, 1)
        metrics_all.append(m)
        (OUT / 'metrics.json').write_text(json.dumps(metrics_all, indent=2))
        print(f"  iter{it}: mean_r={m['mean_r']} valid={m['valid']} sold={m['sold']} "
              f"reuse(imp)={m['reused_improve']} rating={m['mean_rating_valid']} by_op={by_op} [{m['wall_min']}min]")

        nxt = str(CKPT_ROOT / f'iter{it}')
        # group-normalize advantages with CARE quality-preserving damping:
        # saturated groups (s->0 or 1) get damped so efficiency noise isn't amplified
        groups = {}
        for s in rollouts:
            groups.setdefault(s['pi'], []).append(s)
        train_samples, n_skipped = [], 0
        for pi, ss in groups.items():
            rs = [x['rw']['r'] for x in ss]
            mu, sd = statistics.mean(rs), statistics.pstdev(rs)
            if sd < 1e-6:
                n_skipped += len(ss); continue
            gs = ss[0]['rw'].get('group_s')
            w = max(0.25, min(1.0, 4.0 * gs * (1.0 - gs))) if gs is not None else 1.0
            for x in ss:
                train_samples.append({'prompt': x['prompt'], 'text': x['text'],
                                      'adv': w * (x['rw']['r'] - mu) / (sd + 1e-6)})
        if not train_samples:
            print('  no signal groups; keeping previous adapter')
            adapter = adapter
        else:
            job_f = OUT / f'train_job_it{it}.json'
            job_f.write_text(json.dumps({'adapter': adapter, 'out_adapter': nxt,
                                         'samples': train_samples,
                                         'core_path': str(BENCH / 'runs' / 'training_data' / 'sft_v2_core.jsonl'),
                                         'lr': 2e-5, 'anchor_w': 0.3, 'max_len': 2300}))
            r = subprocess.run([sys.executable, '-W', 'ignore', str(HERE / 'rl_train_step_worker.py'), str(job_f)],
                               capture_output=True, text=True, timeout=3600)
            line = [l for l in r.stdout.splitlines() if '"status"' in l]
            if line:
                st = json.loads(line[-1])
                print(f"  train: pg={st['pg']:.4f} over {st['n_pg']} | anchor_ce={st['ce']:.4f} over {st['n_ce']} | skipped={n_skipped}")
                adapter = nxt
            else:
                print(f'  train_step failed: {(r.stderr or r.stdout)[-300:]}')
                break

    print('\nfinal metrics:', json.dumps(metrics_all, indent=2))


if __name__ == '__main__':
    main()
