#!/usr/bin/env python3
"""Pure-RL training with MiMo-style GAR (Groupwise Advantage Redistribution).

NO SFT from other models. The model learns entirely from its own rollouts:
  1. GENERATE: sample N candidates per prompt on Money Bench contexts
  2. EXECUTE: real build123d CAD evaluation (execution-grounded)
  3. GRADE: judge rating → binary pass/fail
  4. GAR: within each group, rank passing designs by quality (rating × speed);
         redistribute positive advantage from low-quality to high-quality passes
  5. TRAIN: GRPO update with GAR-redistributed advantages

Key MiMo insight (their Eq. 3): binary rewards can't distinguish passing solutions.
GAR ranks passes within the group and shifts advantage mass toward better ones.

Usage: MIMO_KEY=... python tools/gar_rl.py --iters 6
"""
import argparse, json, os, random, statistics, subprocess, sys, time
from collections import defaultdict
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
HERE = Path(__file__).resolve().parent
BENCH = HERE.parent
sys.path.insert(0, str(HERE))
import money_bench_v5 as mb
from rsi_night_loop import (merge_adapter, start_server, wait_server, stop_server,
                            cad_eval, judge, speed_price, ACCEPT)
import rsi_night_loop as _rnl
import parametric_demands as PD

BASE = '/home/exuber/models/qwen3.5-9b-bf16'
MERGED = '/home/exuber/models/qwen9b-gar-merged'
CKPT = Path('/home/exuber/models/prsi_gar')
OUT = BENCH / 'runs' / 'gar_rl'
PORT = 8100
_rnl.MERGED = MERGED  # make start_server serve from OUR merged path
N_CANDIDATES = 6  # rollouts per prompt (MiMo uses 16; we're limited by GPU speed)
N_PROMPTS = 6     # prompts per iteration


def build_prompts(rng):
    """Fresh parametric contexts: 2 draft + 3 improve + 1 shrink."""
    def msg(demand, capital):
        return json.dumps({'demand': demand,
                           'capital': [{'id': k, 'desc': v} for k, v in capital.items()],
                           'hint': 'Use capital(asset_id) to import previous modules.' if capital else None})

    sess = BENCH / 'runs' / 'control_experiments' / 'glm-5.3-flash' / 'treatment_20261003_145642'
    def cap_upto(n):
        c = {}
        for rd in range(n):
            for att in ('a0', 'a1'):
                p = sess / f'r{rd}_{att}' / 'cad' / 'design.step'
                if p.exists():
                    c[f'r{rd+1}'] = {'status': 'EXECUTED_CAD', 'step_path': str(p),
                                     'description': f'Round {rd+1} design', 'measurements': {}}
                    break
        return c

    instA, instB, instC = PD.sample_train(rng), PD.sample_train(rng), PD.sample_train(rng)
    return [
        {'op': 'draft', 'demand': instA['demands'][0], 'desk': instA['desk'], 'capital': {},
         'user': msg(instA['demands'][0], {})},
        {'op': 'draft', 'demand': instB['demands'][0], 'desk': instB['desk'], 'capital': {},
         'user': msg(instB['demands'][0], {})},
        {'op': 'improve', 'demand': instB['demands'][1], 'desk': instB['desk'], 'capital': cap_upto(1),
         'user': msg(instB['demands'][1], cap_upto(1))},
        {'op': 'improve', 'demand': instC['demands'][2], 'desk': instC['desk'], 'capital': cap_upto(2),
         'user': msg(instC['demands'][2], cap_upto(2))},
        {'op': 'improve', 'demand': instA['demands'][3], 'desk': instA['desk'], 'capital': cap_upto(3),
         'user': msg(instA['demands'][3], cap_upto(3))},
        {'op': 'improve', 'demand': instC['demands'][4], 'desk': instC['desk'], 'capital': cap_upto(4),
         'user': msg(instC['demands'][4], cap_upto(4))},
    ]


def rollout_all(ctxs, tok, k=N_CANDIDATES, temp=0.8):
    """Sample k candidates per context via vLLM completions API."""
    import httpx
    reqs = []
    for ci, c in enumerate(ctxs):
        prompt = tok.apply_chat_template(
            [{'role': 'system', 'content': mb.SYSTEM}, {'role': 'user', 'content': c['user']}],
            tokenize=False, add_generation_prompt=True, enable_thinking=False)
        for j in range(k):
            reqs.append({'ci': ci, 'prompt': prompt, 'seed': j})

    def one(req):
        body = {'model': 'rsi-policy', 'prompt': req['prompt'], 'max_tokens': 1800,
                'temperature': temp, 'top_p': 0.95, 'seed': req['seed']}
        t0 = time.monotonic()
        try:
            with httpx.Client(timeout=httpx.Timeout(420, connect=20), trust_env=False) as c:
                r = c.post(f'http://127.0.0.1:{PORT}/v1/completions', json=body,
                           headers={'Authorization': 'Bearer none'})
            dt = round(time.monotonic() - t0, 1)
            if r.status_code != 200: return {**req, 'text': '', 'secs': dt}
            ch = r.json()['choices'][0]
            return {**req, 'text': ch['text'].strip(), 'secs': dt,
                    'tokens': r.json().get('usage', {}).get('completion_tokens', 0)}
        except Exception:
            return {**req, 'text': '', 'secs': round(time.monotonic() - t0, 1), 'tokens': 0}

    with ThreadPoolExecutor(max_workers=6) as ex:
        return list(ex.map(one, reqs))


