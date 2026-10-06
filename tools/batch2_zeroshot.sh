#!/usr/bin/env bash
# Batch 2: 17 zero-shot Money Bench controls (user-requested models).
# Per model: download -> vLLM serve (optional --trust-remote-code) -> bench n=3 -> cleanup.
set -u
cd /home/exuber/CODE/CORE/pythonProject1/AUTORESEARCH/MechanogenesisBench-upstream
export MIMO_KEY="${MIMO_KEY:?set MIMO_KEY env var}"
PY=/home/exuber/.venvs/dd_qwen9b_fla_20260910/bin/python
VLLM=/home/exuber/.venvs/vllm_serve/bin/python
LOG=runs/batch2_zeroshot.log
MODELS_DIR=/home/exuber/models

run_one () {  # tag repo trust(0/1)
  local tag=$1 repo=$2 trust=$3 dir=$MODELS_DIR/zs-$1
  echo "[b2] $(date +%H:%M) === $tag ===" >> $LOG
  for attempt in 1 2 3; do
    $PY -c "
from huggingface_hub import snapshot_download
snapshot_download('$repo', local_dir='$dir')
print('DL-OK')" > /tmp/dl2_$tag.log 2>&1 && break
    echo "[b2] $tag dl attempt $attempt failed; retrying" >> $LOG; sleep 30
  done
  grep -q DL-OK /tmp/dl2_$tag.log || { echo "[b2] $tag DOWNLOAD FAILED" >> $LOG; return 1; }
  local TR=(); [ "$trust" = "1" ] && TR=(--trust-remote-code)
  nohup $VLLM -m vllm.entrypoints.openai.api_server --model $dir --served-model-name $tag \
    --port 8100 --max-model-len 4096 --gpu-memory-utilization 0.93 --enforce-eager \
    --max-num-seqs 2 --max-num-batched-tokens 4096 "${TR[@]}" > /tmp/vllm2_$tag.log 2>&1 &
  for i in $(seq 1 45); do curl -s --max-time 5 http://127.0.0.1:8100/v1/models | grep -q '"'$tag'"' && break; sleep 10; done
  curl -s --max-time 5 http://127.0.0.1:8100/v1/models | grep -q '"'$tag'"' || {
    echo "[b2] $tag SERVER FAILED" >> $LOG; pkill -f 'vllm.entrypoints' || true; sleep 10;
    rm -rf $dir; $PY -c "
from huggingface_hub import scan_cache_dir
for r in scan_cache_dir().repos:
    if r.size_on_disk > 4e9: r.delete_repo()" 2>/dev/null; return 1; }
  MIMO_KEY=$MIMO_KEY /home/exuber/CODE/CORE/pythonProject1/AUTORESEARCH/text-to-cad/.venv/bin/python \
    tools/run_local_bench.py --endpoint http://127.0.0.1:8100/v1 --served-model $tag \
    --designer $tag-zeroshot --judges mimo-v2.6-pro --n 3 --max-tokens 3000 \
    >> runs/bench2_$tag.log 2>&1
  echo "[b2] $(date +%H:%M) $tag done: $(grep -a 'profit mean' runs/bench2_$tag.log | tail -1 | sed 's/.*mean=//')" >> $LOG
  pkill -f 'vllm.entrypoints' || true; sleep 10
  rm -rf $dir
  $PY -c "
from huggingface_hub import scan_cache_dir
for r in scan_cache_dir().repos:
    if r.size_on_disk > 4e9: r.delete_repo()" 2>/dev/null
}

# instruct-capable first, base/coder last
run_one mistral-7b-v0.3        mistralai/Mistral-7B-Instruct-v0.3 0
run_one glm-4-9b-chat          zai-org/glm-4-9b-chat-1m           1
run_one internlm3-8b-instruct  internlm/internlm3-8b-instruct     1
run_one minicpm5-2b            openbmb/MiniCPM5-2B                1
run_one spark-x2.5-4b          XHToken/Spark-X2.5-4B              0
run_one vibethinker-3b         WeiboAI/VibeThinker-3B             0
run_one phi4-mini-flash        microsoft/Phi-4-mini-flash-reasoning 0
run_one k2-horizon-7b          IFM/K2-Horizon-7B                  0
run_one loopcoder-v2           Multilingual-Multimodal-NLP/LoopCoder-V2 1
run_one clm-v0.1-8b            Contrastive-LM/CLM-v0.1-8B         0
run_one ling-3.0-tiny          inclusionAI/Ling-3.0-tiny          1
run_one seed-coder-8b-inst     ByteDance-Seed/Seed-Coder-8B-Instruct 0
run_one seed-coder-8b-reas     ByteDance-Seed/Seed-Coder-8B-Reasoning 0
run_one seed-coder-8b-base     ByteDance-Seed/Seed-Coder-8B-Base  0
run_one diffucoder-inst        apple/DiffuCoder-7B-Instruct       0
run_one diffucoder-cpgrpo      apple/DiffuCoder-7B-cpGRPO         0
run_one diffucoder-base        apple/DiffuCoder-7B-Base           0
echo "[b2] $(date +%H:%M) ALL DONE" >> $LOG
