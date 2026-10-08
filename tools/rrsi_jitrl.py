#!/usr/bin/env python3
"""RRSI-Regularized JitRL: JitRL + Google's regularization techniques (arXiv:2609.24972).

Integrates three RRSI regularization principles into our JitRL:
  1. CRITIC: screens incoming memories for benchmark-specific overfitting
     (rejects designs too similar to a single benchmark demand pattern)
  2. NOISE-ADJUSTED FLOOR: only accept experience entries whose advantage
     exceeds evaluation noise (prevents memorizing noise)
  3. COST RULE + PRUNING: memories that cost more tokens than they deliver in
     quality are pruned; stale unused memories are removed

Combined with JitRL's test-time experience accumulation and advantage-weighted
logit modulation, this creates a regularized self-improvement loop that
avoids overfitting to specific benchmark tasks.
"""
import argparse, json, math, os, random, re, statistics, sys, time
from pathlib import Path
from collections import defaultdict

os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
HERE = Path(__file__).resolve().parent
BENCH = HERE.parent
sys.path.insert(0, str(HERE))
import money_bench_v5 as mb
from rsi_night_loop import cad_eval, judge, speed_price, ACCEPT

BASE = '/home/exuber/models/qwen3.5-9b-bf16'
ADAPTER = '/home/exuber/models/prsi_rl_v3/iter6'  # V1.0 champion
RESULTS = BENCH / 'runs' / 'rrsi_jitrl'

# ═══ RRSI Regularization Parameters ═══
NOISE_FLOOR = 1.5        # minimum advantage magnitude to accept a memory
MAX_MEMORY = 24           # hard cap on memory size (cost rule)
STALENESS_LIMIT = 3       # prune memories unused for N rounds
CRITIC_SIMILARITY = 0.85  # reject memories too similar to one benchmark demand
BETA_BASE = 0.5
BETA_MAX = 1.0


# ═══ RRSI Critic: screen for benchmark-specific overfitting ═══
def critic_screen(demand, all_demands):
    """RRSI critic: reject memories that are too benchmark-specific.
    A memory is rejected if its demand is nearly identical to one specific
    benchmark demand (memorization) rather than a general pattern."""
    def token_overlap(a, b):
        ta, tb = set(a.lower().split()), set(b.lower().split())
        return len(ta & tb) / max(len(ta | tb), 1)

    # Check against ALL benchmark demands (not just current one)
    max_sim = max(token_overlap(demand, d) for d in all_demands)
    if max_sim > CRITIC_SIMILARITY:
        return False, f"rejected: {max_sim:.2f} similarity to benchmark demand (overfitting risk)"
    return True, "generalizable"


# ═══ RRSI Noise-Adjusted Floor: only accept beyond-noise advantages ═══
def noise_adjusted_accept(advantage, noise_floor=NOISE_FLOOR):
    """RRSI noise floor: reject gains within evaluation variance."""
    if abs(advantage) < noise_floor:
        return False, f"advantage {advantage:.2f} within noise floor {noise_floor}"
    return True, "beyond noise"


# ═══ RRSI Cost Rule + Pruning ═══
def prune_memories(bank, current_round):
    """RRSI pruner: remove stale or oversized memories."""
    pruned = []
    for e in bank.entries:
        # prune if unused for too long (stale)
        rounds_since_use = current_round - e.get('last_used', 0)
        if rounds_since_use > STALENESS_LIMIT:
            pruned.append(e)
            continue
        # prune if too many memories (cost rule)
    if len(bank.entries) - len(pruned) > MAX_MEMORY:
        # keep only the best MAX_MEMORY by reward
        remaining = [e for e in bank.entries if e not in pruned]
        remaining.sort(key=lambda x: -x.get('reward', 0))
        to_keep = set(id(e) for e in remaining[:MAX_MEMORY])
        pruned += [e for e in remaining if id(e) not in to_keep]
    for p in pruned:
        if p in bank.entries:
            bank.entries.remove(p)
    return len(pruned)


