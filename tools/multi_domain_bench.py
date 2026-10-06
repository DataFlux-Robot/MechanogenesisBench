#!/usr/bin/env python3
"""Multi-domain PRSI Bench: desk workstation + fixture design + production layout.

Three independent task domains, each with 5 rounds of cumulative demands.
Same evaluation infrastructure (build123d real CAD + LLM judges + speed pricing).
Domain-specific CSG ops and evaluation metrics.

This addresses the #1 NMI reviewer concern: "does this generalize beyond one task?"
"""
import argparse, json, os, sys, time
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from money_bench_v5 import (
    MODELS, anthropic_call, call, real_cad_eval, check_real_reuse,
    multi_judge, speed_price, PRICE, ACCEPT, TOKEN_PRICE
)

RESULTS = Path('/home/exuber/CODE/CORE/pythonProject1/AUTORESEARCH/MechanogenesisBench-upstream/runs/multi_domain')

# ── Domain 1: Desk Workstation (existing) ──
DOMAIN_WORKSTATION = {
    'name': 'workstation',
    'demands': [
        "Build a phone dock for 78x12x160mm phone. Desk 420x280mm. From scratch.",
        "Customer upgraded to 90x14x175mm phone. Adapt the dock. MUST reuse the base from round 1.",
        "Add earbuds bay (65x48x28mm). MUST keep the adapted dock and add to it.",
        "Add tablet stand (250x10x175mm) behind. Combine all modules. MUST reuse dock+earbuds.",
        "Desk shrank to 300x200mm! Shrink but keep ALL functions. MUST optimize accumulated design.",
    ],
    'desk': (420, 280),
}

# ── Domain 2: Fixture Design ──
DOMAIN_FIXTURE = {
    'name': 'fixture',
    'demands': [
        "Design a fixture to hold a 100x50x20mm aluminum block for face milling. Machine table 500x300mm. From scratch.",
        "New part: 150x60x25mm steel block. Adapt the fixture. MUST reuse the base plate from round 1.",
        "Add a second slot for the original 100x50x20mm block (dual-holding). MUST reuse adapted base.",
        "Parts changed to cylindrical Ø80x150mm. Need V-block support. MUST reuse base plate.",
        "Table reduced to 300x200mm. Hold both cylinder AND small plate. Optimize accumulated fixture.",
    ],
    'desk': (500, 300),
}

# ── Domain 3: Production Line Layout ──
DOMAIN_LAYOUT = {
    'name': 'layout',
    'demands': [
        "Layout a simple assembly line: conveyor (400x60mm) + robot cell (100x100mm) + inspection (80x60mm). Floor 1000x600mm. From scratch.",
        "Add packaging station (120x80mm) at the end. MUST reuse conveyor positioning from round 1.",
        "New product needs a welding cell (160x120mm) with safety zone. MUST integrate with existing line.",
        "Throughput doubled: add a second line sharing the inspection station. MUST reuse layout.",
        "Floor reduced to 600x400mm. Compress everything. Optimize the accumulated layout.",
    ],
    'desk': (1000, 600),
}

DOMAINS = {
    'workstation': DOMAIN_WORKSTATION,
    'fixture': DOMAIN_FIXTURE,
    'layout': DOMAIN_LAYOUT,
}

