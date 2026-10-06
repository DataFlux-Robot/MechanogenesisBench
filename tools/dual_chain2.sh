#!/usr/bin/env bash
# Correct sequential chain: wait full2 -> rsi -> capital -> analysis (all backgrounded).
set -u
cd /home/exuber/CODE/CORE/pythonProject1/AUTORESEARCH/MechanogenesisBench-upstream
export MIMO_KEY="${MIMO_KEY:?set MIMO_KEY env var before running}"
PY=/home/exuber/.venvs/dd_qwen9b_fla_20260910/bin/python

# 1. wait for the RUNNING full arm (log: dual_full2.log)
for i in $(seq 1 160); do
  grep -aq "\[full\] DONE" runs/dual_full2.log 2>/dev/null && break
  sleep 60
done
echo "[chain2] full done: $(grep -a '\[full\] DONE' runs/dual_full2.log | tail -1)"

# 2. rsi arm
$PY -W ignore tools/dual_loop_prsi.py --arm rsi --gens 3 > runs/dual_rsi2.log 2>&1 &
RSI_PID=$!
wait $RSI_PID
echo "[chain2] rsi done: $(grep -a '\[rsi\] DONE' runs/dual_rsi2.log | tail -1)"

# 3. capital arm
$PY -W ignore tools/dual_loop_prsi.py --arm capital --gens 3 > runs/dual_capital2.log 2>&1 &
CAP_PID=$!
wait $CAP_PID
echo "[chain2] capital done: $(grep -a '\[capital\] DONE' runs/dual_capital2.log | tail -1)"

$PY tools/dual_loop_analysis.py > runs/dual_loop/ANALYSIS.txt 2>&1
echo "[chain2] CHAIN-ALL-DONE"
