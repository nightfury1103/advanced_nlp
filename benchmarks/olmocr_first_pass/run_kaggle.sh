#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/../.." && pwd)"
cd "$repo_root"

model="${OLMOCR_MODEL:-allenai/olmOCR-2-7B-1025-FP8}"
run_id="${OLMOCR_RUN_ID:-kaggle-$(date -u +%Y%m%dT%H%M%SZ)}"
working_root="${KAGGLE_WORKING_ROOT:-/kaggle/working}"
venv_dir="${OLMOCR_VENV:-${working_root}/olmocr-venv}"
hf_home="${HF_HOME:-${working_root}/hf-cache}"
uv_dir="${UV_INSTALL_DIR:-${working_root}/uv-bin}"
uv_bin="${uv_dir}/uv"
run_root="benchmarks/olmocr_first_pass/output/runs/${run_id}"
archive="${working_root}/olmocr-${run_id}.zip"

log() {
  printf '\n==> %s\n' "$*"
}

fail() {
  printf '\nERROR: %s\n' "$*" >&2
  exit 1
}

command -v nvidia-smi >/dev/null 2>&1 || fail "No NVIDIA GPU found. Enable a GPU accelerator in Kaggle."

log "GPU information"
nvidia-smi

gpu_count="$(nvidia-smi --query-gpu=name --format=csv,noheader | wc -l | tr -d ' ')"
gpu_names="$(nvidia-smi --query-gpu=name --format=csv,noheader | paste -sd ',' -)"

if [[ "$gpu_names" == *"P100"* && "${ALLOW_UNSUPPORTED_GPU:-0}" != "1" ]]; then
  fail "P100 is not a suitable default for the FP8 olmOCR stack. Start a Kaggle session with L4/A100/T4x2, or set ALLOW_UNSUPPORTED_GPU=1 to attempt it anyway."
fi

if [[ -n "${OLMOCR_TP_SIZE:-}" ]]; then
  tp_size="$OLMOCR_TP_SIZE"
elif [[ "$gpu_names" == *"T4"* && "$gpu_count" -ge 2 ]]; then
  tp_size=2
else
  tp_size=1
fi

log "Configuration"
printf 'Repository: %s\n' "$repo_root"
printf 'Model: %s\n' "$model"
printf 'Run ID: %s\n' "$run_id"
printf 'GPU count: %s\n' "$gpu_count"
printf 'Tensor parallel size: %s\n' "$tp_size"
printf 'Hugging Face cache: %s\n' "$hf_home"

available_kb="$(df -Pk "$working_root" | awk 'NR==2 {print $4}')"
available_gb="$((available_kb / 1024 / 1024))"
printf 'Free disk: %s GB\n' "$available_gb"
if [[ "$available_gb" -lt 30 ]]; then
  low_disk_mode=1
  printf 'WARNING: only %sGB is free; enabling low-disk mode.\n' "$available_gb" >&2
  printf 'Low-disk mode reuses the Kaggle Python environment instead of duplicating GPU packages in a venv.\n' >&2
else
  low_disk_mode=0
fi

log "Installing system dependencies"
if [[ "${KAGGLE_SKIP_APT:-0}" != "1" ]]; then
  if [[ "$(id -u)" -eq 0 ]]; then
    apt-get update -qq
    apt-get install -y poppler-utils fonts-dejavu-core time zip curl
  elif command -v sudo >/dev/null 2>&1; then
    sudo apt-get update -qq
    sudo apt-get install -y poppler-utils fonts-dejavu-core time zip curl
  else
    fail "Root or sudo access is required to install Poppler."
  fi
fi
command -v pdftoppm >/dev/null 2>&1 || fail "pdftoppm is not installed."
command -v /usr/bin/time >/dev/null 2>&1 || fail "/usr/bin/time is not installed."

apt-get clean 2>/dev/null || true
python3 -m pip cache purge >/dev/null 2>&1 || true

log "Preparing Python environment"
if [[ "$low_disk_mode" == "1" ]]; then
  if [[ -d "$venv_dir" ]]; then
    log "Removing incomplete dedicated venv to recover disk space"
    rm -rf "$venv_dir"
  fi
  python_bin="$(command -v python3)"
  PIP_NO_CACHE_DIR=1 "$python_bin" -m pip install --upgrade pip
  PIP_NO_CACHE_DIR=1 "$python_bin" -m pip install "olmocr[gpu]" \
    --extra-index-url https://download.pytorch.org/whl/cu128
  python_scripts_dir="$("$python_bin" -c 'import sysconfig; print(sysconfig.get_path("scripts"))')"
  olmocr_bin="${python_scripts_dir}/olmocr"
else
  if [[ ! -x "$uv_bin" ]]; then
    mkdir -p "$uv_dir"
    curl -LsSf https://astral.sh/uv/install.sh | env UV_UNMANAGED_INSTALL="$uv_dir" sh
  fi

  if [[ ! -x "${venv_dir}/bin/python" || ! -x "${venv_dir}/bin/pip" ]]; then
    UV_VENV_CLEAR=1 "$uv_bin" venv --python 3.11 --seed "$venv_dir"
  fi

  "${venv_dir}/bin/pip" install --no-cache-dir --upgrade pip
  if [[ ! -x "${venv_dir}/bin/olmocr" || "${OLMOCR_FORCE_INSTALL:-0}" == "1" ]]; then
    "${venv_dir}/bin/pip" install --no-cache-dir "olmocr[gpu]" \
      --extra-index-url https://download.pytorch.org/whl/cu128
  fi
  python_bin="${venv_dir}/bin/python"
  olmocr_bin="${venv_dir}/bin/olmocr"
fi

[[ -x "$olmocr_bin" ]] || fail "olmocr executable was not installed: $olmocr_bin"

log "Verifying CUDA runtime"
"$python_bin" - <<'PY'
import torch

print("PyTorch:", torch.__version__)
print("CUDA available:", torch.cuda.is_available())
if not torch.cuda.is_available():
    raise SystemExit("CUDA is not available inside the olmOCR environment")
print("GPU count:", torch.cuda.device_count())
for index in range(torch.cuda.device_count()):
    print(index, torch.cuda.get_device_name(index), torch.cuda.get_device_capability(index))
PY

log "Pre-downloading model outside benchmark timing"
mkdir -p "$hf_home"
HF_HOME="$hf_home" "$python_bin" - <<PY
from huggingface_hub import snapshot_download

snapshot_download("${model}")
PY

log "Running five-page olmOCR benchmark"
HF_HOME="$hf_home" \
OLMOCR_BIN="$olmocr_bin" \
OLMOCR_MODEL="$model" \
OLMOCR_TP_SIZE="$tp_size" \
OLMOCR_RUN_ID="$run_id" \
  bash benchmarks/olmocr_first_pass/run_olmocr_gpu.sh

[[ -d "${run_root}/text" ]] || fail "Expected text output directory was not created: ${run_root}/text"

log "Scoring strict and aligned CER"
python3 benchmarks/no_gpu_first_pass/score_ocr.py \
  --model-dir "${run_root}/text" \
  --out "${run_root}/text/cer_scores.json"

log "Creating result archive"
(
  cd "$(dirname "$run_root")"
  zip -qr "$archive" "$(basename "$run_root")"
)

log "Completed"
printf 'Run directory: %s/%s\n' "$repo_root" "$run_root"
printf 'Download this Kaggle file: %s\n' "$archive"
printf 'Score file: %s/%s/text/cer_scores.json\n' "$repo_root" "$run_root"
