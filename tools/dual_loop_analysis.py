#!/usr/bin/env python3
"""Dual-loop PRSI x RSI factorial analysis."""
import json, statistics
from pathlib import Path

DUAL = Path(__file__).resolve().parent.parent / 'runs' / 'dual_loop'


def load(arm):
    try:
        return json.loads((DUAL / arm / 'log.json').read_text())
    except FileNotFoundError:
        return None


def main():
    print('=' * 66)
    print('  DUAL-LOOP PRSI x RSI — FACTORIAL RESULT')
    print('=' * 66)
    finals = {}
    for arm, desc in (('full', 'RSI loop + capital ACCUMULATES'),
                      ('rsi', 'RSI loop + capital RESET each gen'),
                      ('capital', 'model FROZEN + capital ACCUMULATES')):
        log = load(arm)
        if not log:
            print(f'\n[{arm}] no data'); continue
        finals[arm] = log
        print(f'\n[{arm}] {desc}')
        for x in log:
            acc = x.get('accepted')
            acc_s = {'True': '', 'False': '✗rej', 'None': '(frozen)'}[str(acc)]
            print(f"  g{x['gen']}: prod ¥{x['prod_profit']:>4} ({x['prod_sold']}/{x['prod_n']} sold, "
                  f"{x['prod_reuse']} reuse) | probe ¥{x['probe_mean']:>5.0f} | lib {x['library_size']}{acc_s}")
    if len(finals) == 3:
        b = finals['capital'][0]['probe_mean']            # gen1 approximates the shared baseline
        fA = statistics.mean([x['probe_mean'] for x in finals['full']])
        fB = statistics.mean([x['probe_mean'] for x in finals['rsi']])
        fC = statistics.mean([x['probe_mean'] for x in finals['capital']])
        print(f'\nmean probe-with-capital: full(A) ¥{fA:.0f} | rsi-only(B) ¥{fB:.0f} | capital-only(C) ¥{fC:.0f}')
        print(f'production profit trend: full {[x["prod_profit"] for x in finals["full"]]} | '
              f'rsi {[x["prod_profit"] for x in finals["rsi"]]} | capital {[x["prod_profit"] for x in finals["capital"]]}')
        print(f'interaction estimate A-B-C+base = {fA - fB - fC + b:+.0f} (positive => loops reinforce)')


if __name__ == '__main__':
    main()
