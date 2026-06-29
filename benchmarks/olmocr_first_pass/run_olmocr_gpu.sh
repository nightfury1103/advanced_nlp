#!/usr/bin/env bash
set -euo pipefail

olmocr_bin="${OLMOCR_BIN:-olmocr}"
python_bin="${OLMOCR_PYTHON:-python3}"
launcher="${OLMOCR_LAUNCHER:-benchmarks/olmocr_first_pass/olmocr_launcher.py}"
model="${OLMOCR_MODEL:-allenai/olmOCR-2-7B-1025-FP8}"
tp_size="${OLMOCR_TP_SIZE:-1}"
run_id="${OLMOCR_RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)}"
run_root="benchmarks/olmocr_first_pass/output/runs/${run_id}"
workspace="${run_root}/workspace"
timing="${run_root}/olmocr_timing.txt"

mkdir -p "$workspace"

if command -v nvidia-smi >/dev/null 2>&1; then
  nvidia-smi > "${run_root}/gpu_info.txt"
fi

printf '%s\n' "$model" > "${run_root}/model.txt"

if [[ -f "$launcher" ]]; then
  olmocr_command=("$python_bin" "$launcher")
else
  olmocr_command=("$olmocr_bin")
fi

/usr/bin/time -p -o "$timing" \
  "${olmocr_command[@]}" "$workspace" \
    --model "$model" \
    --markdown \
    --workers 1 \
    --max_concurrent_requests 1 \
    --pages_per_group 1 \
    --target_longest_image_dim 1288 \
    --gpu-memory-utilization 0.80 \
    --max_model_len 16384 \
    --tensor-parallel-size "$tp_size" \
    --pdfs \
      benchmarks/olmocr_first_pass/input_pages/page_044.pdf \
      benchmarks/olmocr_first_pass/input_pages/page_080.pdf \
      benchmarks/olmocr_first_pass/input_pages/page_160.pdf \
      benchmarks/olmocr_first_pass/input_pages/page_240.pdf \
      benchmarks/olmocr_first_pass/input_pages/page_320.pdf

python3 benchmarks/olmocr_first_pass/prepare_olmocr_results.py "$run_root"

printf 'olmOCR run complete: %s\n' "$run_root"
