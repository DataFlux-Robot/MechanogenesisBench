#!/usr/bin/env python3
"""Acceleration Bench v1.0 — measures THE metric: Generational Acceleration.

Core question (paper title): "Machines That Accelerate Machine-Making"
→ Does each generation of machine-making cost less than the last?

Formula: Acceleration = 1 − ℓ_g2/ℓ_g1
  Positive = accelerating (each generation cheaper → machines accelerating machine-making)
  Zero     = flat
  Negative = decelerating

ℓ = frozen net production loss (paper Eq.4):
  quality_loss + cost_loss + failure_penalty
  = (excess_mm/100 + overlap_mm³/1000)
  + (designer_seconds/600 + output_tokens/10000)
  + 2.0 × candidate_failures

Uses LiteLLM for all model routing — zero custom LLM infrastructure.
Works with remote APIs (GLM/MiMo/OpenAI/Claude/...) and local models
(Ollama/vLLM/...) interchangeably.

Usage:
  python tools/accel_bench.py --models glm-5.3-flash mimo-v2.6-pro ...
  python tools/accel_bench.py --models local-qwen  # via Ollama/vLLM
"""
import argparse
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
RESULTS = Path('/media/exuber/Elements/DataFlux/MechanogenesisBenchDEV/accel_bench_runs')


# ── Model registry: LiteLLM model string + endpoint + key env ──
MODELS = {
    'glm-5.3-flash': {
        'model': 'openai/glm-5.3-flash',
        'api_base': 'https://api.z.ai/api/paas/v4',
        'key_env': 'ZAI_KEY',
        'max_tokens': 16000,
        'temperature': 0.3,
    },
    'glm-5.3': {
        'model': 'openai/glm-5.3',
        'api_base': 'https://api.z.ai/api/paas/v4',
        'key_env': 'ZAI_KEY',
        'max_tokens': 32000,
        'temperature': 0.6,
    },
    'glm-5.2': {
        'model': 'openai/glm-5.2',
        'api_base': 'https://api.z.ai/api/paas/v4',
        'key_env': 'ZAI_KEY',
        'max_tokens': 32000,
        'temperature': 0.6,
    },
    'glm-5.1': {
        'model': 'openai/glm-5.1',
        'api_base': 'https://api.z.ai/api/paas/v4',
        'key_env': 'ZAI_KEY',
        'max_tokens': 32000,
        'temperature': 0.6,
    },
    'mimo-v2.6-pro': {
        'model': 'openai/mimo-v2.6-pro',
        'api_base': 'https://api.xiaomimimo.com/v1',
        'key_env': 'MIMO_KEY',
        'max_tokens': 32000,
        'temperature': 0.6,
    },
    'mimo-v2.6-flash': {
        'model': 'openai/mimo-v2.6-flash',
        'api_base': 'https://api.xiaomimimo.com/v1',
        'key_env': 'MIMO_KEY',
        'max_tokens': 32000,
        'temperature': 0.6,
    },
    # ── Local models (Ollama) ──
    'local-qwen3.5-9b': {
        'model': 'ollama/qwen3.5:9b',
        'api_base': 'http://127.0.0.1:11434',
        'key_env': None,
        'max_tokens': 16000,
        'temperature': 0.3,
    },
    'local-qwen3.8-27b': {
        'model': 'ollama/qwen3.8:27b-q4_K_M',
        'api_base': 'http://127.0.0.1:11437',
        'key_env': None,
        'max_tokens': 16000,
        'temperature': 0.3,
    },
}


# ── Task definition (same as workstation surface, self-contained) ──
SYSTEM_PROMPT = '''You are a workstation product designer. Design a reconfigurable desk-top
workstation by constructing a bounded CSG graph.

INTERFACE SPEC: the ONLY legal node ops are exactly:
  {"id":"n1","op":"box","size":[x,y,z]}
  {"id":"n2","op":"cylinder","radius":r,"height":h}
  {"id":"n3","op":"union","inputs":["n1","n2"]}
  {"id":"n4","op":"difference","inputs":["n1","n2"]}
  {"id":"n5","op":"transform","input":"n1","xyz":[x,y,z],"rpy":[rx,ry,rz]}
  {"id":"n6","op":"capital","asset_id":"<id from capital list>"}
Any other op is INVALID. Node ids must match [A-Za-z][A-Za-z0-9_]{0,63} and reference
only EARLIER nodes. A part is exactly {"name","node","role","xyz","rpy"} with role in
{frame,module,tooling}. At most 128 nodes, 32 parts.

MINIMAL VALID EXAMPLE:
{"schema":"workstation-csg/1","hypothesis":"base with riser",
 "nodes":[{"id":"b","op":"box","size":[200,150,10]},
          {"id":"r","op":"box","size":[60,40,40]},
          {"id":"rt","op":"transform","input":"r","xyz":[0,-50,10],"rpy":[0,0,0]}],
 "parts":[{"name":"base","node":"b","role":"frame","xyz":[0,0,0],"rpy":[0,0,0]},
          {"name":"riser","node":"rt","role":"module","xyz":[0,0,0],"rpy":[0,0,0]}]}

Return ONLY the JSON object. No code, no explanation.'''

