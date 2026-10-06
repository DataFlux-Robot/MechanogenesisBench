#!/usr/bin/env bash
# Day-2 master sequence: 2 more seeds x 2 arms, then capital demo v2, then analysis.
# Existing seed-0 data (rsi/, control/) is reused. Fully unattended.
set -u
cd /home/exuber/CODE/CORE/pythonProject1/AUTORESEARCH/MechanogenesisBench-upstream
PY=/home/exuber/.venvs/dd_qwen9b_fla_20260910/bin/python
export MIMO_KEY="${MIMO_KEY:?set MIMO_KEY env var before running}"

run_arm () {  # arm, seed-offset
  echo "[master] $(date +%H:%M) launching arm=$1 seed=$2" >> runs/rsi_night/master.log
  $PY -W ignore tools/rsi_night_loop.py --arm "$1" --gens 4 --seed-offset "$2" \
      --init-adapter /home/exuber/models/prsi_rl_v3/iter6 \
      >> "runs/rsi_night/${1}_s${2}.log" 2>&1
  echo "[master] $(date +%H:%M) finished arm=$1 seed=$2 rc=$?" >> runs/rsi_night/master.log
}

run_arm rsi 1
run_arm control 1
run_arm rsi 2
run_arm control 2

echo "[master] $(date +%H:%M) capital demo v2" >> runs/rsi_night/master.log
$PY -W ignore tools/capital_inheritance_demo.py > runs/rsi_night/cap_demo2.log 2>&1
echo "[master] $(date +%H:%M) capital demo done rc=$?" >> runs/rsi_night/master.log

$PY tools/rsi_night_analysis.py > runs/rsi_night/ANALYSIS_DAY2.txt 2>&1
echo "[master] $(date +%H:%M) ALL DONE" >> runs/rsi_night/master.log
