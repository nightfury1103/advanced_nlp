# No-GPU OCR First-Pass Benchmark

This folder benchmarks the OCR options that do not require a local GPU.

## Input Pages

The same 8 selected pages are used across models:

```text
5, 20, 44, 52, 80, 160, 240, 320
```

Rendered PNG inputs:

```text
benchmarks/no_gpu_first_pass/input_images/page_*.png
```

Render command:

```bash
uv run --with pypdfium2 --with pillow \
  python benchmarks/no_gpu_first_pass/render_pages.py
```

## Umi-OCR CPU Baseline

This machine does not have the Umi-OCR desktop app or a Umi-OCR CLI binary installed. For a local no-GPU baseline, this benchmark uses RapidOCR ONNX Runtime on CPU, which is in the OCR engine family supported by Umi-OCR.

Run:

```bash
uv run --with rapidocr_onnxruntime --with pillow \
  python benchmarks/no_gpu_first_pass/run_umi_cpu_rapidocr.py
```

Output:

```text
benchmarks/no_gpu_first_pass/output/umi_cpu/
```

## KanDianGuJi Hosted API

Requires account credentials. Export them before running:

```bash
export KANDIANGUJI_TOKEN="..."
export KANDIANGUJI_EMAIL="..."

uv run --with requests \
  python benchmarks/no_gpu_first_pass/run_kandianguji_api.py
```

Output:

```text
benchmarks/no_gpu_first_pass/output/kandianguji/
```

For Modal or another server network, use the packaged retry wrapper:

```bash
export KANDIANGUJI_TOKEN="..."
export KANDIANGUJI_EMAIL="..."
KANDIANGUJI_PAGES=44,80,160,240,320 \
KANDIANGUJI_MAX_ATTEMPTS=5 \
KANDIANGUJI_CURL_MAX_TIME=300 \
KANDIANGUJI_RETRY_SLEEP_SECONDS=20 \
bash benchmarks/no_gpu_first_pass/run_kandianguji_modal.sh
```

The wrapper records successful pages, writes `page_XXX.error.txt` for failed pages,
and scores whatever page outputs are available.

## GJ.cool Hosted API

Requires account credentials and the account-specific base URL from the GJ.cool documentation:

```bash
export GJCOOL_BASE_URL="..."
export GJCOOL_ACCESS_TOKEN="..."

uv run --with requests \
  python benchmarks/no_gpu_first_pass/run_gjcool_api.py
```

Output:

```text
benchmarks/no_gpu_first_pass/output/gjcool/
```

## olmOCR

Deferred to the GPU environment. See:

```text
benchmarks/olmocr_first_pass/
```