TASKS = [
    {'id': 'phone_tools',
     'brief': 'Compact reconfigurable desktop workstation for a phone (78×12×160mm), '
              'earbud case (65×48×28mm) and hand tools. Desk 420×280mm. '
              'Keep front accessible, allow charging cables, reusable modules.',
     'desk': [420, 280]},
    {'id': 'tablet_left_hand',
     'brief': 'Add a landscape tablet (250×10×175mm), keep phone usable, move storage '
              'to left/front. Reuse earlier capital if helpful. Desk 420×280mm. '
              'Do not merely enlarge everything.',
     'desk': [420, 280]},
]


def call_model(spec, system, user, label, folder):
    """Call a model via LiteLLM. Returns (text, usage, seconds) or raises."""
    from litellm import completion
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)

    key = os.environ.get(spec['key_env'], 'none') if spec['key_env'] else 'none'
    started = time.monotonic()
    try:
        r = completion(
            model=spec['model'],
            api_base=spec['api_base'],
            api_key=key,
            messages=[{'role': 'system', 'content': system},
                      {'role': 'user', 'content': user}],
            max_tokens=spec['max_tokens'],
            temperature=spec['temperature'],
            timeout=300)
        text = r.choices[0].message.content or ''
        usage = {'input': r.usage.prompt_tokens or 0,
                 'output': r.usage.completion_tokens or 0}
        seconds = round(time.monotonic() - started, 1)
        # strip markdown fence if present
        clean = text.strip()
        if clean.startswith('```') and clean.endswith('```') and clean.count('```') == 2:
            lines = clean.split('\n')
            if len(lines) >= 3:
                clean = '\n'.join(lines[1:-1]).strip()
        (folder / f'{label}.json').write_text(json.dumps({
            'text': clean, 'raw_text': text, 'usage': usage,
            'seconds': seconds, 'model': spec['model']}, ensure_ascii=False, indent=2))
        return clean, usage, seconds
    except Exception as e:
        (folder / f'{label}_error.json').write_text(json.dumps({
            'error': str(e)[:500], 'model': spec['model']}, indent=2))
        raise


def evaluate_design(design_json, task):
    """Simple deterministic evaluation: parse + measure against desk limits."""
    try:
        d = json.loads(design_json)
        nodes = d.get('nodes', [])
        parts = d.get('parts', [])
        if not nodes or not parts:
            return {'valid': False, 'error': 'empty design', 'excess_mm': 999,
                    'overlap_mm3': 999, 'quality': 99.9}
        # estimate footprint from part positions + node sizes
        xs, ys = [], []
        for p in parts:
            xyz = p.get('xyz', [0, 0, 0])
            node = next((n for n in nodes if n.get('id') == p.get('node')), {})
            size = node.get('size', [100, 100, 50])
            xs += [xyz[0] - size[0] / 2, xyz[0] + size[0] / 2]
            ys += [xyz[1] - size[1] / 2, xyz[1] + size[1] / 2]
        if not xs:
            return {'valid': False, 'error': 'no placeable parts', 'excess_mm': 999,
                    'overlap_mm3': 999, 'quality': 99.9}
        extent_x = max(xs) - min(xs)
        extent_y = max(ys) - min(ys)
        excess_x = max(0, extent_x - task['desk'][0])
        excess_y = max(0, extent_y - task['desk'][1])
        excess = excess_x + excess_y
        # crude overlap: count pairs of parts with overlapping bounding boxes
        overlap_count = 0
        for i, p1 in enumerate(parts):
            for p2 in parts[i + 1:]:
                x1, y1 = p1.get('xyz', [0, 0, 0])[:2]
                x2, y2 = p2.get('xyz', [0, 0, 0])[:2]
                if abs(x1 - x2) < 50 and abs(y1 - y2) < 50:
                    overlap_count += 1
        overlap_mm3 = overlap_count * 50000  # rough estimate
        quality = excess / 100 + overlap_mm3 / 1000
        return {'valid': True, 'excess_mm': excess, 'overlap_mm3': overlap_mm3,
                'quality': quality, 'extent': [round(extent_x), round(extent_y)]}
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        return {'valid': False, 'error': str(e), 'excess_mm': 999,
                'overlap_mm3': 999, 'quality': 99.9}


def compute_loss(evaluations, usage_total, seconds_total, failures):
    """Frozen loss formula (paper Eq.4)."""
    best_quality = min((e['quality'] for e in evaluations if e.get('valid')), default=99.9)
    cost = seconds_total / 600 + usage_total.get('output', 0) / 10000 + 2.0 * failures
    return round(best_quality + cost, 4)


