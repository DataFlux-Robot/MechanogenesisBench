#!/usr/bin/env python3
"""Run money_bench_v5 against a LOCAL vLLM OpenAI server (e.g. Qwen-27B AWQ or
fine-tuned 9B), with results stored on local disk instead of the full SSD.

Usage:
  python tools/run_local_bench.py --endpoint http://127.0.0.1:8100/v1 \
      --served-model qwen3.5-27b-awq --designer qwen27b-awq [--judges mimo-v2.6-pro] [--n 3]
"""
import argparse, json, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import money_bench_v5 as mb

RESULTS_LOCAL = HERE.parent / 'runs' / 'local_bench'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--endpoint', required=True)
    ap.add_argument('--served-model', required=True)
    ap.add_argument('--designer', required=True)
    ap.add_argument('--judges', nargs='+', default=['mimo-v2.6-pro'])
    ap.add_argument('--n', type=int, default=1)
    ap.add_argument('--max-tokens', type=int, default=8000)
    ap.add_argument('--temp', type=float, default=0.3)
    a = ap.parse_args()

    mb.RESULTS = RESULTS_LOCAL
    mb.MODELS[a.designer] = {'model': f'openai/{a.served_model}', 'api_base': a.endpoint,
                             'protocol': 'openai', 'key_env': None,
                             'max_tokens': a.max_tokens, 'temp': a.temp}
    # Qwen thinking models served by vLLM need the template kwarg to emit raw JSON;
    # injected via litellm extra_body (remote OpenAI-compatible endpoints ignore it).
    import litellm, re
    _orig_completion = litellm.completion
    def _completion_with_nothink(*args, **kw):
        eb = kw.setdefault('extra_body', {})
        eb.setdefault('chat_template_kwargs', {})['enable_thinking'] = False
        r = _orig_completion(*args, **kw)
        # some distill templates emit a literal <think></think> block inside content
        try:
            c = r.choices[0].message.content
            if c and '<think>' in c:
                r.choices[0].message.content = re.sub(r'<think>.*?</think>', '', c, flags=re.S).strip()
        except Exception:
            pass
        return r
    litellm.completion = _completion_with_nothink
    judges = {j: mb.MODELS[j] for j in a.judges if j in mb.MODELS}
    for k, v in judges.items():
        if v.get('key_env') and not __import__('os').environ.get(v['key_env']):
            print(f"FATAL: {v['key_env']} not set for judge {k}"); sys.exit(1)

    all_runs = []
    for i in range(a.n):
        root = RESULTS_LOCAL / a.designer / time.strftime('%Y%m%d_%H%M%S')
        print(f"\n💰 LOCAL bench: {a.designer} ({a.served_model} @ {a.endpoint}) session {i+1}/{a.n}\n")
        r = mb.run(mb.MODELS[a.designer], judges, a.designer, root)
        (root / 'result.json').write_text(json.dumps(r, indent=2, ensure_ascii=False) + '\n')
        mb.display(r)
        all_runs.append(r)
    out = RESULTS_LOCAL / f'{a.designer}_all_runs.json'
    out.write_text(json.dumps(all_runs, ensure_ascii=False, indent=2))
    profits = [r['profit'] for r in all_runs]
    print(f"\n{a.designer}: n={len(all_runs)} profit mean={sum(profits)/len(profits):.1f} "
          f"runs={[round(p,1) for p in profits]} -> {out}")


if __name__ == '__main__':
    main()
