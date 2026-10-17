#!/usr/bin/env python3
"""3-judge symmetric recompute for the CARE-v4 vs CARE-v3 weights-only head-to-head.

Same protocol as rejudge_v2.py: the recorded in-run mimo-v2.6-pro rating stays as
judge 1; glm-5.3 and glm-5.3-flash re-rate the identical final designs; sale =
median-of-3 >= ACCEPT. Applied symmetrically to both arms — noise reduction only,
no GPU needed (design texts are archived in each session's r{rd}_a*/cad/_job_in.json).

Arms (leaderboard/data/care_v4_headtohead_v7gate.json):
  care-v4b-it8 + care-v4b-it8b   (10 sessions)
  care-v3-it6  + care-v3-it6b   (10 sessions)
"""
import json, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0,(str(HERE)))
from money_bench_v5 import DEMANDS, speed_price, PRICE, ACCEPT
from openrsi_sft_v2 import anthropic_call, GLM_BASE, zai_key, extract_json

JUDGE_SYS = ('Rate the workstation design 0-10 for user satisfaction. Return ONLY '
             'JSON: {"rating":<n>,"accepted":<bool>,"feedback":"<t>"}')
EVAL = HERE.parent / 'runs' / 'local_model_eval'
OUT = HERE.parent / 'leaderboard' / 'data' / 'care_v4_headtohead_3judge.json'
ARM_TAGS = {'care-v4': ['care-v4b-it8', 'care-v4b-it8b'],
            'care-v3': ['care-v3-it6', 'care-v3-it6b']}


def glm_rating(key, model, demand, text, max_tokens=4096):
    for _ in range(2):
        try:
            jt, _ = anthropic_call(GLM_BASE, key, model, JUDGE_SYS,
                                   f"Demand: {demand}\nDesign: {text[:6000]}",
                                   max_tokens, 0.2)
            r = (extract_json(jt) or {}).get('rating', 0)
            if r:
                return int(r)
        except Exception:
            time.sleep(3)
    return 0


def final_design(sess_dir, rd):
    """First attempt whose CAD executed = the design the eval kept."""
    for att in sorted(sess_dir.glob(f'r{rd}_a*')):
        ji = att / 'cad' / '_job_in.json'
        jo = att / 'cad' / '_job_out.json'
        if not (ji.exists() and jo.exists()):
            continue
        try:
            if json.loads(jo.read_text()).get('metrics'):
                return json.loads(ji.read_text()).get('text', '')
        except Exception:
            continue
    return None


