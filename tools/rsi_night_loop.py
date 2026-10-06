#!/usr/bin/env python3
"""Overnight RSI experiment: two arms x G generations, fully autonomous.

Arm RSI      : the model itself PROPOSES its training recipe each generation
               (operator mix, data top-q, lr, SFT anchor) from its own competence
               stats; SEAL-style posterior acceptance gate (rollback on probe
               degradation). This is the self-improvement mechanism under test.
Arm CONTROL  : identical loop, identical compute, FIXED recipe, no proposer,
               no acceptance gate. Any RSI-arm gain over this arm is attributable
               to self-proposed updates, not extra training.

Every generation:
  merge -> serve -> [RSI: propose recipe] -> rollout on FRESH parametric instances
  -> CARE rewards (real CAD, per-instance desk) -> recipe-filtered training ->
  adapter checkpoint -> SEALED probe (4 instances, exploit temp) -> chain hash.
Probes use instances the system NEVER trains on (probe_instances.json, fixed seed).

Usage:
  MIMO_KEY=... python tools/rsi_night_loop.py --arm rsi --gens 5 \
      --init-adapter /home/exuber/models/prsi_rl_v3/iter6
"""
import argparse, hashlib, json, os, random, statistics, subprocess, sys, time
from collections import Counter
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import money_bench_v5 as mb
from prsi_rl_loop import care_rewards, speed_price  # module-level reuse
import parametric_demands as PD

VLLM_PY = '/home/exuber/.venvs/vllm_serve/bin/python'
CAD_PY = '/home/exuber/CODE/CORE/pythonProject1/AUTORESEARCH/text-to-cad/.venv/bin/python'
CAD_ENV = ('/home/exuber/CODE/CORE/pythonProject1/AUTORESEARCH/text-to-cad/packages/cadpy/src:'
           '/home/exuber/CODE/CORE/pythonProject1/AUTORESEARCH/MechanogenesisBenchDEV/src')
BASE = '/home/exuber/models/qwen3.5-9b-bf16'
MERGED = '/home/exuber/models/qwen9b-rsi-night-merged'
OUT = HERE.parent / 'runs' / 'rsi_night'
PORT = 8100
MIMO_BASE = 'https://api.xiaomimimo.com/v1'
ACCEPT = 5
FROZEN_CHAIN = (HERE.parent / 'runs' / 'control_experiments' / 'glm-5.3-flash' /
                'treatment_20261003_145642')  # reproducible commercial capital STEP chain

DEFAULT_RECIPE = {'draft': 1.0, 'improve': 3.0, 'debug': 1.0, 'top_q': 0.5, 'lr': 2e-5, 'anchor': 0.3}


# ── infra ──
def merge_adapter(adapter):
    script = f'''
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
m = AutoModelForCausalLM.from_pretrained("{BASE}", dtype=torch.bfloat16, device_map="cuda", trust_remote_code=True)
m = PeftModel.from_pretrained(m, "{adapter}")
m = m.merge_and_unload()
m.save_pretrained("{MERGED}")
AutoTokenizer.from_pretrained("{BASE}", trust_remote_code=True).save_pretrained("{MERGED}")
print("MERGED-OK")
'''
    r = subprocess.run([sys.executable, '-W', 'ignore', '-c', script], capture_output=True, text=True, timeout=1500)
    return 'MERGED-OK' in r.stdout


def start_server():
    cmd = [VLLM_PY, '-m', 'vllm.entrypoints.openai.api_server', '--model', MERGED,
           '--served-model-name', 'rsi-policy', '--port', str(PORT), '--max-model-len', '3072',
           '--gpu-memory-utilization', '0.93', '--enforce-eager', '--max-num-seqs', '6',
           '--max-num-batched-tokens', '4096', '--kv-cache-dtype', 'fp8']
    log = open(OUT / 'vllm.log', 'a')
    return subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT)


def wait_server(timeout=420):
    import httpx
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            with httpx.Client(timeout=5, trust_env=False) as c:
                if c.get(f'http://127.0.0.1:{PORT}/v1/models').status_code == 200:
                    return True
        except Exception:
            pass
        time.sleep(5)
    return False


