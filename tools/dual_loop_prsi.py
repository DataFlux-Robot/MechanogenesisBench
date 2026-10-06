#!/usr/bin/env python3
"""Dual-loop PRSI x RSI experiment: TWO closed loops in one lineage.

Loop 1 (PRSI, production capital): each generation runs production on FIXED
  instances; outputs with execution-verified quality (rating >= 4) are curated
  into a capital LIBRARY that persists across generations and is offered as
  available capital in all subsequent rounds/generations.
Loop 2 (RSI, model): the model proposes its own training recipe; posterior
  acceptance gate on a sealed probe.

Three arms isolate the factors (the "base x RSI x capital" hypothesis):
  A full   : RSI loop ON  + capital library ACCUMULATES across generations
  B rsi    : RSI loop ON  + library RESET to the initial seed set each generation
  C capital: model FROZEN + capital library ACCUMULATES

Measure per generation: production profit on the fixed instances and
probe-with-capital profit on sealed instances (never trained on).
Interaction estimate: final(A) - final(B) - final(C) + gen0 baseline.

Usage:
  MIMO_KEY=... python tools/dual_loop_prsi.py --arm full --gens 4
"""
import argparse, hashlib, json, os, random, statistics, subprocess, sys, time
from collections import Counter
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import money_bench_v5 as mb
from rsi_night_loop import (merge_adapter, start_server, wait_server, stop_server,
                            cad_eval, judge, speed_price, apply_recipe, propose_recipe,
                            rollout, score_all, DEFAULT_RECIPE, ACCEPT, OUT)
import parametric_demands as PD

BASE = '/home/exuber/models/qwen3.5-9b-bf16'
DUAL = HERE.parent / 'runs' / 'dual_loop'
PORT = 8100
PROD_SEED = 555      # fixed production instances (same for every arm and generation)
N_PROD = 4           # production instances
N_ROUNDS = 3         # rounds per production instance
CURATE_RATING = 4    # min rating to promote an output into the library
PROBE_N = 4          # sealed probe instances (with library capital available)


def adapter_hash(path):
    f = Path(path) / 'adapter_model.safetensors'
    return hashlib.sha256(f.read_bytes()).hexdigest()[:16] if f.exists() else 'n/a'


def production_instances():
    rng = random.Random(PROD_SEED)
    return [PD.gen_instance(rng) for _ in range(N_PROD)]


def library_caps(library):
    return [{'id': k, 'desc': v['description']} for k, v in library.items()]


def user_msg(demand, library):
    return json.dumps({'demand': demand, 'capital': library_caps(library),
                       'hint': 'Use capital(asset_id) to import previous modules.' if library else None})


# ── one production pass: N_PROD instances x N_ROUNDS, curating assets ──
SEED_OFFSET = 0


