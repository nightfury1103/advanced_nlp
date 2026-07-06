#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${OLMOCR_BIN:-}" && -x "olmocr-venv/bin/olmocr" ]]; then
  olmocr_bin="olmocr-venv/bin/olmocr"
else
  olmocr_bin="${OLMOCR_BIN:-olmocr}"
fi

if [[ -z "${OLMOCR_PYTHON:-}" && -x "olmocr-venv/bin/python" ]]; then
  python_bin="olmocr-venv/bin/python"
else
  python_bin="${OLMOCR_PYTHON:-python3}"
fi
launcher="${OLMOCR_LAUNCHER:-benchmarks/olmocr_first_pass/olmocr_launcher.py}"
model="${OLMOCR_MODEL:-allenai/olmOCR-2-7B-1025-FP8}"
tp_size="${OLMOCR_TP_SIZE:-1}"
run_id="${OLMOCR_RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)}"
preflight_only="${OLMOCR_PREFLIGHT_ONLY:-0}"
run_root="benchmarks/olmocr_first_pass/output/runs/${run_id}"
workspace="${run_root}/workspace"
timing="${run_root}/olmocr_timing.txt"

mkdir -p "$workspace"

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

resolve_executable() {
  local label="$1"
  local executable="$2"

  if [[ "$executable" == */* ]]; then
    if [[ ! -x "$executable" ]]; then
      fail "${label} does not exist or is not executable: ${executable}. If this is a fresh Modal session, run run_kaggle.sh first so the venv is created, or set ${label} to the correct executable path."
    fi
    printf '%s\n' "$executable"
    return
  fi

  command -v "$executable" >/dev/null 2>&1 || fail "${label} executable not found in PATH: ${executable}"
  command -v "$executable"
}

olmocr_bin="$(resolve_executable OLMOCR_BIN "$olmocr_bin")"
python_bin="$(resolve_executable OLMOCR_PYTHON "$python_bin")"

if command -v nvidia-smi >/dev/null 2>&1; then
  nvidia-smi > "${run_root}/gpu_info.txt"
fi

printf '%s\n' "$model" > "${run_root}/model.txt"

if [[ "$olmocr_bin" == */* ]]; then
  olmocr_bin_dir="$(cd "$(dirname "$olmocr_bin")" && pwd)"
  export PATH="$olmocr_bin_dir:$PATH"
fi

if ! command -v vllm >/dev/null 2>&1; then
  printf 'ERROR: vllm executable not found in PATH. Install olmocr[gpu] or set OLMOCR_BIN to the venv/bin/olmocr path.\n' >&2
  exit 1
fi

cuda_link_dir="${run_root}/cuda-link"
mkdir -p "$cuda_link_dir"
ldconfig_output=""
if command -v ldconfig >/dev/null 2>&1; then
  ldconfig_output="$(ldconfig -p 2>/dev/null || true)"
fi

if ! grep -q 'libcuda\.so ' <<<"$ldconfig_output"; then
  libcuda_path="$(awk '/libcuda\.so\.1 / {print $NF; exit}' <<<"$ldconfig_output")"
  if [[ -n "${libcuda_path:-}" && -e "$libcuda_path" ]]; then
    ln -sf "$libcuda_path" "${cuda_link_dir}/libcuda.so"
    export LIBRARY_PATH="${cuda_link_dir}${LIBRARY_PATH:+:${LIBRARY_PATH}}"
    export LD_LIBRARY_PATH="${cuda_link_dir}${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"
  fi
fi

cat > "${cuda_link_dir}/cuda_link_check.c" <<'EOF'
#include <Python.h>

static struct PyModuleDef cuda_link_check_module = {
  PyModuleDef_HEAD_INIT,
  "cuda_link_check",
  NULL,
  -1,
  NULL
};

PyMODINIT_FUNC PyInit_cuda_link_check(void) {
  return PyModule_Create(&cuda_link_check_module);
}
EOF

python_include="$("$python_bin" -c 'import sysconfig; print(sysconfig.get_path("include") or "")')"
if ! gcc "${cuda_link_dir}/cuda_link_check.c" -O3 -shared -fPIC -Wno-psabi -o "${cuda_link_dir}/cuda_link_check.so" -L"$cuda_link_dir" ${python_include:+-I"$python_include"} -lcuda; then
  printf 'ERROR: gcc cannot link against libcuda. Check that libcuda.so.1 exists and libcuda.so is available through LIBRARY_PATH.\n' >&2
  exit 1
fi

if [[ "$preflight_only" == "1" ]]; then
  printf 'olmOCR GPU preflight complete: vllm and libcuda linker checks passed.\n'
  exit 0
fi

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
