#!/usr/bin/env bash
# Batch zero-shot Money Bench for 7 community/open models (user-requested controls).
# Per model: download -> vLLM serve -> bench n=3 -> stop -> delete weights+cache.
set -u
cd /home/exuber/CODE/CORE/pythonProject1/AUTORESEARCH/MechanogenesisBench-upstream
export MIMO_KEY="${MIMO_KEY:?set MIMO_KEY env var}"
PY=/home/exuber/.venvs/dd_qwen9b_fla_20260910/bin/python
VLLM=/home/exuber/.venvs/vllm_serve/bin/python
LOG=runs/batch_zeroshot.log
MODELS_DIR=/home/exuber/models

run_one () {  # tag repo_dir flags...
  local tag=$1 repo=$2 dir=$3; shift 3
  echo "[batch] $(date +%H:%M) === $tag ===" >> $LOG
  $PY -c "
from huggingface_hub import snapshot_download
snapshot_download('$repo', local_dir='$dir')
print('DL-OK')
" >> runs/dl_$tag.log 2>&1 || { echo "[batch] $tag DOWNLOAD FAILED" >> $LOG; return 1; }

  nohup $VLLM -m vllm.entrypoints.openai.api_server \
    --model $dir --served-model-name $tag --port 8100 \
    --max-model-len 4096 --gpu-memory-utilization 0.93 --enforce-eager \
    --max-num-seqs 2 --max-num-batched-tokens 2048 "$@" \
    > /tmp/vllm_$tag.log 2>&1 &
  for i in $(seq 1 40); do
    curl -s --max-time 5 http://127.0.0.1:8100/v1/models | grep -q "$tag" && break; sleep 10
  done
  curl -s --max-time 5 http://127.0.0.1:8100/v1/models | grep -q "$tag" || {
    echo "[batch] $tag SERVER FAILED" >> $LOG; pkill -f 'vllm.entrypoints' || true; sleep 8;
    rm -rf $dir; return 1; }

  MIMO_KEY=$MIMO_KEY /home/exuber/CODE/CORE/pythonProject1/AUTORESEARCH/text-to-cad/.venv/bin/python \
    tools/run_local_bench.py --endpoint http://127.0.0.1:8100/v1 --served-model $tag \
    --designer $tag-zeroshot --judges mimo-v2.6-pro --n 3 --max-tokens 3000 \
    >> runs/bench_$tag.log 2>&1
  echo "[batch] $(date +%H:%M) $tag bench done: $(grep -a 'profit mean' runs/bench_$tag.log | tail -1)" >> $LOG
  pkill -f 'vllm.entrypoints' || true; sleep 10
  rm -rf $dir
  $PY -c "
from huggingface_hub import scan_cache_dir
for r in scan_cache_dir().repos:
    if r.size_on_disk > 5e9: r.delete_repo()
" 2>/dev/null || true
}

run_one gemma-4-12b    cyankiwi/gemma-4-12B-it-AWQ-INT4 $MODELS_DIR/zs-gemma4 --kv-cache-dtype fp8
run_one ornith-1.5-9b  ornith-ai/Ornith-1.5-9B         $MODELS_DIR/zs-ornith --kv-cache-dtype fp8
run_one qwopus3.5-9b-v3 Jackrong/Qwopus3.5-9B-v3       $MODELS_DIR/zs-qwopus --kv-cache-dtype fp8
run_one qwythos-9b-v2  empero-ai/Qwythos-9B-v2         $MODELS_DIR/zs-qwythos --kv-cache-dtype fp8
run_one omnicoder-9b   Tesslate/OmniCoder-9B           $MODELS_DIR/zs-omnicoder --kv-cache-dtype fp8
run_one neohorse-1-9b  TokenRhythm/NeoHorse-1-9B       $MODELS_DIR/zs-neohorse --kv-cache-dtype fp8
run_one zdtaichu5-9b   TaichuAI/ZDTaichu5.0-9B-FP8     $MODELS_DIR/zs-zdtaichu
echo "[batch] $(date +%H:%M) ALL DONE" >> $LOG
