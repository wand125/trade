#!/usr/bin/env bash
set -euo pipefail

if (($# == 0)); then
  echo "usage: run_low_priority_worker.sh COMMAND [ARG ...]" >&2
  exit 64
fi

worker_threads="${TRADE_WORKER_THREADS:-8}"
minimum_available_gb="${TRADE_MIN_AVAILABLE_MEMORY_GB:-8}"
maximum_load="${TRADE_MAX_LOAD_1M:-12}"
require_idle_gpu="${TRADE_REQUIRE_IDLE_GPU:-0}"
maximum_gpu_used_mb="${TRADE_MAX_GPU_USED_MB:-12288}"
maximum_gpu_utilization="${TRADE_MAX_GPU_UTILIZATION:-25}"
worker_lock="${TRADE_WORKER_LOCK:-/tmp/trade-next-bar-worker.lock}"

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

available_kb="$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)"
minimum_available_kb="$((minimum_available_gb * 1024 * 1024))"
if ((available_kb < minimum_available_kb)); then
  echo "trade worker deferred: available memory is below ${minimum_available_gb} GiB" >&2
  exit 75
fi

load_1m="$(awk '{print $1}' /proc/loadavg)"
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