def run_generations(spec, model_name, root, n_candidates=3):
    """Run G0→G1→G2, return per-generation losses for acceleration computation."""
    from litellm import completion  # ensure import
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    capital_list = []
    gen_losses = []
    gen_details = []

    for gen in range(3):
        task = TASKS[min(gen, len(TASKS) - 1)]
        user = json.dumps({
            'task': task, 'operator': 'Draft' if gen == 0 else 'Improve',
            'capital': [{'id': c['id'], 'description': c['desc']} for c in capital_list],
        }, ensure_ascii=False)

        evaluations, failures = [], 0
        usage_total = {'input': 0, 'output': 0}
        seconds_total = 0.0

        for cand in range(n_candidates):
            label = f'g{gen}_c{cand}'
            try:
                text, usage, seconds = call_model(spec, SYSTEM_PROMPT, user,
                                                  label, root / label)
                usage_total['input'] += usage['input']
                usage_total['output'] += usage['output']
                seconds_total += seconds
                ev = evaluate_design(text, task)
                evaluations.append(ev)
                if ev['valid']:
                    capital_list.append({
                        'id': f'g{gen}_c{cand}',
                        'desc': f'Gen {gen} candidate {cand}: extent {ev.get("extent")}'})
            except Exception:
                failures += 1

        loss = compute_loss(evaluations, usage_total, seconds_total, failures)
        gen_losses.append(loss)
        gen_details.append({
            'generation': gen, 'loss': loss, 'failures': failures,
            'valid': sum(1 for e in evaluations if e.get('valid')),
            'candidates': n_candidates,
            'seconds': round(seconds_total, 1),
            'tokens_out': usage_total['output'],
        })
        print(f'  G{gen}: loss={loss} valid={gen_details[-1]["valid"]}/{n_candidates} '
              f'failures={failures} {round(seconds_total)}s', flush=True)

    # acceleration
    if len(gen_losses) >= 2 and gen_losses[0] > 0:
        accel_g12 = round(1 - gen_losses[1] / gen_losses[0], 3)
    else:
        accel_g12 = None
    if len(gen_losses) >= 3 and gen_losses[1] > 0:
        accel_g23 = round(1 - gen_losses[2] / gen_losses[1], 3)
    else:
        accel_g23 = None

    return {
        'model': model_name,
        'gen_losses': gen_losses,
        'accel_g1_to_g2': accel_g12,
        'accel_g2_to_g3': accel_g23,
        'accel_overall': round(1 - gen_losses[-1] / gen_losses[0], 3) if gen_losses[0] else None,
        'details': gen_details,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--models', nargs='+', required=True,
                        choices=list(MODELS.keys()) + ['all'],
                        help='Models to test (or "all")')
    parser.add_argument('--candidates', type=int, default=3,
                        help='Candidates per generation')
    parser.add_argument('--output', default=str(RESULTS / 'accel_results.json'))
    args = parser.parse_args()

    if 'all' in args.models:
        args.models = [m for m in MODELS if MODELS[m].get('key_env') is None
                       or os.environ.get(MODELS[m]['key_env'])]
        print(f' runnable models (keys available): {args.models}')

    all_results = []
    for model_name in args.models:
        spec = MODELS[model_name]
        if spec.get('key_env') and not os.environ.get(spec['key_env']):
            print(f'SKIP {model_name}: {spec["key_env"]} not set')
            continue
        print(f'\n=== {model_name} ===', flush=True)
        root = RESULTS / model_name / time.strftime('%Y%m%d_%H%M%S')
        try:
            result = run_generations(spec, model_name, root, args.candidates)
            all_results.append(result)
            a = result['accel_g1_to_g2']
            print(f'  → Acceleration G1→G2: {a:+.1%}' if a is not None else '  → incomplete')
        except Exception as e:
            print(f'  FAILED: {str(e)[:200]}')
            all_results.append({'model': model_name, 'error': str(e)[:300]})

    # sort by acceleration
    valid = [r for r in all_results if r.get('accel_g1_to_g2') is not None]
    valid.sort(key=lambda r: -(r['accel_g1_to_g2']))

    print(f'\n{"=" * 70}')
    print(f'{"Rank":>4} | {"Model":20s} | {"ℓ_g1":>8s} | {"ℓ_g2":>8s} | {"Accel G1→G2":>12s}')
    print(f'{"-" * 70}')
    for i, r in enumerate(valid, 1):
        print(f'{i:4d} | {r["model"]:20s} | {r["gen_losses"][0]:8.2f} | {r["gen_losses"][1]:8.2f}'
              f' | {r["accel_g1_to_g2"]:+.1%}')
    for r in all_results:
        if r.get('accel_g1_to_g2') is None:
            print(f'  —  | {r["model"]:20s} | {"incomplete":>8s}')

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    # merge with existing if any
    existing = json.loads(out.read_text()) if out.exists() else []
    existing_by_model = {r['model']: r for r in existing}
    for r in all_results:
        existing_by_model[r['model']] = r
    out.write_text(json.dumps(list(existing_by_model.values()), indent=2) + '\n')
    print(f'\nResults: {out}')


if __name__ == '__main__':
    main()
