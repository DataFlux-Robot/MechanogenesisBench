#!/usr/bin/env bash
# Batch 4: retry pass — trust-remote-code retries + Ouro via llama.cpp GGUF.
set -u
cd /home/exuber/CODE/CORE/pythonProject1/AUTORESEARCH/MechanogenesisBench-upstream
export MIMO_KEY="${MIMO_KEY:?set MIMO_KEY env var}"
PY=/home/exuber/.venvs/dd_qwen9b_fla_20260910/bin/python
VLLM=/home/exuber/.venvs/vllm_serve/bin/python
LOG=runs/batch4_zeroshot.log
MD=/home/exuber/models

retry_trust () {  # tag repo
  local tag=$1 repo=$2 dir=$MD/zs-$1
  echo "[b4] $(date +%H:%M) === $tag (trust) ===" >> $LOG
  $PY -c "
from huggingface_hub import snapshot_download
snapshot_download('$repo', local_dir='$dir')
print('DL-OK')" > /tmp/dl4_$tag.log 2>&1 || { echo "[b4] $tag DL FAILED" >> $LOG; return 1; }
  nohup $VLLM -m vllm.entrypoints.openai.api_server --model $dir --served-model-name $tag \
    --port 8100 --max-model-len 4096 --gpu-memory-utilization 0.93 --enforce-eager \
    --max-num-seqs 2 --max-num-batched-tokens 4096 --trust-remote-code > /tmp/vllm4_$tag.log 2>&1 &
  local ok=0
  for i in $(seq 1 45); do curl -s --max-time 5 http://127.0.0.1:8100/v1/models | grep -q '"'$tag'"' && ok=1 && break; sleep 10; done
  if [ $ok = 1 ]; then
    MIMO_KEY=$MIMO_KEY /home/exuber/CODE/CORE/pythonProject1/AUTORESEARCH/text-to-cad/.venv/bin/python \
      tools/run_local_bench.py --endpoint http://127.0.0.1:8100/v1 --served-model $tag \
      --designer $tag-zeroshot --judges mimo-v2.6-pro --n 3 --max-tokens 3000 >> runs/bench4_$tag.log 2>&1
    echo "[b4] $(date +%H:%M) $tag done: $(grep -a 'profit mean' runs/bench4_$tag.log | tail -1 | sed 's/.*mean=//')" >> $LOG
  else
    echo "[b4] $tag SERVER FAILED even with trust" >> $LOG
  fi
  pkill -f 'vllm.entrypoints' || true; sleep 10; rm -rf $dir
  $PY -c "
from huggingface_hub import scan_cache_dir
for r in scan_cache_dir().repos:
    if r.size_on_disk > 4e9: r.delete_repo()" 2>/dev/null
}

ouro_gguf () {  # tag repo file
  local tag=$1 repo=$2 file=$3 dir=$MD/zsg-$1
  echo "[b4] $(date +%H:%M) === $tag (llama.cpp) ===" >> $LOG
  $PY -c "
from huggingface_hub import hf_hub_download
hf_hub_download('$repo', '$file', local_dir='$dir')
print('DL-OK')" > /tmp/dl4_$tag.log 2>&1 || { echo "[b4] $tag DL FAILED" >> $LOG; return 1; }
  local G=$(ls $dir/*.gguf | head -1)
  nohup /tmp/llama.cpp/build/bin/llama-server -m "$G" --port 8101 -ngl 99 -c 8192 --jinja > /tmp/llm4_$tag.log 2>&1 &
  local ok=0
  for i in $(seq 1 30); do curl -s --max-time 5 http://127.0.0.1:8101/v1/models >/dev/null 2>&1 && ok=1 && break; sleep 10; done
  if [ $ok = 1 ]; then
    MIMO_KEY=$MIMO_KEY /home/exuber/CODE/CORE/pythonProject1/AUTORESEARCH/text-to-cad/.venv/bin/python \
      tools/run_local_bench.py --endpoint http://127.0.0.1:8101/v1 --served-model $tag \
      --designer $tag-zeroshot --judges mimo-v2.6-pro --n 3 --max-tokens 4000 >> runs/bench4_$tag.log 2>&1
    echo "[b4] $(date +%H:%M) $tag done: $(grep -a 'profit mean' runs/bench4_$tag.log | tail -1 | sed 's/.*mean=//')" >> $LOG
  else
    echo "[b4] $tag LLAMA FAILED" >> $LOG
  fi
  pkill -f 'llama-server' || true; sleep 8; rm -rf $dir
}

retry_trust spark-x2.5-4b   XHToken/Spark-X2.5-4B
retry_trust phi4-mini-flash microsoft/Phi-4-mini-flash-reasoning
retry_trust k2-horizon-7b  IFM/K2-Horizon-7B
retry_trust loopcoder-v2    Multilingual-Multimodal-NLP/LoopCoder-V2
retry_trust clm-v0.1-8b     Contrastive-LM/CLM-v0.1-8B
retry_trust diffucoder-inst apple/DiffuCoder-7B-Instruct
ouro_gguf ouro-2.6b          BrandeisPatrick/Ouro-2.6B-GGUF Ouro-2.6B-Q4_K_M.gguf
ouro_gguf ouro-2.6b-thinking BrandeisPatrick/Ouro-2.6B-Thinking-GGUF Ouro-2.6B-Thinking-Q4_K_M.gguf
echo "[b4] $(date +%H:%M) ALL DONE" >> $LOG
