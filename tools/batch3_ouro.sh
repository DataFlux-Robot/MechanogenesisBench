#!/usr/bin/env bash
# Batch 3: Ouro looped-transformer variants (the host models of LoopSpec, arXiv:2609.17184).
# Runs after batch2 completes. Same zero-shot protocol.
set -u
cd /home/exuber/CODE/CORE/pythonProject1/AUTORESEARCH/MechanogenesisBench-upstream
export MIMO_KEY="${MIMO_KEY:?set MIMO_KEY env var}"
PY=/home/exuber/.venvs/dd_qwen9b_fla_20260910/bin/python
VLLM=/home/exuber/.venvs/vllm_serve/bin/python
LOG=runs/batch3_zeroshot.log

# wait for batch2 to finish (shared GPU)
for i in $(seq 1 900); do grep -aq "ALL DONE" runs/batch2_zeroshot.log 2>/dev/null && break; sleep 30; done
echo "[b3] $(date +%H:%M) batch2 finished, starting Ouro" >> $LOG

for spec in "ouro-2.6b ByteDance/Ouro-2.6B" "ouro-2.6b-thinking ByteDance/Ouro-2.6B-Thinking"; do
  set -- $spec; tag=$1; repo=$2; dir=/home/exuber/models/zs-$tag
  echo "[b3] $(date +%H:%M) === $tag ===" >> $LOG
  $PY -c "
from huggingface_hub import snapshot_download
snapshot_download('$repo', local_dir='$dir')
print('DL-OK')" > /tmp/dl3_$tag.log 2>&1 || { echo "[b3] $tag DL FAILED" >> $LOG; continue; }
  nohup $VLLM -m vllm.entrypoints.openai.api_server --model $dir --served-model-name $tag \
    --port 8100 --max-model-len 4096 --gpu-memory-utilization 0.93 --enforce-eager \
    --max-num-seqs 2 --max-num-batched-tokens 4096 --trust-remote-code > /tmp/vllm3_$tag.log 2>&1 &
  ok=0
  for i in $(seq 1 40); do curl -s --max-time 5 http://127.0.0.1:8100/v1/models | grep -q '"'$tag'"' && ok=1 && break; sleep 10; done
  if [ $ok = 1 ]; then
    MIMO_KEY=$MIMO_KEY /home/exuber/CODE/CORE/pythonProject1/AUTORESEARCH/text-to-cad/.venv/bin/python \
      tools/run_local_bench.py --endpoint http://127.0.0.1:8100/v1 --served-model $tag \
      --designer $tag-zeroshot --judges mimo-v2.6-pro --n 3 --max-tokens 3000 \
      >> runs/bench3_$tag.log 2>&1
    echo "[b3] $(date +%H:%M) $tag done: $(grep -a 'profit mean' runs/bench3_$tag.log | tail -1 | sed 's/.*mean=//')" >> $LOG
  else
    echo "[b3] $tag SERVER FAILED" >> $LOG
  fi
  pkill -f 'vllm.entrypoints' || true; sleep 10; rm -rf $dir
done
echo "[b3] $(date +%H:%M) ALL DONE" >> $LOG
