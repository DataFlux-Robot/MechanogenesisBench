#!/usr/bin/env python3
"""Harness v2 bench (Qwen-Planner-Agent style model-harness co-evolution):
  1. Error-feedback retry: attempt 2 receives the REAL CAD validation error from
     attempt 1 (execution evidence enters the next planning turn) — activates the
     Debug operator capability the SFT model was trained on.
  2. Outcome memory: capital descriptions carry the previous round's rating and
     judge feedback (persistent memory of what occurred).
Run against a local vLLM server. Same judges/pricing as money_bench_v5.

  python tools/harness_v2_bench.py --endpoint http://127.0.0.1:8100/v1 \
      --served-model qwen9b-rl-it3 --designer qwen9b-rl-it3-h2 --judges mimo-v2.6-pro --n 3
"""
import argparse, json, os, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import money_bench_v5 as mb

RESULTS_LOCAL = HERE.parent / 'runs' / 'local_bench'


def build_user(demand, capital, extra=None):
    """Capital entries carry outcome memory (rating + feedback)."""
    caps = []
    for k, v in capital.items():
        desc = v.get('description', '')
        mem = v.get('memory')
        if mem:
            desc = f"{desc}; rated {mem.get('rating')}/10; feedback: {mem.get('feedback', '')[:120]}"
        caps.append({'id': k, 'desc': desc})
    msg = {'demand': demand, 'capital': caps,
           'hint': 'Use capital(asset_id) to import previous modules.' if capital else None}
    if extra:
        msg.update(extra)
    return json.dumps(msg, ensure_ascii=False)


def call_design(spec, system, user, folder, label, max_tokens=None):
    from litellm import completion
    t0 = time.monotonic()
    try:
        r = completion(model=spec['model'], api_base=spec['api_base'], api_key='none',
                   messages=[{'role': 'system', 'content': system}, {'role': 'user', 'content': user}],
                   max_tokens=max_tokens or spec['max_tokens'], temperature=spec['temp'], timeout=600,
                   extra_body={'chat_template_kwargs': {'enable_thinking': False}})
    except Exception as e:
        print(f"    call error ({label}): {str(e)[:100]}")
        return '', 0.0
    raw = (r.choices[0].message.content or '').strip()
    if raw.startswith('```') and raw.count('```') >= 2:
        lines = raw.split('\n')
        if len(lines) >= 3:
            raw = '\n'.join(lines[1:-1]).strip() or raw
    if '"h":' in raw and '"hypothesis":' not in raw:
        raw = raw.replace('"h":', '"hypothesis":')
    secs = round(time.monotonic() - t0, 1)
    folder = Path(folder); folder.mkdir(parents=True, exist_ok=True)
    (folder / f'{label}.json').write_text(json.dumps({'text': raw, 'secs': secs}, ensure_ascii=False, indent=2))
    return raw, secs


