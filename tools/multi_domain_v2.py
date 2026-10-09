#!/usr/bin/env python3
"""Multi-domain evaluation with fine-tuned models + V2 inference stack.

Fixes the single-domain gap: fixture + layout domains, n sessions each,
native 3-judge median (mimo-v2.6-pro + glm-5.3 + glm-5.3-flash), same CAD
chain / pricing / capital semantics as the main bench.

Arms:
  --arm v15           local FluxEidosV1.5 weights, pristine prompts
  --arm v2            + syntax repair, best-of-3 R1 (parts-first), conditional
                      resample (+second retry on R4/R5), judge-retry, and a
                      WITHIN-DOMAIN experience bank that starts empty and
                      accumulates rating>=6 designs across sessions (JitRL-
                      accumulate semantics — measures whether the experience
                      mechanism itself transfers to new domains)
  --designer NAME     API baseline instead (e.g. mimo-v2.6-flash)
"""
import argparse, json, os, re, statistics, sys, time
from pathlib import Path

os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
HERE = Path(__file__).resolve().parent
BENCH = HERE.parent
sys.path.insert(0, str(HERE))

import money_bench_v5 as mb
from money_bench_v5 import MODELS, call, check_real_reuse, multi_judge, speed_price, PRICE, ACCEPT
from rsi_night_loop import cad_eval
from multi_domain_bench import DOMAINS, SYSTEMS
import surpass_bench as sb
from openrsi_sft_v2 import zai_key

RESULTS = BENCH / 'runs' / 'multi_domain_v2'
TOKEN_PLAN_BASE = 'https://token-plan-cn.xiaomimimo.com/v1'