def main():
    from concurrent.futures import ThreadPoolExecutor
    key = zai_key()

    # collect final designs per (arm, tag, session, round) — ONLY the sessions
    # that are in the published head-to-head archive (care-v4b-it8 has 5 stale
    # dirs from a batch whose all_runs.json was overwritten; exclude them by
    # exact run-signature matching against the archive)
    archive = json.loads((HERE.parent / 'leaderboard' / 'data' /
                          'care_v4_headtohead_v7gate.json').read_text())
    archive_arms = {'care-v4': 'care_v4b_it8', 'care-v3': 'care_v3_it6'}

    def sig(run):
        return (run['profit'], tuple((r['rd'], r['rating'], r['rev'], r['sold'])
                                     for r in run['rounds']))

    entries, tasks = [], []
    for arm, tags in ARM_TAGS.items():
        dirs = [d for t in tags for d in sorted(EVAL.glob(f'{t}_2*'))]
        for run in archive[archive_arms[arm]]:
            hits = [d for d in dirs
                    if (d / 'result.json').exists()
                    and sig(json.loads((d / 'result.json').read_text())) == sig(run)]
            if len(hits) != 1:
                print(f"[gather] WARN {arm} run ¥{run['profit']}: {len(hits)} dir matches", flush=True)
                continue
            sess_dir = hits[0]
            for rr in run['rounds']:
                rd = rr['rd']
                txt = final_design(sess_dir, rd)
                if not txt:
                    continue
                e = {'arm': arm, 'tag': sess_dir.name.rsplit('_', 1)[0], 'sess': sess_dir.name,
                     'rd': rd, 'mimo': rr['rating'], 'secs': rr.get('secs', 30)}
                entries.append(e)
                for model in ('glm-5.3', 'glm-5.3-flash'):
                    tasks.append((e['sess'], rd, model, DEMANDS[rd], txt))
    print(f"[gather] {len(entries)} round designs, {len(tasks)} judge calls", flush=True)

    cache = EVAL / 'rejudge_headtohead_cache.json'
    cached = json.loads(cache.read_text()) if cache.exists() else {}
    done = {tuple(json.loads(k)): v for k, v in cached.items()}
    tasks = [t for t in tasks if (t[0], t[1], t[2]) not in done]
    print(f"[gather] cache hit {len(cached)}, {len(tasks)} calls remain", flush=True)

    def work(t):
        sess, rd, model, demand, txt = t
        return (sess, rd, model), glm_rating(key, model, demand, txt)

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=8) as ex:
        for k, r in ex.map(work, tasks):
            done[k] = r
    cache.write_text(json.dumps({json.dumps(list(k)): v for k, v in done.items()}))
    print(f"[gather] done in {time.time()-t0:.0f}s", flush=True)

    for e in entries:
        g1 = done.get((e['sess'], e['rd'], 'glm-5.3'), 0)
        g2 = done.get((e['sess'], e['rd'], 'glm-5.3-flash'), 0)
        e['glm53'], e['glm53f'] = g1, g2
        e['med3'] = sorted([e['mimo'], g1, g2])[1]
        e['sold3'] = e['med3'] >= ACCEPT
        e['rev3'] = round(PRICE * speed_price(e['secs'])) if e['sold3'] else 0

    out = {'protocol': '3-judge symmetric recompute (recorded mimo + glm-5.3 + '
                       'glm-5.3-flash, median-of-3 >= 5) over archived head-to-head '
                       'designs; identical treatment for both arms',
           'arms': {}}
    for arm in ARM_TAGS:
        sess_profits, sess_profits3 = {}, {}
        for e in entries:
            if e['arm'] != arm:
                continue
            sess_profits.setdefault(e['sess'], 0)
            sess_profits3.setdefault(e['sess'], 0)
            sess_profits[e['sess']] += round(PRICE * speed_price(e['secs'])) if e['mimo'] >= ACCEPT else 0
            sess_profits3[e['sess']] += e['rev3']
        p1 = list(sess_profits.values())
        p3 = list(sess_profits3.values())
        out['arms'][arm] = {'n': len(p3), 'single_judge_profits': p1, 'three_judge_profits': p3,
                            'single_mean': round(sum(p1) / len(p1)), 'three_mean': round(sum(p3) / len(p3)),
                            'three_median': sorted(p3)[len(p3) // 2],
                            'sold_single': sum(1 for e in entries if e['arm'] == arm and e['mimo'] >= ACCEPT),
                            'sold_three': sum(1 for e in entries if e['arm'] == arm and e['sold3']),
                            'n_rounds': sum(1 for e in entries if e['arm'] == arm)}
        print(f"== {arm}: n={len(p3)} single ¥{out['arms'][arm]['single_mean']} "
              f"3-judge ¥{out['arms'][arm]['three_mean']} (median ¥{out['arms'][arm]['three_median']}) "
              f"rounds sold {out['arms'][arm]['sold_single']}→{out['arms'][arm]['sold_three']}/{out['arms'][arm]['n_rounds']}",
              flush=True)

    try:
        from scipy.stats import mannwhitneyu
        a = out['arms']['care-v4']['three_judge_profits']
        b = out['arms']['care-v3']['three_judge_profits']
        u, p = mannwhitneyu(a, b, alternative='greater')
        import statistics as st
        d = (st.mean(a) - st.mean(b)) / ((st.stdev(a) ** 2 + st.stdev(b) ** 2) / 2) ** 0.5
        out['test'] = {'vs': 'care-v4 > care-v3', 'mannwhitney_u': u, 'p_one_sided': round(p, 4),
                       'cohens_d': round(d, 2)}
        print(f"== care-v4 > care-v3: U={u:.0f} p(one-sided)={p:.4f} d={d:.2f}", flush=True)
    except Exception as ex:
        print('stats failed:', ex, flush=True)

    out['entries'] = entries
    OUT.write_text(json.dumps(out, indent=2))
    print('saved', OUT, flush=True)


if __name__ == '__main__':
    main()