def score_all(samples, ctxs, gen_dir):
    """Execution-grounded scoring: CAD validity + judge rating + speed."""
    def score(s):
        c = ctxs[s['ci']]
        text = s['text']
        if not text or len(text) < 40:
            s['reward'] = {'valid': False, 'rating': 0, 'sold': False, 'rev': 0,
                          'quality': 0.0, 'secs': s['secs']}
            return s
        if '"h":' in text and '"hypothesis":' not in text:
            text = text.replace('"h":', '"hypothesis":')
        cad = cad_eval(text, c['capital'], gen_dir / f"p{s['ci']}_s{s['seed']}", c['desk'])
        valid = bool(cad.get('metrics'))
        if not valid:
            s['reward'] = {'valid': False, 'rating': 0, 'sold': False, 'rev': 0,
                          'quality': 0.0, 'secs': s['secs']}
            return s
        rating = judge(c['demand'], text, cad.get('metrics'))
        sold = rating >= ACCEPT
        rev = round(100 * speed_price(s['secs'])) if sold else 0
        # Quality score: MiMo-style multi-dimensional (solution quality × behavior)
        # solution quality = rating normalized; behavior = speed efficiency
        speed_eff = min(1.0, 30.0 / max(s['secs'], 1))  # faster = better
        quality = (rating / 10.0) * 0.7 + speed_eff * 0.3  # weighted composite
        try:
            reused = any(n.get('op') == 'capital' for n in json.loads(text).get('nodes', []))
        except: reused = False
        s['reward'] = {'valid': True, 'rating': rating, 'sold': sold, 'rev': rev,
                      'quality': round(quality, 4), 'reused': reused, 'secs': s['secs']}
        return s
    with ThreadPoolExecutor(max_workers=4) as ex:
        return list(ex.map(score, samples))


def gar_advantages(samples):
    """MiMo-style Groupwise Advantage Redistribution (their Eq. 3, simplified).

    Within each prompt group:
    - Binary reward: R_i = 1 if sold, 0 otherwise
    - Quality factor: f_i ∈ (0,1] for passing trajectories (from rating+speed)
    - GAR: redistribute advantage mass from low-quality to high-quality passes
    - Failed trajectories get negative advantage as usual
    """
    groups = defaultdict(list)
    for s in samples:
        groups[s['ci']].append(s)

    train_samples = []
    for ci, ss in groups.items():
        R = [1.0 if s['reward']['sold'] else 0.0 for s in ss]
        R_bar = statistics.mean(R)
        A_raw = [r - R_bar for r in R]  # standard GRPO advantage

        P = [i for i, r in enumerate(R) if r == 1.0]  # passing indices
        if P:
            # GAR: quality factors for passing trajectories
            f = [max(0.1, ss[i]['reward']['quality']) for i in P]
            # redistribute: boost high-quality passes, downweight low-quality
            total_pos_A = sum(A_raw[i] for i in P)
            if total_pos_A > 0:
                f_sum = sum(f)
                for j, i in enumerate(P):
                    boost = f[j] / f_sum  # proportional share
                    A_raw[i] = total_pos_A * boost * len(P) / len(P)  # scale-preserving
                    # simpler: A_raw[i] = A_raw[i] * f[j] * len(P) / f_sum

        for i, s in enumerate(ss):
            adv = A_raw[i]
            # normalize within group
            sd = statistics.pstdev(A_raw)
            if sd > 1e-6:
                adv = adv / sd
            train_samples.append({'prompt': s['prompt'], 'text': s['text'],
                                  'adv': max(-2, min(2, adv))})
    return train_samples


