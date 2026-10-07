#!/usr/bin/env python3
"""JitRL for Money Bench: test-time policy optimization via experience retrieval
and advantage-weighted logit modulation (arXiv:2601.18510 adapted to design generation).

RSI loop, no weight updates:
  session k generates designs -> real CAD + judge rewards -> stored as experience
  triplets (context, token sequence, advantage) -> session k+1 modulates logits
  z'(t) = z(t) + beta * A(experiences whose prefix matches current generation)

Protocol: standard Money Bench v5 (fixed 5 demands, real CAD, mimo judge, speed
pricing), memory starts EMPTY and accumulates across the eval sessions — the
across-session profit trajectory IS the test-time RSI measurement, zero leakage.

Arms (same model, same HF inference path — only modulation differs):
  plain : no modulation (control)
  jitrl : + experience modulation, memory grows across sessions

Usage (dd_qwen9b venv):
  MIMO_KEY=... python tools/jitrl_bench.py --arm jitrl --n 5
"""
import argparse, json, os, statistics, sys, time
from pathlib import Path

os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import money_bench_v5 as mb
from rsi_night_loop import cad_eval, judge, speed_price, ACCEPT, OUT

BASE = '/home/exuber/models/qwen3.5-9b-bf16'
ADAPTER = '/home/exuber/models/prsi_gar2/gen5'  # GAR-RL v2 gen5
RESULTS = HERE.parent / 'runs' / 'jitrl'
BETA_BASE = 0.5     # starting modulation strength
BETA_MAX = 1.2      # max modulation as memory grows

def adaptive_beta(n_mem):
    import math
    return min(BETA_MAX, BETA_BASE + 0.1 * math.log2(max(n_mem, 1)))
BOOST_CAP = 3.0     # max additive logit boost per token
MAX_EXP = 20        # experiences retrieved per context
MAX_EXP_TOKENS = 1800


# ── experience bank ──
def reward_of(rating, rev, valid, reused):
    return rev + 10 * rating + 50 * valid + 50 * reused


class ExperienceBank:
    def __init__(self):
        self.entries = []  # {'demand','round','text','reward'}

    def add(self, demand, rd, text, rating, rev, valid, reused):
        self.entries.append({'demand': demand, 'round': rd, 'text': text,
                              'rating': rating, 'rev': rev, 'valid': valid,
                              'reused': reused,
                              'reward': reward_of(rating, rev, valid, reused)})

    def retrieve(self, demand, rd):
        """Exact-demand first, then fuzzy token-overlap, then same-round-type."""
        same = [e for e in self.entries if e['demand'] == demand]
        if len(same) < 3:
            # fuzzy: token overlap matching
            toks = set(demand.lower().split())
            scored = []
            for e in self.entries:
                if e in same: continue
                e_toks = set(e['demand'].lower().split())
                overlap = len(toks & e_toks) / max(len(toks | e_toks), 1)
                if overlap > 0.3:
                    scored.append((overlap, e))
            scored.sort(key=lambda x: -x[0])
            same += [e for _, e in scored[:MAX_EXP - len(same)]]
        if len(same) < 3:
            same += [e for e in self.entries if e['round'] == rd and e not in same]
        pool = [e for e in same if e['valid'] and e['rating'] >= 3]
        pool = sorted(pool, key=lambda e: -e['reward'])[:MAX_EXP]
        if not pool:
            return []
        mu = statistics.mean(e['reward'] for e in same)
        sd = statistics.pstdev([e['reward'] for e in same]) or 1.0
        for e in pool:
            e['adv'] = max(-2.0, min(2.0, (e['reward'] - mu) / sd))
        return pool