def stop_server():
    subprocess.run(['pkill', '-f', 'vllm.entrypoints'], capture_output=True)
    time.sleep(10)


def adapter_hash(path):
    f = Path(path) / 'adapter_model.safetensors'
    return hashlib.sha256(f.read_bytes()).hexdigest()[:16] if f.exists() else 'n/a'


# ── desk-aware CAD + judge ──
def cad_eval(text, capital, folder, desk):
    folder = Path(folder); folder.mkdir(parents=True, exist_ok=True)
    ji, jo = folder / '_ji.json', folder / '_jo.json'
    ji.write_text(json.dumps({'text': text, 'capital': capital, 'folder': str(folder), 'desk': list(desk)}))
    env = dict(os.environ, PYTHONPATH=CAD_ENV)
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
                r = c.post(f'{MIMO_BASE}/chat/completions', headers={'Authorization': f'Bearer {key}'},
                           json={'model': 'mimo-v2.6-pro',
                                 'messages': [{'role': 'system', 'content': mb.JUDGE_SYS},
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


# ── environment: fresh parametric contexts each generation ──
def frozen_capital(upto):
    cap = {}
    for rd in range(upto):
        for att in ('a0', 'a1'):
            p = FROZEN_CHAIN / f'r{rd}_{att}' / 'cad' / 'design.step'
            if p.exists():
                cap[f'r{rd+1}'] = {'status': 'EXECUTED_CAD', 'step_path': str(p),
                                   'description': f'Round {rd+1} design', 'measurements': {}}
                break
    return cap


def build_contexts(rng):
    """6 contexts from fresh instances + 2 fixed debug contexts."""
    def msg(demand, capital):
        return json.dumps({'demand': demand,
                           'capital': [{'id': k, 'desc': v['description']} for k, v in capital.items()],
                           'hint': 'Use capital(asset_id) to import previous modules.' if capital else None})

    instA, instB, instC = PD.sample_train(rng), PD.sample_train(rng), PD.sample_train(rng)
    ctxs = [
        {'op': 'draft', 'rd': 0, 'demand': instA['demands'][0], 'desk': instA['desk'], 'capital': {},
         'user': msg(instA['demands'][0], {})},
        {'op': 'improve', 'rd': 1, 'demand': instB['demands'][1], 'desk': instB['desk'], 'capital': frozen_capital(1),
         'user': msg(instB['demands'][1], frozen_capital(1))},
        {'op': 'improve', 'rd': 2, 'demand': instB['demands'][2], 'desk': instB['desk'], 'capital': frozen_capital(2),
         'user': msg(instB['demands'][2], frozen_capital(2))},
        {'op': 'improve', 'rd': 4, 'demand': instC['demands'][4], 'desk': instC['desk'], 'capital': frozen_capital(4),
         'user': msg(instC['demands'][4], frozen_capital(4))},
    ]
    dbg = [json.loads(l) for l in (HERE.parent / 'runs' / 'training_data' / 'sft_v2_debug.jsonl').read_text().splitlines() if l.strip()]
    for e in dbg[:2]:
        ctxs.append({'op': 'debug', 'rd': 0, 'demand': '', 'desk': (420, 280), 'capital': {},
                     'user': e['messages'][1]['content'], 'system_override': e['messages'][0]['content']})
    return ctxs


# ── rollout ──
SEED_OFFSET = 0


def rollout(ctxs, k, tok, temp=0.75):
    import httpx
    reqs = []
    for ci, c in enumerate(ctxs):
        system = c.get('system_override') or mb.SYSTEM
        prompt = tok.apply_chat_template([{'role': 'system', 'content': system},
                                          {'role': 'user', 'content': c['user']}],
                                         tokenize=False, add_generation_prompt=True, enable_thinking=False)
        for j in range(k):
            reqs.append({'ci': ci, 'op': c['op'], 'prompt': prompt, 'seed': j})

    def one(req):
        body = {'model': 'rsi-policy', 'prompt': req['prompt'], 'max_tokens': 1800,
                'temperature': temp, 'top_p': 0.95, 'seed': req['seed'] + SEED_OFFSET * 100}
        t0 = time.monotonic()
        try:
            with httpx.Client(timeout=httpx.Timeout(420, connect=20), trust_env=False) as c:
                r = c.post(f'http://127.0.0.1:{PORT}/v1/completions', json=body,
                           headers={'Authorization': 'Bearer none'})
            dt = round(time.monotonic() - t0, 1)
            if r.status_code != 200:
                return {**req, 'text': '', 'secs': dt, 'tokens': 0}
            ch = r.json()['choices'][0]
            return {**req, 'text': ch['text'].strip(), 'secs': dt,
                    'tokens': r.json().get('usage', {}).get('completion_tokens', 0)}
        except Exception as e:
            return {**req, 'text': '', 'secs': round(time.monotonic() - t0, 1), 'tokens': 0, 'err': str(e)[:80]}

    with ThreadPoolExecutor(max_workers=6) as ex:
        return list(ex.map(one, reqs))


def score_all(samples, ctxs, gen_dir):
    def score(s):
        c = ctxs[s['ci']]
        text = s['text']
        if not text or len(text) < 40:
            s['rw'] = {'r': 0.0, 'valid': False, 'rating': 0, 'sold': False, 'reused': False, 'rev': 0}
            s['op'] = c['op']; return s
        if '"h":' in text and '"hypothesis":' not in text:
            text = text.replace('"h":', '"hypothesis":')
        cad = cad_eval(text, c['capital'], gen_dir / f"p{s['ci']}_s{s['seed']}", c['desk'])
        valid = bool(cad.get('metrics'))
        if c['op'] == 'debug':
            rating = judge('workstation repair', text, cad.get('metrics')) if valid else 0
            s['rw'] = {'r': round(0.5 * valid + 0.05 * rating, 4), 'valid': valid, 'rating': rating,
                       'sold': False, 'reused': False, 'rev': 0, 'regime': 'debug-static'}
        elif not valid:
            s['rw'] = {'r': 0.0, 'valid': False, 'rating': 0, 'sold': False, 'reused': False, 'rev': 0}
        else:
            rating = judge(c['demand'], text, cad.get('metrics'))
            sold = rating >= ACCEPT
            rev = round(100 * speed_price(s['secs'])) if sold else 0
            try:
                reused = any(n.get('op') == 'capital' and n.get('asset_id') in c['capital']
                             for n in json.loads(text).get('nodes', []))
            except Exception:
                reused = False
            s['rw'] = {'r': None, 'valid': True, 'rating': rating, 'sold': sold,
                       'reused': reused, 'rev': rev}
        s['op'] = c['op']
        return s
    with ThreadPoolExecutor(max_workers=4) as ex:
        samples = list(ex.map(score, samples))
    for s in samples:  # aliases for care_rewards (expects pi/operator keys)
        s['pi'] = s['ci']
        s['operator'] = s['op']
    care_rewards(samples)
    return samples


# ── SEAL-style self-proposed recipe ──
PROPOSER_SYS = '''You are tuning your own next training round. Given your recent performance statistics,
propose a training recipe. Return ONLY JSON:
{"operator_mix": {"draft": <float weight>, "improve": <float>, "debug": <float>},
 "top_q": <0.3-0.9 keep top fraction of samples by reward>,
 "lr": <5e-6 to 5e-5>,
 "anchor": <0.1-0.5 sft anchor weight>}
Reason about your weakest operator (give it more weight), whether data quality or volume is the
bottleneck (top_q), and how stable recent updates were (lr, anchor).'''


def propose_recipe(stats, tok):
    import httpx
    prompt = f"Your recent generation statistics:\n{json.dumps(stats, indent=1)}\n\nPropose your next training recipe."
    msgs_prompt = tok.apply_chat_template([{'role': 'system', 'content': PROPOSER_SYS},
                                           {'role': 'user', 'content': prompt}],
                                          tokenize=False, add_generation_prompt=True, enable_thinking=False)
    body = {'model': 'rsi-policy', 'prompt': msgs_prompt, 'max_tokens': 800,
            'temperature': 0.4, 'seed': 7}
    try:
        with httpx.Client(timeout=httpx.Timeout(300, connect=20), trust_env=False) as c:
            r = c.post(f'http://127.0.0.1:{PORT}/v1/completions', json=body,
                       headers={'Authorization': 'Bearer none'})
        t = r.json()['choices'][0]['text'].strip()
        if t.startswith('```'):
            t = t.split('\n', 1)[-1].rsplit('```', 1)[0].strip()
        i, j = t.find('{'), t.rfind('}')
        rec = json.loads(t[i:j+1])
        mix = rec.get('operator_mix', {})
        out = {'draft': max(0.0, float(mix.get('draft', 1))), 'improve': max(0.0, float(mix.get('improve', 3))),
               'debug': max(0.0, float(mix.get('debug', 1))),
               'top_q': min(0.9, max(0.3, float(rec.get('top_q', 0.5)))),
               'lr': min(5e-5, max(5e-6, float(rec.get('lr', 2e-5)))),
               'anchor': min(0.5, max(0.1, float(rec.get('anchor', 0.3))))}
        return out, t
    except Exception as e:
        return None, f'proposer failed: {str(e)[:100]}'


def apply_recipe(samples, recipe):
    """Self-selected training data: operator reweighting + top-q by reward."""
    import random as _r
    rng = _r.Random(11)
    by_op = {}
    for s in samples:
        by_op.setdefault(s['op'], []).append(s)
    total_w = sum(recipe.get(op, 1.0) for op in by_op) or 1.0
    picked = []
    for op, ss in by_op.items():
        share = recipe.get(op, 1.0) / total_w
        n_target = max(1, round(share * 30))  # normalise to ~30 train samples
        ss = sorted(ss, key=lambda x: -x['rw']['r'])
        keep = max(1, round(len(ss) * recipe.get('top_q', 0.5)))
        pool = ss[:keep]
        picked += (pool * 4)[:n_target] if len(pool) < n_target else rng.sample(pool, min(n_target, len(pool)))
    return picked


# ── sealed probe (never trained on) ──
def probe(probe_instances, n_inst, tok):
    import httpx
    results = []
    for inst in probe_instances[:n_inst]:
        capital, total = {}, 0.0
        for rd in range(5):
            demand = inst['demands'][rd]
            user = json.dumps({'demand': demand,
                               'capital': [{'id': k, 'desc': v['description']} for k, v in capital.items()],
                               'hint': 'Use capital(asset_id) to import previous modules.' if capital else None})
            prompt = tok.apply_chat_template([{'role': 'system', 'content': mb.SYSTEM},
                                              {'role': 'user', 'content': user}],
                                             tokenize=False, add_generation_prompt=True, enable_thinking=False)
            best = None
            for att in range(2):
                body = {'model': 'rsi-policy', 'prompt': prompt, 'max_tokens': 2000,
                        'temperature': 0.3, 'seed': att + SEED_OFFSET * 10}
                t0 = time.monotonic()
                try:
                    with httpx.Client(timeout=httpx.Timeout(420, connect=20), trust_env=False) as c:
                        r = c.post(f'http://127.0.0.1:{PORT}/v1/completions', json=body,
                                   headers={'Authorization': 'Bearer none'})
                    text = r.json()['choices'][0]['text'].strip()
                except Exception:
                    continue
                if not text:
                    continue
                if '"h":' in text and '"hypothesis":' not in text:
                    text = text.replace('"h":', '"hypothesis":')
                secs = round(time.monotonic() - t0, 1)
                cad = cad_eval(text, capital, OUT / 'probe_cad' / f"{inst['family']}_{rd}_{att}", inst['desk'])
                if cad.get('metrics'):
                    best = (text, secs, cad)
                    break
            if best is None:
                continue
            text, secs, cad = best
            rating = judge(demand, text, cad.get('metrics'))
            if rating >= ACCEPT:
                total += round(100 * speed_price(secs))
            if rating >= 3:
                capital[f'r{rd+1}'] = {'status': 'EXECUTED_CAD', 'step_path': cad['step_path'],
                                       'description': f'Round {rd+1} design', 'measurements': {}}
        results.append({'family': inst['family'], 'profit': total})
    return results


# ── main loop ──
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--arm', choices=['rsi', 'control'], required=True)
    ap.add_argument('--gens', type=int, default=5)
    ap.add_argument('--init-adapter', default='/home/exuber/models/prsi_rl_v3/iter6')
    ap.add_argument('--seed-offset', type=int, default=0)
    a = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    global SEED_OFFSET
    SEED_OFFSET = a.seed_offset
    arm_dir = a.arm if a.seed_offset == 0 else f"{a.arm}_s{a.seed_offset}"
    (OUT / arm_dir).mkdir(exist_ok=True)
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(BASE, trust_remote_code=True)
    probe_instances = json.loads((OUT / 'probe_instances.json').read_text())

    adapter = a.init_adapter
    recipe = dict(DEFAULT_RECIPE)
    recipe_log, probe_log, chain = [], [], []
    last_probe_mean = None
    rng = random.Random(1234 + a.seed_offset * 10 + (0 if a.arm == 'rsi' else 1))

    # generation 0 probe (baseline of the init adapter)
    if not merge_adapter(adapter):
        print('init merge failed'); return
    srv = start_server()
    ok = wait_server()
    if ok:
        p0 = probe(probe_instances, 4, tok)
        last_probe_mean = statistics.mean([p['profit'] for p in p0])
        probe_log.append({'gen': 0, 'probe': p0, 'mean': last_probe_mean})
        (OUT / arm_dir / 'probe_log.json').write_text(json.dumps(probe_log, indent=2))
        print(f"gen0 probe baseline: {last_probe_mean:.0f}", flush=True)
    stop_server()

    for gen in range(1, a.gens + 1):
        t_gen = time.monotonic()
        print(f"\n===== [{a.arm}] generation {gen} =====", flush=True)
        if not merge_adapter(adapter):
            print('merge failed; aborting'); break
        srv = start_server()
        if not wait_server():
            print('server failed; aborting'); break
        try:
            # 1. self-proposed recipe (RSI arm) or frozen recipe (control)
            if a.arm == 'rsi' and last_probe_mean is not None and recipe_log:
                stats = recipe_log[-1].get('post_stats')
                if stats:
                    proposal, raw = propose_recipe(stats, tok)
                    if proposal:
                        recipe = proposal
                        print(f"  self-proposed recipe: mix={ {k: round(v,1) for k,v in proposal.items() if k in ('draft','improve','debug')} } "
                              f"top_q={proposal['top_q']:.2f} lr={proposal['lr']:.1e} anchor={proposal['anchor']:.2f}", flush=True)
                    else:
                        print(f"  {raw}; keeping previous recipe", flush=True)

            # 2. rollout on fresh parametric contexts + CARE rewards (server session 1)
            ctxs = build_contexts(rng)
            samples = rollout(ctxs, 6, tok)
            samples = score_all(samples, ctxs, OUT / arm_dir / f'gen{gen}')
            (OUT / arm_dir / f'gen{gen}_rollouts.jsonl').write_text(
                '\n'.join(json.dumps({k: s.get(k) for k in ('op', 'seed', 'secs', 'tokens', 'text', 'rw')},
                                     ensure_ascii=False) for s in samples) + '\n')
        finally:
            stop_server()

        post_stats = {
            'by_op': {op: {'mean_r': round(statistics.mean([s['rw']['r'] for s in samples if s['op'] == op]), 4),
                           'valid': round(statistics.mean([1.0 * s['rw']['valid'] for s in samples if s['op'] == op]), 3),
                           'sold': round(statistics.mean([1.0 * s['rw']['sold'] for s in samples if s['op'] == op]), 3)}
                       for op in ('draft', 'improve', 'debug')
                       if any(s['op'] == op for s in samples)},
            'last_probe_mean': last_probe_mean}

        # 3. recipe-filtered training data + train step (GPU free: server stopped)
        picked = apply_recipe(samples, recipe)
        groups = {}
        for s in picked:
            groups.setdefault(s['ci'], []).append(s)
        train_samples = []
        for ci, ss in groups.items():
            rs = [x['rw']['r'] for x in ss]
            mu, sd = statistics.mean(rs), statistics.pstdev(rs)
            if sd < 1e-6:
                continue
            gs = next((x['rw'].get('group_s') for x in ss if x['rw'].get('group_s') is not None), None)
            w = max(0.25, min(1.0, 4.0 * gs * (1 - gs))) if gs is not None else 1.0
            for x in ss:
                train_samples.append({'prompt': x['prompt'], 'text': x['text'],
                                      'adv': w * (x['rw']['r'] - mu) / (sd + 1e-6)})
        nxt = str(OUT / arm_dir / f'adapter_gen{gen}')
        job_f = OUT / arm_dir / f'train_job_gen{gen}.json'
        job_f.write_text(json.dumps({'adapter': adapter, 'out_adapter': nxt, 'samples': train_samples,
                                     'core_path': str(HERE.parent / 'runs' / 'training_data' / 'sft_v2_core.jsonl'),
                                     'lr': recipe['lr'], 'anchor_w': recipe['anchor'], 'max_len': 2300}))
        r = subprocess.run([sys.executable, '-W', 'ignore', str(HERE / 'rl_train_step_worker.py'), str(job_f)],
                           capture_output=True, text=True, timeout=3600)
        line = [l for l in r.stdout.splitlines() if '"status"' in l]
        if not line:
            print(f"  train failed: {(r.stderr or r.stdout)[-300:]}"); break
        st = json.loads(line[-1])
        print(f"  train: pg={st['pg']:.4f} over {st['n_pg']} | recipe kept {len(picked)}/{len(samples)}", flush=True)

        # 4. sealed probe on the candidate (server session 2)
        srv = start_server()
        if not wait_server():
            print('probe server failed; aborting'); break
        try:
            p = probe(probe_instances, 4, tok)
        finally:
            stop_server()
        p_mean = statistics.mean([x['profit'] for x in p])

        # 5. SEAL posterior acceptance: RSI arm rolls back on degradation
        accepted = True
        if a.arm == 'rsi' and last_probe_mean is not None and p_mean < 0.8 * last_probe_mean:
            accepted = False
            print(f"  posterior REJECT: probe {p_mean:.0f} < 0.8*{last_probe_mean:.0f}; rolling back", flush=True)
        else:
            adapter = nxt
        post_stats['accepted'] = accepted
        recipe_log.append({'gen': gen, 'recipe': recipe, 'post_stats': post_stats})
        probe_log.append({'gen': gen, 'probe': p, 'mean': p_mean, 'accepted': accepted})
        chain.append({'gen': gen, 'adapter': adapter, 'hash': adapter_hash(adapter), 'accepted': accepted})
        (OUT / arm_dir / 'recipe_log.json').write_text(json.dumps(recipe_log, indent=2))
        (OUT / arm_dir / 'probe_log.json').write_text(json.dumps(probe_log, indent=2))
        (OUT / arm_dir / 'chain.json').write_text(json.dumps(chain, indent=2))
        if accepted:
            last_probe_mean = p_mean
        print(f"  probe mean: {p_mean:.0f} (prev {last_probe_mean if not accepted else '--'}) "
              f"[{(time.monotonic()-t_gen)/60:.0f}min]", flush=True)

    print(f"\n[{a.arm}] DONE. probe trajectory: " +
          str([f"g{x['gen']}:{x['mean']:.0f}{'' if x.get('accepted', True) else '✗'}" for x in probe_log]))


if __name__ == '__main__':
    main()
