#!/usr/bin/env bash
# Full Money Bench evaluation for JitRL test-time RSI:
#   1) accumulate n=10 (memory 0->full, trajectory = RSI curve)
#   2) mature n=5 (memory frozen -> steady-state = leaderboard number)
#   3) plain control n=10 (same inference path, no memory)
#   4) 3-judge rejudge of the mature sessions (primary-table protocol)
set -u
cd /home/exuber/CODE/CORE/pythonProject1/AUTORESEARCH/MechanogenesisBench-upstream
export MIMO_KEY="${MIMO_KEY:?set MIMO_KEY env var}"
PY=/home/exuber/.venvs/dd_qwen9b_fla_20260910/bin/python

echo "[jitrl-full] $(date +%H:%M) accumulate n=10" >> runs/jitrl_full.log
$PY -W ignore tools/jitrl_bench.py --arm jitrl --mode accumulate --n 10 >> runs/jitrl_acc.log 2>&1
echo "[jitrl-full] $(date +%H:%M) accumulate done rc=$?" >> runs/jitrl_full.log

$PY -W ignore tools/jitrl_bench.py --arm jitrl --mode mature --n 5 --bank-from runs/jitrl/accumulate_bank.json >> runs/jitrl_mat.log 2>&1
echo "[jitrl-full] $(date +%H:%M) mature done rc=$?" >> runs/jitrl_full.log

$PY -W ignore tools/jitrl_bench.py --arm plain --mode accumulate --n 10 >> runs/jitrl_plain10.log 2>&1
echo "[jitrl-full] $(date +%H:%M) plain10 done rc=$?" >> runs/jitrl_full.log

PYTHONPATH="/home/exuber/CODE/CORE/pythonProject1/AUTORESEARCH/text-to-cad/packages/cadpy/src:/home/exuber/CODE/CORE/pythonProject1/AUTORESEARCH/MechanogenesisBenchDEV/src" \
  /home/exuber/CODE/CORE/pythonProject1/AUTORESEARCH/text-to-cad/.venv/bin/python -u tools/rejudge.py \
  --dir runs/jitrl/mature --tag jitrl-mature >> runs/jitrl_rejudge.log 2>&1
echo "[jitrl-full] $(date +%H:%M) rejudge done rc=$?" >> runs/jitrl_full.log
echo "[jitrl-full] ALL DONE" >> runs/jitrl_full.log