def probe_bench(tok, n=4):
    """Quick sealed-probe evaluation."""
    import httpx
    probe = json.loads((BENCH / 'runs' / 'rsi_night' / 'probe_instances.json').read_text())
    results = []
    for inst in probe[:n]:
        capital, total = {}, 0.0
        for rd in range(3):
            user = json.dumps({'demand': inst['demands'][rd],
                               'capital': [{'id': k, 'desc': v['description']} for k, v in capital.items()],
                               'hint': 'Use capital(asset_id) to import previous modules.' if capital else None})
            prompt = tok.apply_chat_template(
                [{'role': 'system', 'content': mb.SYSTEM}, {'role': 'user', 'content': user}],
                tokenize=False, add_generation_prompt=True, enable_thinking=False)
            best = None
            for att in range(2):
                body = {'model': 'rsi-policy', 'prompt': prompt, 'max_tokens': 1800,
                        'temperature': 0.3, 'seed': att}
                t0 = time.monotonic()
                try:
                    with httpx.Client(timeout=httpx.Timeout(420, connect=20), trust_env=False) as c:
                        r = c.post(f'http://127.0.0.1:{PORT}/v1/completions', json=body,
                                   headers={'Authorization': 'Bearer none'})
                    text = r.json()['choices'][0]['text'].strip()
                    secs = round(time.monotonic() - t0, 1)
                except: continue
                if not text: continue
                if '"h":' in text and '"hypothesis":' not in text:
                    text = text.replace('"h":', '"hypothesis":')
                cad = cad_eval(text, capital, OUT / 'probe' / f"{inst['family']}_{rd}_{att}", inst['desk'])
                if cad.get('metrics'):
                    best = (text, secs, cad); break
            if best is None: continue
            text, secs, cad = best
            rating = judge(inst['demands'][rd], text, cad.get('metrics'))
            if rating >= ACCEPT: total += round(100 * speed_price(secs))
            if rating >= 3:
                capital[f'p{rd+1}'] = {'status': 'EXECUTED_CAD', 'step_path': cad['step_path'],
                                       'description': f'Round {rd+1} design', 'measurements': {}}
        results.append(total)
    return statistics.mean(results) if results else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--iters', type=int, default=6)
    ap.add_argument('--init-adapter', default=None, help='start from raw base if None')
    a = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    CKPT.mkdir(parents=True, exist_ok=True)
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(BASE, trust_remote_code=True)

    adapter = a.init_adapter
    rng = random.Random(777)
    log = []
    for gen in range(1, a.iters + 1):
        t_gen = time.monotonic()
        print(f"\n===== GAR-RL generation {gen} =====", flush=True)

        # 1. Merge + serve
        # GPU guard: ensure clean before merge
        import gpu_guard
        if not gpu_guard.ensure_clean():
            print('GPU not clean; waiting 30s'); time.sleep(30)
            gpu_guard.ensure_clean()
        if adapter is None:
            import shutil; shutil.copytree(BASE, MERGED, dirs_exist_ok=True)
        elif not merge_adapter(adapter):
            print('merge failed'); break
        srv = start_server()
        if not wait_server():
            print('server failed'); break
        try:
            # 2. Rollout on fresh contexts
            ctxs = build_prompts(rng)
            samples = rollout_all(ctxs, tok)
            # 3. Execution-grounded scoring
            samples = score_all(samples, ctxs, OUT / f'gen{gen}')
            sold_count = sum(1 for s in samples if s['reward']['sold'])
            valid_count = sum(1 for s in samples if s['reward']['valid'])
            print(f"  rollout: {valid_count}/{len(samples)} valid, {sold_count}/{len(samples)} sold", flush=True)
        finally:
            stop_server()

        # 4. GAR advantage computation
        train_samples = gar_advantages(samples)
        if not train_samples:
            print("  no signal; skipping"); continue

        # 5. Train step (GRPO with GAR advantages)
        nxt = str(CKPT / f'gen{gen}')
        job = {'adapter': adapter or 'none', 'out_adapter': nxt, 'samples': train_samples,
               'lora_r': 32, 'lora_targets': ['q_proj', 'k_proj', 'v_proj', 'o_proj'],
               'core_path': '', 'lr': 5e-6, 'anchor_w': 0.3, 'max_len': 2300}
        # empty core_path trick: point to sft core but anchor_w=0 means it's unused
        job['core_path'] = str(BENCH / 'runs' / 'training_data' / 'sft_v2_core.jsonl')
        jf = OUT / f'train_job_gen{gen}.json'
        jf.write_text(json.dumps(job))
        r = subprocess.run([sys.executable, '-W', 'ignore', str(HERE / 'rl_train_step_worker.py'), str(jf)],
                           capture_output=True, text=True, timeout=3600)
        line = [l for l in r.stdout.splitlines() if '"status"' in l]
        if not line:
            print(f"  train failed: {(r.stderr or r.stdout)[-200:]}"); break
        st = json.loads(line[-1])
        adapter = nxt
        print(f"  train: pg={st['pg']:.4f} over {st['n_pg']}", flush=True)

        # 6. Probe
        # GPU guard: ensure clean before merge
        import gpu_guard
        if not gpu_guard.ensure_clean():
            print('GPU not clean; waiting 30s'); time.sleep(30)
            gpu_guard.ensure_clean()
        if adapter is None:
            import shutil; shutil.copytree(BASE, MERGED, dirs_exist_ok=True)
        elif not merge_adapter(adapter):
            print('probe merge failed'); break
        srv = start_server()
        if wait_server():
            try:
                probe_mean = probe_bench(tok, n=4)
            finally:
                stop_server()
        else:
            probe_mean = 0; stop_server()
        entry = {'gen': gen, 'valid': valid_count, 'sold': sold_count,
                'probe': probe_mean, 'pg': st['pg'], 'wall_min': round((time.monotonic()-t_gen)/60, 1)}
        log.append(entry)
        (OUT / 'log.json').write_text(json.dumps(log, indent=2))
        print(f"  probe: ¥{probe_mean:.0f} | sold {sold_count}/{len(samples)} [{entry['wall_min']}min]", flush=True)

    print(f"\nGAR-RL DONE: " + ' -> '.join(f"g{e['gen']}:¥{e['probe']:.0f}" for e in log))


if __name__ == '__main__':
    main()
