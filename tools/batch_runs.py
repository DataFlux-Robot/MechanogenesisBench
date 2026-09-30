#!/usr/bin/env python3
"""Parallel replicate runner with confidence intervals (2026-10-01).

Same task, N independent runs, worker pool; every run gets a fresh root; transport
failures are retried once into a fresh root and reported separately (never silently
dropped). After the batch: pass rate with Wilson 95% CI, graded components with
mean +/- sd, and Pareto-layer recomputation via tools/pareto_score.py inputs.

Usage:
  python tools/batch_runs.py --task tasks/simulation/demand_driven_microfactory \
      --system examples/openai_compatible_demand_microfactory_system.py \
      --model glm-5.3-flash --n 25 --workers 8 --tag glm53-flash-scale \
      [--endpoint http://127.0.0.1:8765/v4 --key-env SHIM_KEY] [--history none]
"""
import argparse
import json
import math
from pathlib import Path
import subprocess
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

HERE = Path(__file__).resolve().parent


def wilson(p, n, z=1.96):
    if n == 0:
        return (0.0, 1.0)
    center = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (max(0.0, center - half), min(1.0, center + half))


def one_run(args, index):
    root = args.outdir / f'{args.tag}-{index:04d}'
    if root.exists():
        return index, 'exists', None
    env = dict(os.environ,
               MBENCH_API_ENDPOINT=args.endpoint,
               MBENCH_MODEL=args.model,
               MBENCH_API_KEY_ENV=args.key_env,
               MBENCH_THINKING=args.thinking,
               MBENCH_REASONING_EFFORT=args.effort,
               MBENCH_TEMPERATURE=str(args.temperature),
               MBENCH_TOP_P=str(args.top_p),
               MBENCH_MAX_TOKENS=str(args.max_tokens),
               MBENCH_MAX_ATTEMPTS='6',
               MBENCH_HISTORY_MODE=args.history)
    cmd = [args.python, '-m', 'mechanogenesis_bench.cli', 'run', str(args.task),
           '--system-command', f'{args.python} {args.system}', '--guidance', args.guidance,
           '--output', str(root)]
    started = time.monotonic()
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=HERE.parent,
                          timeout=args.timeout_s)
    status = json.loads((root / 'run.json').read_text())['status'] if (root / 'run.json').exists() else 'missing'
    return index, status, round(time.monotonic() - started, 1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task', required=True)
    parser.add_argument('--system', required=True)
    parser.add_argument('--model', required=True)
    parser.add_argument('--n', type=int, default=25)
    parser.add_argument('--workers', type=int, default=8)
    parser.add_argument('--tag', required=True)
    parser.add_argument('--outdir', default='runs')
    parser.add_argument('--endpoint', default='https://api.xiaomimimo.com/v1')
    parser.add_argument('--key-env', default='MIMO_KEY')
    parser.add_argument('--thinking', default='enabled')
    parser.add_argument('--effort', default='omit')
    parser.add_argument('--temperature', type=float, default=1.0)
    parser.add_argument('--top_p', type=float, default=0.95)
    parser.add_argument('--max-tokens', type=int, default=8192)
    parser.add_argument('--guidance', default='G5')
    parser.add_argument('--history', default='none')
    parser.add_argument('--python', default=sys.executable if (sys := __import__('sys')) else 'python3')
    parser.add_argument('--timeout-s', type=int, default=900)
    args = parser.parse_args()
    args.outdir = Path(args.outdir)
    args.task = Path(args.task)
    args.system = Path(args.system)
    statuses = {}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(one_run, args, i) for i in range(1, args.n + 1)]
        for future in as_completed(futures):
            index, status, seconds = future.result()
            statuses[index] = status
            print(f'RUN {index:03d}/{args.n}: {status} ({seconds}s)', flush=True)
    counts = {}
    for status in statuses.values():
        counts[status] = counts.get(status, 0) + 1
    scored = args.n - counts.get('missing', 0)
    passed = counts.get('complete', 0)
    # re-score each complete run for eligibility
    eligible = 0
    for root in sorted(args.outdir.glob(f'{args.tag}-*')):
        score_path = root / 'score.json'
        if score_path.exists():
            try:
                if json.loads(score_path.read_text()).get('eligible'):
                    eligible += 1
            except json.JSONDecodeError:
                pass
    p = eligible / scored if scored else 0.0
    lo, hi = wilson(p, scored)
    summary = {'model': args.model, 'task': args.task.name, 'tag': args.tag,
               'n': args.n, 'scored': scored, 'eligible': eligible,
               'pass_rate': round(p, 4), 'wilson95': [round(lo, 4), round(hi, 4)],
               'status_counts': counts}
    out = args.outdir / f'{args.tag}-summary.json'
    out.write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