# ── JitRL trie logit processor ──
class JitRLLogitsProcessor:
    """Boosts tokens following matched prefixes of high-advantage experiences.

    One trie of retrieved experience token sequences; cursors advance while the
    generated prefix matches; a fresh root cursor opens each step so high-reward
    n-grams can boost from any position (advantage-weighted LM interpolation).
    """

    def __init__(self, tokenizer, experiences):
        self._tok = tokenizer
        # trie nodes: {'a': {token: summed_adv_of_edges}, 'c': {token: child_node}}
        self.root = {'a': {}, 'c': {}}
        for e in experiences:
            ids = tokenizer(e['text'], add_special_tokens=False)['input_ids'][:MAX_EXP_TOKENS]
            node = self.root
            for t in ids:
                cur = node.setdefault('c', {})
                nxt = cur.get(t)
                if nxt is None:
                    nxt = {'a': {}, 'c': {}}
                    cur[t] = nxt
                node['a'][t] = node['a'].get(t, 0.0) + e['adv']
                node = nxt
        self.cursors = [self.root]

    def reset(self):
        self.cursors = [self.root]

    def step(self, last_token, scores):
        """Advance cursors with last_token, apply boosts, return modified scores."""
        nxt = []
        for node in self.cursors:
            child = node.get('c', {}).get(last_token) if last_token is not None else None
            if child is not None:
                nxt.append(child)
        nxt.append(self.root)  # allow fresh matches from any position
        self.cursors = nxt[:64]
        import torch
        for node in self.cursors:
            for tok, a in node.get('a', {}).items():
                scores[0, tok] += min(adaptive_beta(getattr(self, '_n_mem', 10)) * a, BOOST_CAP)
        return scores


def generate_with_jitrl(model, tokenizer, prompt, experiences, max_new=1800):
    import torch
    ids = tokenizer(prompt, return_tensors='pt', truncation=True, max_length=3600).to(model.device)
    proc = JitRLLogitsProcessor(tokenizer, experiences) if experiences else None
    if proc:
        proc._n_mem = len(experiences)
    t0 = time.monotonic()
    generated = []
    from transformers import LogitsProcessorList

    class _Wrapper:
        def __init__(self, p, prompt_len):
            self.p = p
            self.pl = prompt_len
        def __call__(self, input_ids, scores):
            if input_ids.shape[1] <= self.pl:
                self.p.reset()
                return scores
            return self.p.step(int(input_ids[0, -1]), scores)

    kwargs = dict(**ids, max_new_tokens=max_new, temperature=0.3, do_sample=True,
                  top_p=0.95, pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id)
    if proc:
        kwargs['logits_processor'] = LogitsProcessorList([_Wrapper(proc, ids['input_ids'].shape[1])])
    with torch.no_grad():
        out = model.generate(**kwargs)
    new_tokens = out[0][ids['input_ids'].shape[1]:].tolist()
    text = tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
    secs = round(time.monotonic() - t0, 1)
    if text.startswith('```') and text.count('```') >= 2:
        lines = text.split('\n')
        if len(lines) >= 3:
            text = '\n'.join(lines[1:-1]).strip() or text
    if '"h":' in text and '"hypothesis":' not in text:
        text = text.replace('"h":', '"hypothesis":')
    return text, secs


