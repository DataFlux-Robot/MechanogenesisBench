#!/usr/bin/env python3
"""Generalization bench for the fine-tuned PRSI model (NMI reviewer concern #1).

Test A — held-out demands: NEW 5-round cumulative sequence (headphone-stand family)
         with the model's TRAINED system prompt. Isolates demand-level generalization
         from prompt-format shift. If profit holds ~¥300, the model learned cumulative
         design + capital reuse, not the 5 training demands.
Test B — fixture domain: the multi-domain fixture demands with the fixture system
         prompt (same protocol the commercial baselines got, n=1 baseline numbers exist).

Usage (text-to-cad venv):
  MIMO_KEY=... python tools/gen_bench.py --endpoint http://127.0.0.1:8100/v1 \
      --served-model care-v3-it6 --tag care-v3 --test heldout --n 10
"""
import argparse, json, os, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import money_bench_v5 as mb
import multi_domain_bench as mdb
from multi_domain_bench import run_domain, SYSTEMS, DOMAIN_FIXTURE

RESULTS = HERE.parent / 'runs' / 'generalization'

# held-out workstation-family demands (never seen in SFT or RL)
HELDOUT_WS = {
    'name': 'heldout-workstation',
    'demands': [
        "Build a headphone stand for 210x95mm over-ear headphones. Desk 420x280mm. From scratch.",
        "Headphones upgraded to 230x105mm. Adapt the stand. MUST reuse the base from round 1.",
        "Add an in-ear bud tray (80x60x25mm). MUST keep the adapted stand and add to it.",
        "Add a cable riser arm (150mm reach) behind. Combine all modules. MUST reuse stand+tray.",
        "Desk shrank to 320x220mm! Shrink but keep ALL functions. MUST optimize accumulated design.",
    ],
    'desk': (420, 280),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--endpoint', required=True)
    ap.add_argument('--served-model', required=True)
    ap.add_argument('--tag', required=True)
    ap.add_argument('--test', choices=['heldout', 'fixture', 'both'], default='heldout')
    ap.add_argument('--judges', nargs='+', default=['mimo-v2.6-pro'])
    ap.add_argument('--n', type=int, default=10)
    a = ap.parse_args()

    for j in a.judges:
        if mb.MODELS[j].get('key_env') and not os.environ.get(mb.MODELS[j]['key_env']):
            print(f"FATAL: {mb.MODELS[j]['key_env']} not set"); sys.exit(1)
    judges = {j: mb.MODELS[j] for j in a.judges}

    spec = {'model': f"openai/{a.served_model}", 'api_base': a.endpoint, 'protocol': 'openai',
            'key_env': None, 'max_tokens': 3000, 'temp': 0.3}
    import litellm
    _orig = litellm.completion
    def _nothink(*args, **kw):
        kw.setdefault('extra_body', {}).setdefault('chat_template_kwargs', {})['enable_thinking'] = False
        return _orig(*args, **kw)
    litellm.completion = _nothink

    RESULTS.mkdir(parents=True, exist_ok=True)
    domains = []
    if a.test in ('heldout', 'both'):
        domains.append((HELDOUT_WS, mb.SYSTEM))  # trained system, new demands
    if a.test in ('fixture', 'both'):
        domains.append((DOMAIN_FIXTURE, SYSTEMS['fixture']))

    def run_custom(spec, judges, dn, dom, system, root):
        """5 rounds of cumulative design in a custom domain (real CAD + judges + pricing)."""
        root = Path(root); root.mkdir(parents=True, exist_ok=True)
        capital, rounds = {}, []
        total = 0.0
        for rd in range(5):
            demand = dom['demands'][rd]
            best = None
            for att in range(2):
                label = f'r{rd}_a{att}'
                msg = json.dumps({'demand': demand,
                                  'capital': [{'id': k, 'desc': v.get('description', '')} for k, v in capital.items()],
                                  'hint': 'Use capital(asset_id) to import previous modules.' if capital else None})
                try:
                    text, usage, secs = mb.call(spec, system, msg, root / label, label)
                    if not text.strip():
                        continue
                    cad = mb.real_cad_eval(text, capital, root / label / 'cad', desk=dom['desk'])
                    if cad.get('metrics'):
                        best = (text, usage, cad, secs)
                        break
                except Exception:
                    continue
            if best is None:
                rounds.append({'rd': rd, 'rating': 0, 'sold': False, 'rev': 0, 'reused': False, 'secs': 0})
                print(f"  {dom['name']} R{rd+1}: ❌ no valid design", flush=True)
                continue
            text, usage, cad, secs = best
            scores = mb.multi_judge(judges, demand, text, cad, root, rd)
            ratings = [s['rating'] for s in scores if s['rating'] > 0]
            med = sorted(ratings)[len(ratings)//2] if ratings else 0
            sold = med >= mb.ACCEPT
            rev = round(mb.PRICE * mb.speed_price(secs)) if sold else 0
            total += rev
            reused = mb.check_real_reuse(text, set(capital.keys()))
            if sold or med >= 3:
                capital[f'r{rd+1}'] = {'status': 'EXECUTED_CAD', 'step_path': cad['step_path'],
                                       'description': f'Round {rd+1}', 'measurements': cad.get('metrics', {})}
            rounds.append({'rd': rd, 'rating': med, 'sold': sold, 'rev': rev, 'reused': reused, 'secs': secs})
            print(f"  {dom['name']} R{rd+1}: {'✅' if sold else '❌'} {med}/10 {'♻️' if reused else '🔧'} {secs:.0f}s ¥{rev}", flush=True)
        early = [r['secs'] for r in rounds[:2] if r['secs'] > 0]
        late = [r['secs'] for r in rounds[3:] if r['secs'] > 0]
        t_accel = round((sum(early)/max(len(early),1)) / (sum(late)/max(len(late),1)), 2) if late else None
        return {'designer': dn, 'domain': dom['name'], 'rounds': rounds, 'profit': round(total, 2),
                'sold': f"{sum(1 for r in rounds if r['sold'])}/5",
                'reuse': f"{sum(1 for r in rounds if r.get('reused'))}/4", 't_accel': t_accel}

    all_runs = []
    for dom, system in domains:
        for i in range(a.n):
            root = RESULTS / a.tag / dom['name'] / time.strftime('%Y%m%d_%H%M%S')
            print(f"\n🧪 {a.tag} | {dom['name']} | session {i+1}/{a.n}")
            r = run_custom(spec, judges, f"{a.tag}", dom, system, root)
            (root / 'result.json').write_text(json.dumps(r, ensure_ascii=False, indent=2))
            all_runs.append(r)
            print(f"  => profit ¥{r['profit']} | sold {r['sold']} | reuse {r['reuse']} | t_accel {r['t_accel']}")

    out = RESULTS / a.tag / f"{a.test}_all_runs.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(all_runs, ensure_ascii=False, indent=2))
    from collections import defaultdict
    by_dom = defaultdict(list)
    for r in all_runs:
        by_dom[r['domain']].append(r['profit'])
    for d, ps in by_dom.items():
        print(f"\n{d}: n={len(ps)} mean={sum(ps)/len(ps):.0f} runs={[round(p) for p in ps]}")


if __name__ == '__main__':
    main()
