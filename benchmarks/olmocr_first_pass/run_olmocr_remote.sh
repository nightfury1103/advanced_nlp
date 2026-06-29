#!/usr/bin/env bash
set -euo pipefail

: "${OLMOCR_SERVER:?Set OLMOCR_SERVER}"
: "${OLMOCR_API_KEY:?Set OLMOCR_API_KEY}"
: "${OLMOCR_MODEL:?Set OLMOCR_MODEL}"

workspace="benchmarks/olmocr_first_pass/output/workspace"
timing="benchmarks/olmocr_first_pass/output/olmocr_timing.txt"
mkdir -p "$workspace" "$(dirname "$timing")"

/usr/bin/time -p -o "$timing" \
  olmocr "$workspace" \
    --server "$OLMOCR_SERVER" \
    --api_key "$OLMOCR_API_KEY" \
    --model "$OLMOCR_MODEL" \
    --markdown \
    --workers 1 \
    --max_concurrent_requests 1 \
    --pages_per_group 1 \
    --target_longest_image_dim 1288 \
    --pdfs \
      benchmarks/olmocr_first_pass/input_pages/page_044.pdf \
      benchmarks/olmocr_first_pass/input_pages/page_080.pdf \
      benchmarks/olmocr_first_pass/input_pages/page_160.pdf \
      benchmarks/olmocr_first_pass/input_pages/page_240.pdf \
      benchmarks/olmocr_first_pass/input_pages/page_320.pdf
