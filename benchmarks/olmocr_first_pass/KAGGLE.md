# Running the olmOCR Benchmark on Kaggle

## One-command Run

After cloning the repository and enabling GPU + Internet, run:

```bash
!cd /kaggle/working/advanced_nlp && \
  bash benchmarks/olmocr_first_pass/run_kaggle.sh
```

The script performs the installation, creates a managed Python 3.11 environment with `uv`, pre-downloads the model, runs the GPU benchmark, calculates CER, and packages the results. It also repairs an incomplete virtual environment left by a failed earlier run.

## 1. Create the Notebook

Enable:

- Accelerator: GPU
- Internet: On
- Persistence: optional, but useful because the model download is large

Copy or upload this repository into writable storage under `/kaggle/working`. Do not run from `/kaggle/input`, which is read-only.

```python
%cd /kaggle/working/XLNNTN
```

## 2. Inspect GPU and Disk

```bash
!nvidia-smi
!df -h /kaggle/working
```

Recommended: L4/A100 or another recent NVIDIA GPU with at least 12GB VRAM. The official project lists RTX 4090, L40S, A100, and H100 as tested. Kaggle T4/P100 sessions are less certain:

- L4/A100: use `OLMOCR_TP_SIZE=1`.
- T4x2: try `OLMOCR_TP_SIZE=2`.
- Single T4 or P100: likely to encounter FP8, CUDA, or memory problems; use a remote endpoint if that happens.

## 3. Install System Dependencies

Kaggle notebooks normally run as root, so do not use `sudo`:

```bash
!apt-get update -qq
!apt-get install -y poppler-utils fonts-dejavu-core time
!pdftoppm -v
```

## 4. Create a Clean Python Environment

The official project recommends Python 3.11 and a clean environment.

```bash
!python3 -m venv /kaggle/working/olmocr-venv
!/kaggle/working/olmocr-venv/bin/pip install --upgrade pip
!/kaggle/working/olmocr-venv/bin/pip install "olmocr[gpu]" --extra-index-url https://download.pytorch.org/whl/cu128
```

The optional FlashInfer wheel may improve speed, but leave it out initially. A simpler first run is easier to debug on Kaggle.

## 5. Verify Runtime Before Downloading the Model

```bash
!/kaggle/working/olmocr-venv/bin/python -c "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0)); print(torch.cuda.get_device_capability(0))"
!/kaggle/working/olmocr-venv/bin/olmocr --help
```

Stop if `torch.cuda.is_available()` is `False`.

## 6. Pre-download the Model

This keeps model download time out of the benchmark timing.

```bash
!HF_HOME=/kaggle/working/hf-cache /kaggle/working/olmocr-venv/bin/python -c "from huggingface_hub import snapshot_download; snapshot_download('allenai/olmOCR-2-7B-1025-FP8')"
```

## 7. Run the Five-page Benchmark

For one suitable GPU:

```bash
!HF_HOME=/kaggle/working/hf-cache \
  OLMOCR_BIN=/kaggle/working/olmocr-venv/bin/olmocr \
  OLMOCR_MODEL=allenai/olmOCR-2-7B-1025-FP8 \
  OLMOCR_TP_SIZE=1 \
  OLMOCR_RUN_ID=kaggle-run-1 \
  bash benchmarks/olmocr_first_pass/run_olmocr_gpu.sh
```

For Kaggle T4x2, change only:

```text
OLMOCR_TP_SIZE=2
```

Do not reuse the same `OLMOCR_RUN_ID`; olmOCR workspaces remember completed documents and a reused workspace can produce misleading timing.

## 8. Score the Output

```bash
!python3 benchmarks/no_gpu_first_pass/score_ocr.py \
  --model-dir benchmarks/olmocr_first_pass/output/runs/kaggle-run-1/text \
  --out benchmarks/olmocr_first_pass/output/runs/kaggle-run-1/text/cer_scores.json
```

## 9. Download Results

Download this directory from Kaggle:

```text
benchmarks/olmocr_first_pass/output/runs/kaggle-run-1/
```

It contains the OCR text, strict/aligned CER, timing, model name, and GPU information needed for the final comparison.