# ═══ Regularized Experience Bank (extends JitRL) ═══
class RegularizedBank:
    """JitRL experience bank with RRSI regularization."""

    def __init__(self, all_demands):
        self.entries = []
        self.all_demands = all_demands
        self.rejected = []  # track critic rejections for analysis

    def add(self, demand, rd, text, rating, rev, valid, reused, round_num):
        # RRSI Critic: screen for benchmark-specific overfitting
        ok, reason = critic_screen(demand, self.all_demands)
        if not ok:
            self.rejected.append({'demand': demand[:50], 'reason': reason, 'round': round_num})
            return False

        # RRSI Noise-Adjusted Floor: check advantage magnitude
        reward = rev + 10 * rating + 50 * valid + 50 * reused
        if len(self.entries) >= 2:
            existing_rewards = [e['reward'] for e in self.entries if e['demand'] == demand]
            if existing_rewards:
                baseline = statistics.mean(existing_rewards)
                advantage = reward - baseline
                ok, reason = noise_adjusted_accept(advantage)
                if not ok:
                    self.rejected.append({'demand': demand[:50], 'reason': reason, 'round': round_num})
                    return False

        self.entries.append({
            'demand': demand, 'round': rd, 'text': text,
            'rating': rating, 'rev': rev, 'valid': valid, 'reused': reused,
            'reward': reward, 'last_used': round_num
        })
        return True

    def retrieve(self, demand, rd):
        """RRSI-style retrieval with staleness tracking."""
        # exact match first
        same = [e for e in self.entries if e['demand'] == demand]
        if len(same) < 3:
            # fuzzy token overlap
            toks = set(demand.lower().split())
            scored = []
            for e in self.entries:
                if e in same: continue
                e_toks = set(e['demand'].lower().split())
                overlap = len(toks & e_toks) / max(len(toks | e_toks), 1)
                if overlap > 0.2:
                    scored.append((overlap, e))
            scored.sort(key=lambda x: -x[0])
            same += [e for _, e in scored[:10]]
        if len(same) < 3:
            same += [e for e in self.entries if e['round'] == rd and e not in same]

        pool = [e for e in same if e['valid'] and e['rating'] >= 3][:20]
        if not pool:
            return []
        mu = statistics.mean(e['reward'] for e in same)
        sd = statistics.pstdev([e['reward'] for e in same]) or 1.0
        for e in pool:
            e['adv'] = max(-2.0, min(2.0, (e['reward'] - mu) / sd))
            e['last_used'] = getattr(e, 'last_used', 0)  # track usage
        return pool


# ═══ JitRL Logit Processor (from our original implementation) ═══
class JitRLLogitsProcessor:
    def __init__(self, tokenizer, experiences):
        self.root = {'a': {}, 'c': {}}
        for e in experiences:
            ids = tokenizer(e['text'], add_special_tokens=False)['input_ids'][:1800]
            node = self.root
            for t in ids:
                cur = node['c']
                nxt = cur.get(t)
                if nxt is None:
                    nxt = {'a': {}, 'c': {}}
                    cur[t] = nxt
                node['a'][t] = node['a'].get(t, 0.0) + e['adv']
                node = nxt
        self.cursors = [self.root]
        self._n_mem = len(experiences)

    def reset(self):
        self.cursors = [self.root]

    def step(self, last_token, scores):
        nxt = []
        for node in self.cursors:
            child = node['c'].get(last_token)
            if child is not None:
                nxt.append(child)
        nxt.append(self.root)
        self.cursors = nxt[:64]
        beta = min(BETA_MAX, BETA_BASE + 0.1 * math.log2(max(self._n_mem, 1)))
        for node in self.cursors:
            for tok, a in node['a'].items():
                scores[0, tok] += min(beta * a, 3.0)
        return scores


def adaptive_beta(n_mem):
    return min(BETA_MAX, BETA_BASE + 0.1 * math.log2(max(n_mem, 1)))


def generate_with_jitrl(model, tokenizer, prompt, experiences):
    import torch
    from transformers import LogitsProcessorList
    ids = tokenizer(prompt, return_tensors='pt', truncation=True, max_length=3600).to(model.device)
    proc = JitRLLogitsProcessor(tokenizer, experiences) if experiences else None
    t0 = time.monotonic()
    class _W:
        def __init__(self, p, pl): self.p = p; self.pl = pl
        def __call__(self, input_ids, scores):
            if input_ids.shape[1] <= self.pl:
                self.p.reset(); return scores
            return self.p.step(int(input_ids[0, -1]), scores)
    kwargs = dict(**ids, max_new_tokens=1800, temperature=0.3, do_sample=True,
                  top_p=0.95, pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id)
    if proc:
        kwargs['logits_processor'] = LogitsProcessorList([_W(proc, ids['input_ids'].shape[1])])
    with torch.no_grad():
        out = model.generate(**kwargs)
    text = tokenizer.decode(out[0][ids['input_ids'].shape[1]:], skip_special_tokens=True).strip()
    secs = round(time.monotonic() - t0, 1)
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.S).strip()
    if text.startswith('```') and text.count('```') >= 2:
        lines = text.split('\n')
        if len(lines) >= 3: text = '\n'.join(lines[1:-1]).strip() or text
    if '"h":' in text and '"hypothesis":' not in text:
        text = text.replace('"h":', '"hypothesis":')
    return text, secs