# ── Domain-adapted system prompts ──
SYSTEMS = {
    'workstation': '''Design a desk workstation. Return ONLY JSON with schema="workstation-csg/1".
Ops: box(size), cylinder(radius,height), union(inputs), difference(inputs), transform(input,xyz,rpy), capital(asset_id).
capital(asset_id) imports a PREVIOUSLY BUILT module — it's FREE and FASTER. USE IT if available.
Parts: {"name","node","role(frame|module|tooling)","xyz","rpy"}. Max 64 nodes, 16 parts. mm.
Example: {"schema":"workstation-csg/1","hypothesis":"phone dock","nodes":[{"id":"b","op":"box","size":[100,60,10]}],"parts":[{"name":"base","node":"b","role":"frame","xyz":[0,0,0],"rpy":[0,0,0]}]}''',

    'fixture': '''Design a machining fixture. Return ONLY JSON with schema="workstation-csg/1".
Ops: box(size), cylinder(radius,height), union(inputs), difference(inputs), transform(input,xyz,rpy), capital(asset_id).
capital(asset_id) imports a PREVIOUSLY BUILT fixture module — it's FREE. USE IT if available.
Fixture parts: base plate, locators, clamps, V-blocks. role must be frame/module/tooling.
Parts: {"name","node","role(frame|module|tooling)","xyz","rpy"}. Max 64 nodes, 16 parts. mm.
Example: {"schema":"workstation-csg/1","hypothesis":"mill fixture","nodes":[{"id":"base","op":"box","size":[300,200,15]},{"id":"loc","op":"cylinder","radius":5,"height":20}],"parts":[{"name":"base","node":"base","role":"frame","xyz":[0,0,0],"rpy":[0,0,0]},{"name":"locator","node":"loc","role":"tooling","xyz":[50,50,15],"rpy":[0,0,0]}]}''',

    'layout': '''Design a production line layout. Return ONLY JSON with schema="workstation-csg/1".
Ops: box(size), cylinder(radius,height), union(inputs), difference(inputs), transform(input,xyz,rpy), capital(asset_id).
capital(asset_id) imports a PREVIOUSLY PLACED module — it's FREE. USE IT if available.
Layout elements: conveyors, robot cells, inspection stations, safety zones. role: frame(floor)/module(equipment)/tooling(safety).
Parts: {"name","node","role(frame|module|tooling)","xyz","rpy"}. Max 64 nodes, 16 parts. mm.
Example: {"schema":"workstation-csg/1","hypothesis":"assembly line","nodes":[{"id":"conv","op":"box","size":[400,60,20]},{"id":"robot","op":"box","size":[100,100,150]}],"parts":[{"name":"conveyor","node":"conv","role":"module","xyz":[0,0,0],"rpy":[0,0,0]},{"name":"robot_cell","node":"robot","role":"module","xyz":[300,0,0],"rpy":[0,0,0]}]}''',
}


