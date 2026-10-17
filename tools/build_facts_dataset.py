#!/usr/bin/env python3
"""Build a truth-anchored dataset: execution facts for archived CARE rollouts.

The rollout JSONL stores design texts but not the prompt/capital context. Capital
is reconstructed exactly: base prompt index -> build_env capital (frozen session
STEPs); reflect prompts -> the reflect_pool_{it-1} entry's capital. Row order in
each iteration's block is (prompt index outer, seed inner) with k=6 samples.
Each design is executed through the real build123d pipeline (cad_eval_worker).
"""
import json, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
BENCH = HERE.parent
CAD_PY = '/home/exuber/CODE/CORE/pythonProject1/AUTORESEARCH/text-to-cad/.venv/bin/python'
CAD_ENV = ('/home/exuber/CODE/CORE/pythonProject1/AUTORESEARCH/text-to-cad/packages/cadpy/src:'
           '/home/exuber/CODE/CORE/pythonProject1/AUTORESEARCH/MechanogenesisBenchDEV/src')
SESS = BENCH / 'runs' / 'control_experiments' / 'glm-5.3-flash' / 'treatment_20261003_145642'
OUT = BENCH / 'runs' / 'probes' / 'facts_from_rollouts.jsonl'
K = 6
DEMANDS = [
    "Build a phone dock for 78x12x160mm phone. Desk 420x280mm. From scratch.",
    "Customer upgraded to 90x14x175mm phone. Adapt the dock. MUST reuse the base from round 1.",
    "Add earbuds bay (65x48x28mm). MUST keep the adapted dock and add to it.",
    "Add tablet stand (250x10x175mm) behind. Combine all modules. MUST reuse dock+earbuds.",
    "Desk shrank to 300x200mm! Shrink but keep ALL functions. MUST optimize accumulated design.",
]


def cap_upto(n):
    c = {}
    for rd in range(n):
        for att in ('a0', 'a1'):
            p = SESS / f'r{rd}_{att}' / 'cad' / 'design.step'
            if p.exists():
                c[f'r{rd+1}'] = {'status': 'EXECUTED_CAD', 'step_path': str(p),
                                 'description': f'Round {rd+1} design', 'measurements': {}}
                break
    return c


def base_prompts():
    ps = [{'capital': {}} for _ in range(3)]                       # draft x3
    ps += [{'capital': cap_upto(1)}, {'capital': cap_upto(2)}, {'capital': cap_upto(1)},
           {'capital': cap_upto(3)}, {'capital': cap_upto(4)}, {'capital': cap_upto(3)},
           {'capital': cap_upto(2)}]                                # improve x7
    ps += [{'capital': {}}, {'capital': {}}]                        # debug x2
    return ps


def cad(text, capital, folder):
    folder = Path(folder); folder.mkdir(parents=True, exist_ok=True)
    ji, jo = folder / '_ji.json', folder / '_jo.json'
    ji.write_text(json.dumps({'text': text, 'capital': capital, 'folder': str(folder)}))
    env = dict(os.environ, PYTHONPATH=CAD_ENV)
    try:
        subprocess.run([CAD_PY, str(HERE / 'cad_eval_worker.py'), str(ji), str(jo)],
                       env=env, capture_output=True, text=True, timeout=180)
        if jo.exists():
            return json.loads(jo.read_text())
    except Exception:
        pass
    return None


def dir_index(run_dir):
    """Map design text -> (it, pi, seed) using the CAD work dirs written during
    the run (they exist exactly for rollouts with text >= 40 chars)."""
    idx = {}
    for d in run_dir.glob('it*/p*_s*'):
        it = int(d.parent.name[2:])
        pi_s = d.name.split('_')
        pi, seed = int(pi_s[0][1:]), int(pi_s[1][1:])
        ji = d / '_ji.json'
        if not ji.exists():
            continue
        try:
            txt = json.loads(ji.read_text())['text']
        except Exception:
            continue
        idx.setdefault(txt, []).append((it, pi, seed))
    return idx


def main():
    runs = sys.argv[1:] or ['care_v4', 'care_v4b', 'rl_v5b']
    base = base_prompts()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if OUT.exists():
        for line in open(OUT):
            try:
                done.add(json.loads(line)['key'])
            except Exception:
                pass
    todo = []
    for run in runs:
        rd = BENCH / 'runs' / run
        rf = rd / 'rollouts.jsonl'
        if not rf.exists():
            print(f'{run}: no rollouts'); continue
        idx = dir_index(rd)
        pools = {}
        rows = [json.loads(l) for l in open(rf)]
        used = set()
        for row in rows:
            txt = row.get('text') or ''
            hits = [h for h in idx.get(txt, []) if h not in used]
            if not hits:
                continue
            it, pi, seed = hits[0]
            used.add(hits[0])
            if pi < len(base):
                capital = base[pi]['capital']
            else:
                t = it - 1
                if t not in pools:
                    pp = rd / f'reflect_pool_it{t}.json'
                    pools[t] = json.loads(pp.read_text()) if pp.exists() else []
                idxr = pi - len(base)
                capital = pools[t][idxr]['capital'] if idxr < len(pools[t]) else {}
            key = f'{run}:it{it}:p{pi}:s{seed}'
            if key in done:
                continue
            todo.append((key, run, it, pi, seed, txt, capital))
    print(f'[facts] {len(todo)} designs to execute ({len(done)} already done)', flush=True)

    def work(t):
        key, run, it, pi, seed, text, capital = t
        folder = BENCH / 'runs' / 'probes' / 'cad' / run / f'it{it}' / f'p{pi}_s{seed}'
        res = cad(text, capital, folder)
        m = (res or {}).get('metrics')
        return {'key': key, 'run': run, 'it': it, 'pi': pi, 'seed': seed,
                'input_len': len(text),
                'valid': bool(m),
                'excess': float((m or {}).get('occupied_envelope_excess_mm', 0) or 0) if m else None,
                'overlap': float((m or {}).get('overlap_mm3', 0) or 0) if m else None,
                'text': text}

    with OUT.open('a') as f, ThreadPoolExecutor(max_workers=4) as ex:
        for i, r in enumerate(ex.map(work, todo), 1):
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
            if i % 100 == 0:
                f.flush()
                print(f'  {i}/{len(todo)}', flush=True)
    print('done ->', OUT)


if __name__ == '__main__':
    main()