def production_run(tok, library_state, gen, arm, adapter_label):
    """Returns (rounds_stats, new_assets). library_state mutates if accumulating."""
    import httpx
    insts = production_instances()
    stats, new_assets = [], []
    root = DUAL / arm / f'gen{gen}_prod'
    for ii, inst in enumerate(insts):
        cap = dict(library_state)  # session starts from the library
        for rd in range(N_ROUNDS):
            demand = inst['demands'][rd]
            prompt = tok.apply_chat_template(
                [{'role': 'system', 'content': mb.SYSTEM}, {'role': 'user', 'content': user_msg(demand, cap)}],
                tokenize=False, add_generation_prompt=True, enable_thinking=False)
            best = None
            for att in range(2):
                body = {'model': 'rsi-policy', 'prompt': prompt, 'max_tokens': 2000,
                        'temperature': 0.3, 'seed': att + SEED_OFFSET * 100}
                t0 = time.monotonic()
                try:
                    with httpx.Client(timeout=httpx.Timeout(420, connect=20), trust_env=False) as c:
                        r = c.post(f'http://127.0.0.1:{PORT}/v1/completions', json=body,
                                   headers={'Authorization': 'Bearer none'})
                    text = r.json()['choices'][0]['text'].strip()
                    secs = round(time.monotonic() - t0, 1)
                except Exception:
                    continue
                if not text:
                    continue
                if '"h":' in text and '"hypothesis":' not in text:
                    text = text.replace('"h":', '"hypothesis":')
                cad = cad_eval(text, cap, root / f'i{ii}_r{rd}_a{att}', inst['desk'])
                if cad.get('metrics'):
                    best = (text, secs, cad)
                    break
            if best is None:
                stats.append({'inst': ii, 'rd': rd, 'rating': 0, 'sold': False, 'rev': 0, 'valid': False})
                continue
            text, secs, cad = best
            rating = judge(demand, text, cad.get('metrics'))
            sold = rating >= ACCEPT
            rev = round(100 * speed_price(secs)) if sold else 0
            try:
                reused = any(n.get('op') == 'capital' for n in json.loads(text).get('nodes', []))
            except Exception:
                reused = False
            stats.append({'inst': ii, 'rd': rd, 'rating': rating, 'sold': sold, 'rev': rev,
                          'valid': True, 'reused': reused, 'secs': secs})
            # within-session capital growth (like the bench)
            if rating >= 3:
                cap[f's{ii}r{rd+1}'] = {'status': 'EXECUTED_CAD', 'step_path': cad['step_path'],
                                         'description': f"{inst['family']} round {rd+1} module",
                                         'measurements': {}}
            # library curation: promote high-quality outputs into the cross-gen library
            if rating >= CURATE_RATING:
                new_assets.append({f'{arm}g{gen}i{ii}r{rd+1}': {
                    'status': 'EXECUTED_CAD', 'step_path': cad['step_path'],
                    'description': f"{inst['family']} {'dock/base' if rd == 0 else 'module'} (rated {rating})",
                    'measurements': {}, 'rating': rating}})
    return stats, new_assets


def probe_with_capital(tok, library, gen, arm):
    """Sealed instances, 3-round sessions, library available from round 1."""
    import httpx
    probe_instances = json.loads((OUT / 'probe_instances.json').read_text())
    results = []
    for inst in probe_instances[:PROBE_N]:
        cap = dict(library)
        total = 0.0
        for rd in range(3):
            demand = inst['demands'][rd]
            prompt = tok.apply_chat_template(
                [{'role': 'system', 'content': mb.SYSTEM}, {'role': 'user', 'content': user_msg(demand, cap)}],
                tokenize=False, add_generation_prompt=True, enable_thinking=False)
            best = None
            for att in range(2):
                body = {'model': 'rsi-policy', 'prompt': prompt, 'max_tokens': 2000,
                        'temperature': 0.3, 'seed': att + gen * 10 + SEED_OFFSET * 100}
                t0 = time.monotonic()
                try:
                    with httpx.Client(timeout=httpx.Timeout(420, connect=20), trust_env=False) as c:
                        r = c.post(f'http://127.0.0.1:{PORT}/v1/completions', json=body,
                                   headers={'Authorization': 'Bearer none'})
                    text = r.json()['choices'][0]['text'].strip()
                    secs = round(time.monotonic() - t0, 1)
                except Exception:
                    continue
                if not text:
                    continue
                if '"h":' in text and '"hypothesis":' not in text:
                    text = text.replace('"h":', '"hypothesis":')
                cad = cad_eval(text, cap, DUAL / arm / f'probe_g{gen}' / f"{inst['family']}_{rd}_{att}", inst['desk'])
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
                cap[f'p{rd+1}'] = {'status': 'EXECUTED_CAD', 'step_path': cad['step_path'],
                                   'description': f'Round {rd+1} design', 'measurements': {}}
        results.append({'family': inst['family'], 'profit': total})
    return results