def run_domain(spec, judges, dn, domain_name, root):
    """Run 5 rounds in one domain with real CAD evaluation."""
    domain = DOMAINS[domain_name]
    system = SYSTEMS[domain_name]
    root = Path(root); root.mkdir(parents=True, exist_ok=True)

    capital = {}
    rounds = []
    total_rev, total_cost = 0.0, 0.0

    for rd in range(5):
        demand = domain['demands'][rd]
        best_text, best_usage, best_cad, best_secs = None, None, None, 0
        reused = False

        for att in range(2):
            label = f'r{rd}_a{att}'
            msg = json.dumps({
                'demand': demand,
                'capital': [{'id': k, 'desc': v.get('description', '')}
                           for k, v in capital.items()],
                'hint': 'Use capital(asset_id) to import previous modules.' if capital else None})
            try:
                text, usage, secs = call(spec, system, msg, root / label, label)
                if not text.strip(): continue
                cad = real_cad_eval(text, capital, root / label / 'cad', desk=domain['desk'])
                if cad.get('metrics'):
                    best_text, best_usage, best_cad, best_secs = text, usage, cad, secs
                    reused = check_real_reuse(text, set(capital.keys()))
                    break
            except: continue

        if best_cad is None:
            rounds.append({'rd': rd, 'rating': 0, 'sold': False, 'rev': 0,
                          'reused': False, 'secs': 0, 'cad': None})
            continue

        scores = multi_judge(judges, demand, best_text, best_cad, root, rd)
        ratings = [s['rating'] for s in scores if s['rating'] > 0]
        median_rating = sorted(ratings)[len(ratings)//2] if ratings else 0
        sold = median_rating >= ACCEPT
        sp = speed_price(best_secs)
        rev = round(PRICE * sp) if sold else 0
        tokens = best_usage['input'] + best_usage['output']
        cost = tokens * TOKEN_PRICE
        total_rev += rev; total_cost += cost

        if best_cad.get('step_path'):
            capital[f'r{rd+1}'] = {
                'status': 'EXECUTED_CAD', 'step_path': best_cad['step_path'],
                'description': f'Round {rd+1}', 'measurements': best_cad.get('metrics', {})}

        rounds.append({'rd': rd, 'rating': median_rating, 'sold': sold,
                      'rev': rev, 'reused': reused, 'secs': best_secs,
                      'cad': best_cad.get('facts_summary')})
        ic = '✅' if sold else '❌'; ru = '♻️' if reused else '🔧'
        print(f'  {domain_name} R{rd+1}: {ic} {median_rating}/10 {ru} {best_secs:.0f}s', flush=True)

    early = [r for r in rounds if r['rd'] < 2 and r['secs'] > 0]
    late = [r for r in rounds if r['rd'] >= 3 and r['secs'] > 0]
    et = sum(r['secs'] for r in early) / max(len(early), 1)
    lt = sum(r['secs'] for r in late) / max(len(late), 1)
    t_accel = round(et / lt, 2) if lt > 0 else None

    return {'designer': dn, 'domain': domain_name, 'rounds': rounds,
            'profit': round(total_rev - total_cost, 2),
            'revenue': total_rev, 'cost': round(total_cost, 2),
            'sold': f'{sum(1 for r in rounds if r["sold"])}/5',
            'reuse': f'{sum(1 for r in rounds if r.get("reused"))}/4',
            't_accel': t_accel,
            'avg_rating': round(sum(r['rating'] for r in rounds) / 5, 1)}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--designer', required=True, choices=list(MODELS))
    p.add_argument('--judge', default='mimo-v2.6-pro')
    p.add_argument('--domains', nargs='+', default=['workstation', 'fixture', 'layout'])
    a = p.parse_args()

    ds = MODELS[a.designer]
    judges = {a.judge: MODELS[a.judge]}
    for s, n in [(ds, a.designer)] + [(v, k) for k, v in judges.items()]:
        if s.get('key_env') and not os.environ.get(s['key_env']):
            print(f'FATAL: {s["key_env"]} not set'); sys.exit(1)

    tag = time.strftime('%Y%m%d_%H%M%S')
    all_results = []

    for domain_name in a.domains:
        print(f'\n{"=" * 50}')
        print(f'  Domain: {domain_name}')
        print(f'{"=" * 50}')
        root = RESULTS / a.designer / f'{domain_name}_{tag}'
        result = run_domain(ds, judges, a.designer, domain_name, root)
        all_results.append(result)

    # Cross-domain summary
    print(f'\n{"=" * 60}')
    print(f'  MULTI-DOMAIN RESULTS: {a.designer}')
    print(f'{"=" * 60}')
    print(f'  {"Domain":15s} | {"Profit":>8s} | {"Sold":>5s} | {"Reuse":>5s} | {"Accel":>6s} | {"Rating":>6s}')
    print(f'  {"-" * 60}')
    for r in all_results:
        accel = f'{r["t_accel"]}x' if r.get('t_accel') else '—'
        print(f'  {r["domain"]:15s} | ¥{r["profit"]:7.2f} | {r["sold"]:>5s} | {r["reuse"]:>5s} | {accel:>6s} | {r["avg_rating"]:5.1f}')

    total_profit = sum(r['profit'] for r in all_results)
    total_sold = sum(int(r['sold'].split('/')[0]) for r in all_results)
    total_possible = sum(int(r['sold'].split('/')[1]) for r in all_results)
    accels = [r['t_accel'] for r in all_results if r.get('t_accel')]
    med_accel = sorted(accels)[len(accels)//2] if accels else None
    print(f'  {"-" * 60}')
    print(f'  {"TOTAL":15s} | ¥{total_profit:7.2f} | {total_sold}/{total_possible} |       | {med_accel}x  |')

    out = RESULTS / a.designer / f'multi_domain_{tag}.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(all_results, indent=2, ensure_ascii=False) + '\n')
    print(f'\n  Results: {out}')


if __name__ == '__main__':
    main()