def median3(judges, demand, text, cad, folder, rd, tries=2):
    """3-judge median, judges in parallel, one retry on all-zero."""
    from concurrent.futures import ThreadPoolExecutor
    import os as _os
    seq = _os.environ.get('MD_SERIAL_JUDGES') == '1'
    for t in range(tries):
        def one(item):
            name, jspec = item
            return multi_judge({name: jspec}, demand, text, cad, folder / f'j_{name}_t{t}', rd)
        if seq:
            scores = [s for item in list(judges.items()) for s in one(item)]
        else:
            with ThreadPoolExecutor(max_workers=3) as ex:
                scores = [s for ss in ex.map(one, list(judges.items())) for s in ss]
        ratings = [s['rating'] for s in scores if s.get('rating', 0) > 0]
        if ratings:
            return sorted(ratings)[len(ratings) // 2]
        time.sleep(2)
    return 0


def parse_reduced_desk(demand):
    m = re.search(r'reduced to (\d+)\s*x\s*(\d+)\s*mm', demand)
    return (int(m.group(1)), int(m.group(2))) if m else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--arm', choices=['v15', 'v2'])
    ap.add_argument('--designer', help='API baseline name from MODELS')
    ap.add_argument('--domains', nargs='+', default=['fixture', 'layout'])
    ap.add_argument('--sessions', type=int, default=5)
    a = ap.parse_args()
    if not a.arm and not a.designer:
        ap.error('need --arm or --designer')

    if not os.environ.get('ZAI_KEY'):
        os.environ['ZAI_KEY'] = zai_key()
    judges = {n: dict(MODELS[n]) for n in ('mimo-v2.6-pro', 'glm-5.3', 'glm-5.3-flash')}
    for j in judges.values():  # user is on token-plan mode; route mimo via token-plan base
        if j.get('api_base', '').startswith('https://api.xiaomimimo.com'):
            j['api_base'] = TOKEN_PLAN_BASE

    api_spec = None
    model = tok = None
    if a.designer:
        api_spec = dict(MODELS[a.designer])
        if api_spec.get('api_base', '').startswith('https://api.xiaomimimo.com'):
            api_spec['api_base'] = TOKEN_PLAN_BASE
        dn = a.designer
    else:
        import torch
        from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
        from peft import PeftModel
        tok = AutoTokenizer.from_pretrained(sb.BASE, trust_remote_code=True)
        if tok.pad_token is None:
            tok.pad_token = tok.eos_token
        bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4',
                                 bnb_4bit_compute_dtype=torch.bfloat16,
                                 bnb_4bit_use_double_quant=True)
        model = AutoModelForCausalLM.from_pretrained(sb.BASE, quantization_config=bnb,
                                                     device_map='cuda', trust_remote_code=True)
        model = PeftModel.from_pretrained(model, sb.ADAPTER)
        model.eval()
        dn = f'FluxEidos{"V2" if a.arm == "v2" else "V1.5"}-local'

    tag = a.designer or a.arm
    all_out = []
    for dom in a.domains:
        spec_d = DOMAINS[dom]
        system = SYSTEMS[dom]
        bank = {}  # rd -> text, within-domain accumulating experience (starts empty)
        dom_runs = []
        print(f'\n===== domain {dom} | arm {tag} =====', flush=True)
        for si in range(a.sessions):
            sess_dir = RESULTS / tag / dom / f'sess{si+1}'
            sess_dir.mkdir(parents=True, exist_ok=True)
            capital, rounds, total = {}, [], 0.0

            def gen(demand, rd, temp, seed, max_new=1500):
                msg = {'demand': demand,
                       'capital': [{'id': k, 'desc': v['description']} for k, v in capital.items()],
                       'hint': 'Use capital(asset_id) to import previous modules.' if capital else None}
                user = json.dumps(msg, ensure_ascii=False)
                if a.arm == 'v2' and rd > 0 and rd in bank:
                    user += (f"\n\nHere is an example of a HIGH-QUALITY design for this kind of "
                             f"request:\n{bank[rd]}")
                if api_spec is not None:
                    text, usage, secs = call(api_spec, system, user, sess_dir / f'g{rd}_{seed}', f'g{rd}_{seed}')
                    return text.strip(), secs
                prompt = tok.apply_chat_template(
                    [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}],
                    tokenize=False, add_generation_prompt=True, enable_thinking=False)
                text, secs = sb.generate(model, tok, prompt, max_new=max_new, temp=temp, seed=seed)
                return sb.repair_design(text), secs

            def do_round_api(rd):
                demand = spec_d['demands'][rd]
                desk = parse_reduced_desk(demand) if rd == 4 else spec_d['desk']
                for att in range(4):
                    text, secs = gen(demand, rd, 0.6, att)
                    if not text or len(text) < 60:
                        time.sleep(4)   # throttle backoff — empty responses mean rate limit
                        continue
                    cad = cad_eval(text, capital, sess_dir / f'r{rd}_a{att}', desk=desk)
                    if cad.get('metrics'):
                        return text, cad, secs, desk
                return None, None, 0, desk

            for rd in range(5):
                desk = parse_reduced_desk(spec_d['demands'][rd]) if rd == 4 else spec_d['desk']
                if api_spec is not None:
                    text, cad, secs, desk = do_round_api(rd)
                elif a.arm == 'v2' and rd == 0:
                    cands, t_tot = [], 0.0
                    for k in range(3):
                        ctext, csecs = gen(spec_d['demands'][0], 0, 0.7, 42 + 1000 * si + 77 * k, max_new=900)
                        t_tot += csecs
                        ctext = sb.repair_design(ctext)
                        if len(ctext) < 60:
                            continue
                        ccad = cad_eval(ctext, capital, sess_dir / f'r{rd}_c{k}', desk=desk)
                        if ccad.get('metrics'):
                            try:
                                np_ = len(json.loads(ctext).get('parts', []))
                            except Exception:
                                np_ = 0
                            cands.append(((-np_, ccad['metrics'].get('overlap_mm3', 1e9)), ctext, ccad))
                    if cands:
                        cands.sort(key=lambda c: c[0])
                        _, text, cad = cands[0]
                        secs = round(t_tot, 1)
                    else:
                        text, secs = '', round(t_tot, 1)
                else:
                    text, secs = gen(spec_d['demands'][rd], rd, 0.3, 42 + rd + 1000 * si)
                cad = None
                if not text or len(text) < 60:
                    rounds.append({'rd': rd, 'rating': 0, 'sold': False, 'rev': 0, 'secs': secs or 0})
                    print(f'  {dom} s{si+1} R{rd+1}: no text', flush=True)
                    continue
                if cad is None:
                    cad = cad_eval(text, capital, sess_dir / f'r{rd}_v1', desk=desk)
                rating = median3(judges, spec_d['demands'][rd], text, cad, sess_dir, rd) if cad.get('metrics') else 0

                # v2 retries
                if a.arm == 'v2' and rating < ACCEPT and rd > 0:
                    rtext, rsecs = gen(spec_d['demands'][rd], rd, 0.6, 42 + rd + 1000 * si + 555)
                    rtext = sb.repair_design(rtext)
                    if len(rtext) >= 60:
                        rcad = cad_eval(rtext, capital, sess_dir / f'r{rd}_v2', desk=desk)
                        if rcad.get('metrics'):
                            rr = median3(judges, spec_d['demands'][rd], rtext, rcad, sess_dir / f'r{rd}_v2', rd)
                            if rr > rating:
                                text, cad, rating = rtext, rcad, rr
                                secs = round(secs + rsecs, 1)
                    if rating < ACCEPT and rd >= 3:
                        r2text, r2secs = gen(spec_d['demands'][rd], rd, 0.8, 42 + rd + 1000 * si + 999)
                        r2text = sb.repair_design(r2text)
                        if len(r2text) >= 60:
                            r2cad = cad_eval(r2text, capital, sess_dir / f'r{rd}_v3', desk=desk)
                            if r2cad.get('metrics'):
                                r2r = median3(judges, spec_d['demands'][rd], r2text, r2cad, sess_dir / f'r{rd}_v3', rd)
                                if r2r > rating:
                                    text, cad, rating = r2text, r2cad, r2r
                                    secs = round(secs + r2secs, 1)

                sold = rating >= ACCEPT
                rev = round(PRICE * speed_price(secs)) if sold else 0
                total += rev
                reused = check_real_reuse(text, set(capital.keys()))
                if cad.get('metrics'):
                    capital[f'r{rd+1}'] = {'status': 'EXECUTED_CAD', 'step_path': cad.get('step_path', ''),
                                           'description': f'Round {rd+1}'}
                    if rating >= 6 and rd > 0 and text not in bank.get(rd, ''):
                        bank[rd] = text
                rounds.append({'rd': rd, 'rating': rating, 'sold': sold, 'rev': rev,
                               'reused': reused, 'secs': secs})
                print(f'  {dom} s{si+1} R{rd+1}: {"OK" if sold else ".."} {rating}/10 '
                      f'{"reuse" if reused else "scratch"} {secs:.0f}s Y{rev}', flush=True)

            dom_runs.append({'session': si + 1, 'profit': total, 'rounds': rounds,
                             'sold': f"{sum(1 for r in rounds if r['sold'])}/5"})
            print(f'  => {dom} s{si+1}: Y{total} sold {dom_runs[-1]["sold"]}', flush=True)
            # incremental save so a crash never loses completed sessions
            Path(RESULTS / tag).mkdir(parents=True, exist_ok=True)
            (RESULTS / tag / f'{dom}_partial.json').write_text(json.dumps(dom_runs, indent=2))

        profits = [r['profit'] for r in dom_runs]
        by_rd = {rd: round(statistics.mean([r['rounds'][rd]['rating'] for r in dom_runs]), 1) for rd in range(5)}
        print(f'\n== [{tag}/{dom}] mean Y{statistics.mean(profits):.0f} '
              f'runs={[round(p) for p in profits]} ratings_by_round={by_rd}', flush=True)
        all_out.append({'arm': tag, 'domain': dom, 'designer': dn, 'runs': dom_runs,
                        'mean_profit': round(statistics.mean(profits), 1),
                        'ratings_by_round': by_rd})

    out = RESULTS / f'{tag}_results.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(all_out, indent=2, ensure_ascii=False))
    print(f'\nsaved: {out}', flush=True)


if __name__ == '__main__':
    main()
