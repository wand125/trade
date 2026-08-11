#!/usr/bin/env bash
set -euo pipefail

if (($# == 0)); then
  echo "usage: run_low_priority_worker.sh COMMAND [ARG ...]" >&2
  exit 64
fi

worker_threads="${TRADE_WORKER_THREADS:-8}"
minimum_available_gb="${TRADE_MIN_AVAILABLE_MEMORY_GB:-16}"
maximum_load="${TRADE_MAX_LOAD_1M:-8}"
enable_gpu="${TRADE_ENABLE_GPU:-0}"
require_idle_gpu="${TRADE_REQUIRE_IDLE_GPU:-0}"
gpu_exclusive_window="${TRADE_GPU_EXCLUSIVE_WINDOW:-0}"
maximum_gpu_used_mb="${TRADE_MAX_GPU_USED_MB:-2048}"
maximum_gpu_utilization="${TRADE_MAX_GPU_UTILIZATION:-10}"
worker_lock="${TRADE_WORKER_LOCK:-/tmp/trade-next-bar-worker.lock}"
meminfo_path="${TRADE_MEMINFO_PATH:-/proc/meminfo}"
loadavg_path="${TRADE_LOADAVG_PATH:-/proc/loadavg}"

for value in \
  "$worker_threads" \
  "$minimum_available_gb" \
  "$maximum_gpu_used_mb" \
  "$maximum_gpu_utilization"; do
  if ! [[ "$value" =~ ^[0-9]+$ ]]; then
    echo "worker resource limits must be non-negative integers" >&2
    exit 64
  fi
done
if ((worker_threads == 0 || minimum_available_gb == 0)); then
  echo "thread and available-memory limits must be positive" >&2
  exit 64
fi
for value in "$enable_gpu" "$require_idle_gpu" "$gpu_exclusive_window"; do
  if [[ "$value" != "0" && "$value" != "1" ]]; then
    echo "GPU worker switches must be 0 or 1" >&2
    exit 64
  fi
done

if [[ "$enable_gpu" == "1" ]]; then
  if [[ "$require_idle_gpu" != "1" ]]; then
    echo "GPU worker requires TRADE_REQUIRE_IDLE_GPU=1" >&2
    exit 64
  fi
  if [[ "$gpu_exclusive_window" != "1" ]]; then
    echo "GPU worker requires a confirmed exclusive GPU window" >&2
    exit 75
  fi
elif [[ "$require_idle_gpu" == "1" ]]; then
  echo "TRADE_REQUIRE_IDLE_GPU=1 also requires TRADE_ENABLE_GPU=1" >&2
  exit 64
else
  # CPU research must not acquire the shared image-generation GPU implicitly.
  export CUDA_VISIBLE_DEVICES=""
fi

available_kb="$(awk '/^MemAvailable:/ {print $2}' "$meminfo_path")"
minimum_available_kb="$((minimum_available_gb * 1024 * 1024))"
if ((available_kb < minimum_available_kb)); then
  echo "trade worker deferred: available memory is below ${minimum_available_gb} GiB" >&2
  exit 75
fi

load_1m="$(awk '{print $1}' "$loadavg_path")"
if ! awk -v current="$load_1m" -v maximum="$maximum_load" \
  'BEGIN { exit !(current <= maximum) }'; then
  echo "trade worker deferred: one-minute load ${load_1m} exceeds ${maximum_load}" >&2
  exit 75
fi

if [[ "$require_idle_gpu" == "1" ]]; then
  nvidia_smi="$(command -v nvidia-smi || true)"
  if [[ -z "$nvidia_smi" && -x /usr/lib/wsl/lib/nvidia-smi ]]; then
    nvidia_smi=/usr/lib/wsl/lib/nvidia-smi
  fi
  if [[ -z "$nvidia_smi" ]]; then
    echo "trade worker deferred: nvidia-smi is unavailable" >&2
    exit 75
  fi
  gpu_state="$($nvidia_smi \
    --query-gpu=memory.used,utilization.gpu \
    --format=csv,noheader,nounits | head -n 1)"
  gpu_used_mb="${gpu_state%%,*}"
  gpu_utilization="${gpu_state##*,}"
  gpu_used_mb="${gpu_used_mb//[[:space:]]/}"
  gpu_utilization="${gpu_utilization//[[:space:]]/}"
  if ((
    gpu_used_mb > maximum_gpu_used_mb
    || gpu_utilization > maximum_gpu_utilization
  )); then
    echo "trade worker deferred: GPU is already in use" >&2
    exit 75
  fi
fi

export OMP_NUM_THREADS="$worker_threads"
export OPENBLAS_NUM_THREADS="$worker_threads"
export MKL_NUM_THREADS="$worker_threads"
export NUMEXPR_NUM_THREADS="$worker_threads"
export VECLIB_MAXIMUM_THREADS="$worker_threads"
export MALLOC_ARENA_MAX="${MALLOC_ARENA_MAX:-2}"

priority=(nice -n "${TRADE_NICE_LEVEL:-10}")
if command -v ionice >/dev/null 2>&1; then
  priority+=(ionice -c 2 -n "${TRADE_IONICE_LEVEL:-7}")
fi

exec flock -n "$worker_lock" "${priority[@]}" "$@"
