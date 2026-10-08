#!/usr/bin/env python3
"""3-judge symmetric recompute for FluxEidosV2 sessions (surpass v6 + v7).

Stored per-round mimo ratings are kept as one judge component; glm-5.3 and
glm-5.3-flash rate the same final designs; sale = median-of-3 >= ACCEPT.

Final-design reconstruction per round:
- R1 (best-of-3): re-simulate parts-first selection from stored candidate metrics.
- R2-R5: v1 artifact; when a resample artifact (v2/v3) exists the runtime kept
  the higher-rated one. If the recorded rating >= 5 the resample won (resamples
  only fire from <5); if still <5 we keep the artifact with the higher glm
  median (symmetric re-simulation, disclosed approximation).
"""
import json, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from money_bench_v5 import DEMANDS, speed_price, PRICE, ACCEPT
from openrsi_sft_v2 import anthropic_call, GLM_BASE, zai_key, extract_json

JUDGE_SYS = ('Rate the workstation design 0-10 for user satisfaction. Return ONLY '
             'JSON: {"rating":<n>,"accepted":<bool>,"feedback":"<t>"}')
RUNS = HERE.parent / 'runs' / 'surpass'
POLICY = int(sys.argv[1]) if len(sys.argv) > 1 else 0
OUT = RUNS / f'v2_rejudge_3judge_p{POLICY}.json'


def glm_rating(key, model, demand, text, max_tokens):
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


def round_artifacts(sess_dir, rd, recorded_rating):
    """Return (text, ambiguous_flag) for the round's final design."""
    # R1: re-simulate best-of-3 parts-first selection
    if rd == 0:
        cands = []
        for c in sorted(sess_dir.glob('r0_c*')):
            ji, jo = c / '_ji.json', c / '_jo.json'
            if not (ji.exists() and jo.exists()):
                continue
            try:
                d = json.loads(json.loads(ji.read_text())['text'])
                m = json.loads(jo.read_text()).get('metrics')
                if not m:
                    continue
                cands.append(((-len(d.get('parts', [])), m.get('overlap_mm3', 1e9)),
                              json.loads(ji.read_text())['text']))
            except Exception:
                continue
        if cands:
            cands.sort(key=lambda c: c[0])
            return cands[0][1], False
        v1 = sess_dir / 'r0_v1' / '_ji.json'
        if v1.exists():
            return json.loads(v1.read_text())['text'], False
        return None, False
    # R2-R5: resample bookkeeping
    texts = {}
    for suf in ('v1', 'v2', 'v3'):
        p = sess_dir / f'r{rd}_{suf}' / '_ji.json'
        if p.exists():
            texts[suf] = json.loads(p.read_text())['text']
    if not texts:
        return None, False
    if len(texts) == 1:
        return texts['v1'], False
    if recorded_rating >= ACCEPT:          # resample fired from <5 -> last won
        return texts[max(texts)], False
    return None, True                      # ambiguous: caller judges all, keeps best glm


JUDGE_RESULTS = {}


def gather_tasks():
    tasks = []
    for tag in ('v6', 'v7'):
        runs = json.loads((RUNS / f'{tag}_results.json').read_text())
        for i in range(len(runs)):
            sess_dir = RUNS / tag / f'sess{i+1}'
            for rd in range(5):
                for art in sorted(sess_dir.glob(f'r{rd}_*')):
                    ji = art / '_ji.json'
                    if not ji.exists():
                        continue
                    try:
                        txt = json.loads(ji.read_text())['text']
                    except Exception:
                        continue
                    if not txt or len(txt) < 40:
                        continue
                    for model in ('glm-5.3', 'glm-5.3-flash'):
                        tasks.append((tag, i, rd, art.name, model, DEMANDS[rd], txt))
    return tasks