def run_h2(spec, judges, dn, root, n_rounds=5, use_memory=False):
    """Error-feedback retry uses the EXACT debug-operator training format
    ({broken_design, error, hint} + DEBUG_SYS) so the capability is in-distribution.
    Outcome memory is optional (default off): memory-enriched capital descriptions are
    out-of-distribution for the current checkpoint (co-evolution requires training with it)."""
    root = Path(root); root.mkdir(parents=True, exist_ok=True)
    capital, rounds = {}, []
    total_rev = 0.0
    for rd in range(n_rounds):
        demand = mb.DEMANDS[rd]
        best = None
        last_text, last_err = None, None
        for att in range(2):
            if att == 1 and last_err and best is None:
                # in-distribution repair request (matches sft_v2_debug training prompts);
                # smaller budget so broken_design + prompt stay inside the 4096 window
                caps = []
                for k, v in capital.items():
                    d = v.get('description', '')
                    if use_memory and v.get('memory'):
                        d += f"; rated {v['memory'].get('rating')}/10; feedback: {v['memory'].get('feedback', '')[:120]}"
                    caps.append({'id': k, 'desc': d})
                user = json.dumps({'demand': demand, 'capital': caps,
                                   'broken_design': last_text[:3000], 'error': last_err,
                                   'hint': 'Repair the broken design JSON so it passes validation. Return ONLY the fixed JSON.'},
                                  ensure_ascii=False)
                system = mb.SYSTEM + '\nYou are repairing a broken design. Fix ONLY the reported errors; keep working parts.'
                text, secs = call_design(spec, system, user, root / f'r{rd}_a{att}', f'r{rd}_a{att}', max_tokens=2200)
                if not text.strip():
                    continue
                cad = mb.real_cad_eval(text, capital, root / f'r{rd}_a{att}' / 'cad')
                if cad.get('metrics'):
                    best = (text, secs, cad)
                    break
                last_text, last_err = text, cad.get('error', 'unknown')
                continue
            else:
                user = build_user(demand, capital)
                system = mb.SYSTEM
            text, secs = call_design(spec, system, user, root / f'r{rd}_a{att}', f'r{rd}_a{att}')
            if not text.strip():
                continue
            cad = mb.real_cad_eval(text, capital, root / f'r{rd}_a{att}' / 'cad')
            if cad.get('metrics'):
                best = (text, secs, cad)
                break
            last_text, last_err = text, cad.get('error', 'unknown')
        if best is None:
            rounds.append({'rd': rd, 'rating': 0, 'sold': False, 'rev': 0, 'reused': False, 'secs': 0})
            print(f"  R{rd+1}: ❌ no valid design")
            continue
        text, secs, cad = best
        scores = mb.multi_judge(judges, demand, text, cad, root, rd)
        ratings = [s['rating'] for s in scores if s['rating'] > 0]
        med = sorted(ratings)[len(ratings)//2] if ratings else 0
        fb = next((s['feedback'] for s in scores if s.get('feedback')), '')
        sold = med >= mb.ACCEPT
        rev = round(mb.PRICE * mb.speed_price(secs)) if sold else 0
        total_rev += rev
        reused = any(n.get('op') == 'capital' for n in json.loads(text).get('nodes', []))
        if sold or med >= 3:
            capital[f'r{rd+1}'] = {'status': 'EXECUTED_CAD', 'step_path': cad['step_path'],
                                   'description': f'Round {rd+1} design',
                                   'measurements': cad.get('metrics', {}),
                                   'memory': {'rating': med, 'feedback': fb[:150]}}
        rounds.append({'rd': rd, 'rating': med, 'sold': sold, 'rev': rev, 'reused': reused,
                       'secs': secs, 'cad': cad.get('facts_summary'), 'judge_feedback': fb[:150]})
        print(f"  R{rd+1}: {'✅' if sold else '❌'} {med}/10 {'♻️' if reused else '🔧'} {secs:.0f}s ¥{rev}")
    early = [r['secs'] for r in rounds[:2] if r['secs'] > 0]
    late = [r['secs'] for r in rounds[3:] if r['secs'] > 0]
    t_accel = round((sum(early)/max(len(early),1)) / (sum(late)/max(len(late),1)), 2) if late else None
    return {'designer': dn, 'rounds': rounds, 'profit': round(total_rev, 2),
            'revenue': total_rev, 'sold': f"{sum(1 for r in rounds if r['sold'])}/5",
            'reuse': f"{sum(1 for r in rounds if r.get('reused'))}/4", 't_accel': t_accel,
            'harness': 'v2-errorfeedback-outcomememory'}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--endpoint', required=True)
    ap.add_argument('--served-model', required=True)
    ap.add_argument('--designer', required=True)
    ap.add_argument('--judges', nargs='+', default=['mimo-v2.6-pro'])
    ap.add_argument('--n', type=int, default=3)
    ap.add_argument('--max-tokens', type=int, default=3000)
    ap.add_argument('--memory', action='store_true', help='enable outcome-memory capital descriptions (requires co-trained model)')
    a = ap.parse_args()

    mb.RESULTS = RESULTS_LOCAL
    spec = {'model': f"openai/{a.served_model}", 'api_base': a.endpoint, 'protocol': 'openai',
            'key_env': None, 'max_tokens': a.max_tokens, 'temp': 0.3}
    judges = {j: mb.MODELS[j] for j in a.judges if j in mb.MODELS}
    for k, v in judges.items():
        if v.get('key_env') and not os.environ.get(v['key_env']):
            print(f"FATAL: {v['key_env']} not set for judge {k}"); sys.exit(1)

    all_runs = []
    for i in range(a.n):
        root = RESULTS_LOCAL / a.designer / time.strftime('%Y%m%d_%H%M%S')
        print(f"\n🔧 harness-v2 bench: {a.designer} session {i+1}/{a.n}")
        r = run_h2(spec, judges, a.designer, root, use_memory=a.memory)
        (root / 'result.json').write_text(json.dumps(r, ensure_ascii=False, indent=2))
        mb.display(r)
        all_runs.append(r)
    out = RESULTS_LOCAL / f'{a.designer}_all_runs.json'
    out.write_text(json.dumps(all_runs, ensure_ascii=False, indent=2))
    profits = [r['profit'] for r in all_runs]
    print(f"\n{a.designer}: n={len(all_runs)} profit mean={sum(profits)/len(profits):.1f} runs={[round(p,1) for p in profits]}")


if __name__ == '__main__':
    main()
