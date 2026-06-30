#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root"

if [[ "${KANDIANGUJI_SKIP_APT:-0}" != "1" ]] && command -v apt-get >/dev/null 2>&1; then
  apt-get update -y
  apt-get install -y curl ca-certificates
fi

mkdir -p benchmarks/no_gpu_first_pass/output/kandianguji

python3 benchmarks/no_gpu_first_pass/run_kandianguji_api.py

python3 benchmarks/no_gpu_first_pass/score_ocr.py \
  --model-dir benchmarks/no_gpu_first_pass/output/kandianguji \
  --out benchmarks/no_gpu_first_pass/output/kandianguji/cer_scores.json

printf 'KanDianGuJi run complete: benchmarks/no_gpu_first_pass/output/kandianguji\n'