# ═══ Main evaluation loop ═══
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sessions', type=int, default=5)
    ap.add_argument('--arm', choices=['rrsi', 'vanilla'], default='rrsi')
    a = ap.parse_args()

    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
    from peft import PeftModel

    RESULTS.mkdir(parents=True, exist_ok=True)
    tok = AutoTokenizer.from_pretrained(BASE, trust_remote_code=True)
    if tok.pad_token is None: tok.pad_token = tok.eos_token
    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4',
                             bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True)
    model = AutoModelForCausalLM.from_pretrained(BASE, quantization_config=bnb,
                                                 device_map='cuda', trust_remote_code=True)
    model = PeftModel.from_pretrained(model, ADAPTER)
    model.eval()

    bank = RegularizedBank(mb.DEMANDS)  # RRSI-regularized bank
    all_runs = []
    total_pruned = 0

    for si in range(a.sessions):
        sess_dir = RESULTS / a.arm / f'sess{si+1}'
        sess_dir.mkdir(parents=True, exist_ok=True)
        capital, rounds = {}, []
        total = 0.0
        print(f"\n=== [RRSI-JitRL:{a.arm}] session {si+1}/{a.sessions} "
              f"(mem:{len(bank.entries)} rej:{len(bank.rejected)}) ===", flush=True)

        for rd in range(5):
            demand = mb.DEMANDS[rd]
            best = None
            for att in range(2):
                user = json.dumps({'demand': demand,
                                   'capital': [{'id': k, 'desc': v['description']} for k, v in capital.items()],
                                   'hint': 'Use capital(asset_id) to import previous modules.' if capital else None},
                                  ensure_ascii=False)
                prompt = tok.apply_chat_template(
                    [{'role': 'system', 'content': mb.SYSTEM}, {'role': 'user', 'content': user}],
                    tokenize=False, add_generation_prompt=True, enable_thinking=False)

                exps = bank.retrieve(demand, rd) if a.arm == 'rrsi' else bank.retrieve(demand, rd)
                text, secs = generate_with_jitrl(model, tok, prompt, exps)
                if not text or len(text) < 40: continue
                cad = cad_eval(text, capital, sess_dir / f'r{rd}_a{att}', (420, 280))
                if cad.get('metrics'):
                    best = (text, secs, cad); break

            if best is None:
                rounds.append({'rd': rd, 'rating': 0, 'sold': False, 'rev': 0, 'secs': 0})
                print(f"  R{rd+1}: ✗", flush=True); continue

            text, secs, cad = best
            rating = judge(demand, text, cad.get('metrics'))
            sold = rating >= ACCEPT
            rev = round(100 * speed_price(secs)) if sold else 0
            total += rev
            reused = any(n.get('op') == 'capital' for n in json.loads(text).get('nodes', []))
            if sold or rating >= 3:
                capital[f'r{rd+1}'] = {'status': 'EXECUTED_CAD', 'step_path': cad['step_path'],
                                       'description': f'Round {rd+1} design'}

            # RRSI-regularized memory update
            accepted = bank.add(demand, rd, text, rating, rev, True, reused, si * 5 + rd)

            # RRSI pruning (every 5 rounds)
            if (si * 5 + rd) % 5 == 4:
                pruned = prune_memories(bank, si * 5 + rd)
                total_pruned += pruned

            rounds.append({'rd': rd, 'rating': rating, 'sold': sold, 'rev': rev,
                           'reused': reused, 'secs': secs, 'memory_accepted': accepted})
            print(f"  R{rd+1}: {'✅' if sold else '❌'} {rating}/10 {'♻️' if reused else '🔧'} "
                  f"{secs:.0f}s ¥{rev} | mem:{'✓' if accepted else '✗critic'} "
                  f"(pool:{len(bank.entries)})", flush=True)

        run = {'profit': total, 'rounds': rounds,
               'sold': f"{sum(1 for r in rounds if r['sold'])}/5",
               'memory_size': len(bank.entries),
               'critic_rejections': len(bank.rejected)}
        all_runs.append(run)
        print(f"  => ¥{total} | sold {run['sold']} | mem:{len(bank.entries)} rej:{len(bank.rejected)}", flush=True)

    profits = [r['profit'] for r in all_runs]
    print(f"\n{'='*50}")
    print(f"[RRSI-JitRL:{a.arm}] profit mean ¥{statistics.mean(profits):.0f} "
          f"runs={[round(p) for p in profits]}")
    print(f"  memory: {len(bank.entries)} entries | critic rejected: {len(bank.rejected)} | pruned: {total_pruned}")
    if bank.rejected:
        for r in bank.rejected[:5]:
            print(f"  rejected: {r['reason']}")
    (RESULTS / f'{a.arm}_results.json').write_text(json.dumps({
        'runs': all_runs, 'final_memory_size': len(bank.entries),
        'critic_rejections': len(bank.rejected), 'total_pruned': total_pruned
    }, indent=2))


if __name__ == '__main__':
    main()