def rsi_train(adapter, library, gen, arm, recipe, train_job_path, tok):
    """Rollout+score (server must be UP) and prepare the train job.
    The train subprocess itself is run by the caller AFTER the server stops."""
    rng = random.Random(9000 + gen)
    instA, instB = PD.sample_train(rng), PD.sample_train(rng)

    def msg(demand, cap):
        return json.dumps({'demand': demand,
                           'capital': [{'id': k, 'desc': v['description']} for k, v in cap.items()],
                           'hint': 'Use capital(asset_id) to import previous modules.' if cap else None})

    ctxs = [
        {'op': 'draft', 'rd': 0, 'demand': instA['demands'][0], 'desk': instA['desk'], 'capital': {},
         'user': msg(instA['demands'][0], {})},
        {'op': 'improve', 'rd': 2, 'demand': instB['demands'][2], 'desk': instB['desk'], 'capital': dict(library),
         'user': msg(instB['demands'][2], library)},
        {'op': 'improve', 'rd': 1, 'demand': instB['demands'][1], 'desk': instB['desk'],
         'capital': {k: v for k, v in library.items() if list(library).index(k) < max(1, len(library)//2)},
         'user': msg(instB['demands'][1], {k: v for k, v in library.items() if list(library).index(k) < max(1, len(library)//2)})},
    ]
    dbg = [json.loads(l) for l in (HERE.parent / 'runs' / 'training_data' / 'sft_v2_debug.jsonl').read_text().splitlines() if l.strip()]
    for e in dbg[:1]:
        ctxs.append({'op': 'debug', 'rd': 0, 'demand': '', 'desk': (420, 280), 'capital': {},
                     'user': e['messages'][1]['content'], 'system_override': e['messages'][0]['content']})
    samples = rollout(ctxs, 6, tok)
    samples = score_all(samples, ctxs, DUAL / arm / f'gen{gen}_train')
    (DUAL / arm / f'gen{gen}_train_rollouts.jsonl').write_text(
        '\n'.join(json.dumps({k: s.get(k) for k in ('op', 'seed', 'secs', 'rw')}, ensure_ascii=False) for s in samples) + '\n')
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
    nxt = str(DUAL / arm / f'adapter_gen{gen}')
    job = {'adapter': adapter, 'out_adapter': nxt, 'samples': train_samples,
           'core_path': str(HERE.parent / 'runs' / 'training_data' / 'sft_v2_core.jsonl'),
           'lr': recipe['lr'], 'anchor_w': recipe['anchor'], 'max_len': 2300}
    Path(train_job_path).write_text(json.dumps(job))
    return {'job_path': train_job_path, 'nxt': nxt}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--arm', choices=['full', 'rsi', 'capital'], required=True)
    ap.add_argument('--gens', type=int, default=4)
    ap.add_argument('--init-adapter', default='/home/exuber/models/prsi_rl_v3/iter6')
    ap.add_argument('--seed-offset', type=int, default=0)
    a = ap.parse_args()
    DUAL.mkdir(parents=True, exist_ok=True)
    global SEED_OFFSET
    SEED_OFFSET = a.seed_offset
    arm_dir = a.arm if a.seed_offset == 0 else f"{a.arm}_s{a.seed_offset}"
    (DUAL / arm_dir).mkdir(exist_ok=True)
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(BASE, trust_remote_code=True)

    adapter = a.init_adater if False else a.init_adapter
    library = {}
    recipe = dict(DEFAULT_RECIPE)
    log = []
    last_probe = None

    for gen in range(1, a.gens + 1):
        t0 = time.monotonic()
        print(f"\n===== [{a.arm}] generation {gen} (library {len(library)} assets) =====", flush=True)
        if not (a.arm == 'capital' and gen > 1):  # frozen arm: adapter unchanged
            if not merge_adapter(adapter):
                print('merge failed'); break
        else:
            time.sleep(2)
        srv = start_server()
        if not wait_server():
            print('server failed'); break
        try:
            # Loop 1: production with current library (mutates library via curation)
            prod_stats, new_assets = production_run(tok, library, gen, a.arm, adapter)
            prod_profit = sum(s['rev'] for s in prod_stats)
            prod_sold = sum(1 for s in prod_stats if s['sold'])
            prod_reuse = sum(1 for s in prod_stats if s.get('reused'))
            print(f"  production: profit ¥{prod_profit} sold {prod_sold}/{len(prod_stats)} "
                  f"reuse {prod_reuse}/{len(prod_stats)}", flush=True)
            # Loop 1 curation policy per arm
            if a.arm in ('full', 'capital'):
                for asset in new_assets:
                    library.update(asset)
            # probe with current library (sealed instances)
            probe_res = probe_with_capital(tok, library, gen, a.arm)
            probe_mean = statistics.mean([p['profit'] for p in probe_res])
            print(f"  probe-with-capital: ¥{probe_mean:.0f} (library {len(library)})", flush=True)
        finally:
            stop_server()

        entry = {'gen': gen, 'adapter_hash': adapter_hash(adapter), 'library_size': len(library),
                 'prod_profit': prod_profit, 'prod_sold': prod_sold, 'prod_reuse': prod_reuse,
                 'prod_n': len(prod_stats), 'probe_mean': probe_mean, 'probe': probe_res}

        # Loop 2: RSI model update (full & rsi arms only)
        train_result = None
        if a.arm in ('full', 'rsi'):
            # server session 2: self-proposed recipe + training rollouts (server needed)
            srv = start_server()
            if not wait_server():
                print('train server failed'); break
            try:
                proposal, raw = propose_recipe({'by_op': {'improve': {'sold': prod_sold / max(len(prod_stats), 1)}},
                                                'last_probe_mean': last_probe}, tok) if last_probe is not None else (None, None)
                if proposal:
                    recipe = proposal
                    print(f"  self-proposed: mix={ {k: round(v,1) for k,v in proposal.items() if k in ('draft','improve','debug')} } "
                          f"lr={proposal['lr']:.1e}", flush=True)
                train_result = rsi_train(adapter, library, gen, a.arm, recipe,
                                         str(DUAL / arm_dir / f'train_job_gen{gen}.json'), tok)
            finally:
                stop_server()
            # train subprocess runs with the GPU free
            r = subprocess.run([sys.executable, '-W', 'ignore',
                                str(HERE / 'rl_train_step_worker.py'), train_result['job_path']],
                               capture_output=True, text=True, timeout=3600)
            line = [l for l in r.stdout.splitlines() if '"status"' in l]
            if not line:
                print(f"  train failed: {(r.stderr or r.stdout)[-200:]}"); break
            st = json.loads(line[-1])
            nxt = train_result['nxt']
            print(f"  train: pg={st['pg']:.4f} over {st['n_pg']}", flush=True)
            # posterior gate on probe
            if last_probe is not None and probe_mean < 0.8 * last_probe:
                print(f"  posterior REJECT (probe {probe_mean:.0f} < 0.8*{last_probe:.0f}); rolling back model", flush=True)
                entry['accepted'] = False
            else:
                adapter = nxt
                entry['accepted'] = True
            if a.arm == 'rsi':
                library = {}  # rsi-only arm: capital does NOT persist across generations
        else:
            entry['accepted'] = None  # capital arm: model frozen

        last_probe = max(probe_mean, last_probe or 0) if entry.get('accepted', True) else last_probe
        log.append(entry)
        (DUAL / arm_dir / 'log.json').write_text(json.dumps(log, indent=2))
        (DUAL / arm_dir / 'library.json').write_text(json.dumps({k: v for k, v in library.items()}, indent=2))
        print(f"  gen{gen} done [{(time.monotonic()-t0)/60:.0f}min]", flush=True)

    print(f"\n[{a.arm}] DONE: " + ' | '.join(
        f"g{x['gen']}:prod¥{x['prod_profit']}/probe¥{x['probe_mean']:.0f}/lib{x['library_size']}" for x in log))


if __name__ == '__main__':
    main()