def main():
    from concurrent.futures import ThreadPoolExecutor
    key = zai_key()
    tasks = gather_tasks()
    print(f"[gather] {len(tasks)} judge calls", flush=True)

    def work(t):
        tag, i, rd, art, model, demand, txt = t
        return (tag, i, rd, art, model), glm_rating(key, model, demand, txt, 4096)

    cache = RUNS / 'rejudge_cache.json'
    if cache.exists():
        JUDGE_RESULTS.update({tuple(json.loads(k)): v for k, v in json.loads(cache.read_text()).items()})
        tasks = [t for t in tasks if (t[0], t[1], t[2], t[3], t[4]) not in JUDGE_RESULTS]
        print(f"[gather] cache hit, {len(tasks)} calls remain", flush=True)
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=8) as ex:
        for k, r in ex.map(work, tasks):
            JUDGE_RESULTS[k] = r
    print(f"[gather] done in {time.time()-t0:.0f}s", flush=True)
    cache.write_text(json.dumps({json.dumps(list(k)): v for k, v in JUDGE_RESULTS.items()}))

    out_runs = {}
    t0 = time.time()
    for tag in ('v6', 'v7'):
        runs = json.loads((RUNS / f'{tag}_results.json').read_text())
        sess3 = []
        for i, run in enumerate(runs):
            sess_dir = RUNS / tag / f'sess{i+1}'
            total = 0.0
            for rr in run['rounds']:
                rd, rec = rr['rd'], rr['rating']
                demand = DEMANDS[rd]
                txt, ambiguous = round_artifacts(sess_dir, rd, rec)
                if txt is None and not ambiguous:
                    continue
                if ambiguous:
                    cands = []
                    for suf in ('v1', 'v2', 'v3'):
                        pj = sess_dir / f'r{rd}_{suf}' / '_ji.json'
                        if not pj.exists():
                            continue
                        g1 = JUDGE_RESULTS[(tag, i, rd, f'r{rd}_{suf}', 'glm-5.3')]
                        g2 = JUDGE_RESULTS[(tag, i, rd, f'r{rd}_{suf}', 'glm-5.3-flash')]
                        cands.append((sorted([rec, g1, g2])[1], g1, g2))
                    best, worst = max(cands), min(cands)
                    # policy 0 optimistic (best-glm), 1 neutral (v1), 2 pessimistic (worst-glm)
                    pick = best if POLICY == 0 else (cands[0] if POLICY == 1 else worst)
                    g1, g2 = pick[1], pick[2]
                else:
                    keyname = None
                    for art in sorted(sess_dir.glob(f'r{rd}_*')):
                        cj = art / '_ji.json'
                        if cj.exists():
                            try:
                                if json.loads(cj.read_text())['text'] == txt:
                                    keyname = art.name
                                    break
                            except Exception:
                                continue
                    if keyname and (tag, i, rd, keyname, 'glm-5.3') in JUDGE_RESULTS:
                        g1 = JUDGE_RESULTS[(tag, i, rd, keyname, 'glm-5.3')]
                        g2 = JUDGE_RESULTS[(tag, i, rd, keyname, 'glm-5.3-flash')]
                    else:
                        g1 = glm_rating(key, 'glm-5.3', demand, txt, 4096)
                        g2 = glm_rating(key, 'glm-5.3-flash', demand, txt, 4096)
                med = sorted([rec, g1, g2])[1]
                if med >= ACCEPT:
                    total += round(PRICE * speed_price(rr.get('secs', 30)))
            sess3.append(total)
            print(f"{tag} sess{i+1}: 3-judge ¥{total:.0f} ({time.time()-t0:.0f}s)", flush=True)
        mean = sum(sess3) / len(sess3)
        print(f"== {tag}: n={len(sess3)} 3-judge mean ¥{mean:.0f} runs={[round(x) for x in sess3]}", flush=True)
        out_runs[tag] = sess3
    pool = out_runs['v6'] + out_runs['v7']
    print(f"== POOLED V2 (n={len(pool)}): 3-judge mean ¥{sum(pool)/len(pool):.0f} "
          f"median ¥{sorted(pool)[len(pool)//2]:.0f}", flush=True)
    OUT.write_text(json.dumps(out_runs, indent=2))


if __name__ == '__main__':
    main()