# ── standard bench session (same protocol as money_bench_v5) ──
def run_session(model, tokenizer, bank, use_jitrl, sess_dir, freeze_mem=False):
    sess_dir.mkdir(parents=True, exist_ok=True)
    capital, rounds = {}, []
    total = 0.0
    for rd in range(5):
        demand = mb.DEMANDS[rd]
        best = None
        for att in range(2):
            user = json.dumps({'demand': demand,
                               'capital': [{'id': k, 'desc': v.get('description', '')} for k, v in capital.items()],
                               'hint': 'Use capital(asset_id) to import previous modules.' if capital else None})
            prompt = tokenizer.apply_chat_template(
                [{'role': 'system', 'content': mb.SYSTEM}, {'role': 'user', 'content': user}],
                tokenize=False, add_generation_prompt=True, enable_thinking=False)
            exps = bank.retrieve(demand, rd) if use_jitrl else []
            text, secs = generate_with_jitrl(model, tokenizer, prompt, exps)
            if not text or len(text) < 40:
                continue
            cad = cad_eval(text, capital, sess_dir / f'r{rd}_a{att}', (420, 280))
            if cad.get('metrics'):
                best = (text, secs, cad)
                break
        if best is None:
            rounds.append({'rd': rd, 'rating': 0, 'sold': False, 'rev': 0, 'reused': False, 'secs': 0})
            print(f"  R{rd+1}: ✗ no valid design", flush=True)
            continue
        text, secs, cad = best
        rating = judge(demand, text, cad.get('metrics'))
        sold = rating >= ACCEPT
        rev = round(100 * speed_price(secs)) if sold else 0
        total += rev
        try:
            reused = any(n.get('op') == 'capital' for n in json.loads(text).get('nodes', []))
        except Exception:
            reused = False
        if sold or rating >= 3:
            capital[f'r{rd+1}'] = {'status': 'EXECUTED_CAD', 'step_path': cad['step_path'],
                                   'description': f'Round {rd+1} design', 'measurements': {}}
        # JitRL memory update: every executed design becomes experience
        if not freeze_mem:
            bank.add(demand, rd, text, rating, rev, True, reused)
        rounds.append({'rd': rd, 'rating': rating, 'sold': sold, 'rev': rev,
                       'reused': reused, 'secs': secs})
        print(f"  R{rd+1}: {'✅' if sold else '❌'} {rating}/10 {'♻️' if reused else '🔧'} "
              f"{secs:.0f}s ¥{rev} | mem {len(bank.entries)}", flush=True)
    return {'profit': total, 'rounds': rounds,
            'sold': f"{sum(1 for r in rounds if r['sold'])}/5",
            'reuse': f"{sum(1 for r in rounds if r.get('reused'))}/4"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--arm', choices=['plain', 'jitrl'], required=True)
    ap.add_argument('--n', type=int, default=5)
    ap.add_argument('--mode', choices=['accumulate', 'mature'], default='accumulate')
    ap.add_argument('--bank-from', default=None, help='load a saved bank (mature mode keeps it frozen)')
    a = ap.parse_args()

    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
    from peft import PeftModel
    RESULTS.mkdir(parents=True, exist_ok=True)
    tok = AutoTokenizer.from_pretrained(BASE, trust_remote_code=True)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4',
                             bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True)
    model = AutoModelForCausalLM.from_pretrained(BASE, quantization_config=bnb,
                                                 device_map='cuda', trust_remote_code=True)
    model = PeftModel.from_pretrained(model, ADAPTER)
    model.eval()

    bank = ExperienceBank()  # starts EMPTY — memory grows only within this eval
    if a.bank_from and Path(a.bank_from).exists():
        bank.entries = json.loads(Path(a.bank_from).read_text())
        print(f'loaded bank: {len(bank.entries)} experiences', flush=True)
    runs = []
    for i in range(a.n):
        print(f"\n=== [{a.arm}] session {i+1}/{a.n} (memory {len(bank.entries)}) ===", flush=True)
        r = run_session(model, tok, bank, a.arm == 'jitrl',
                        RESULTS / a.mode / f'sess{i+1}', freeze_mem=(a.mode == 'mature'))
        runs.append(r)
        print(f"  => profit ¥{r['profit']} | sold {r['sold']} | reuse {r['reuse']}", flush=True)
    (RESULTS / f'{a.mode}_bank.json').write_text(json.dumps(bank.entries, ensure_ascii=False))
    out = {'arm': a.arm, 'mode': a.mode, 'runs': runs,
           'profits': [r['profit'] for r in runs],
           'mean': statistics.mean([r['profit'] for r in runs])}
    (RESULTS / f'{a.mode}_results.json').write_text(json.dumps(out, indent=2))
    print(f"\n[{a.arm}] profits: {[r['profit'] for r in runs]} mean ¥{out['mean']:.0f}")


if __name__ == '__main__':
    main()
