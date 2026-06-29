# Advanced NLP: OCR Benchmark for Historical Chinese Books

This repository benchmarks OCR systems on vertically written historical Chinese text from a scanned Vietnamese collection. It focuses on reproducible model comparison rather than a single OCR demo.

The benchmark currently covers:

- Umi-OCR-style local CPU inference through RapidOCR ONNX Runtime
- GJ.cool hosted ancient-book OCR
- KanDianGuJi hosted OCR integration and transport diagnostics
- olmOCR GPU preparation for Kaggle or another NVIDIA environment

## Current Results

The clean evaluation set contains PDF pages `44`, `80`, `160`, `240`, and `320`. All models are compared against the same ChatGPT-assisted OCR reference.

| Model | Pages | Strict weighted CER | Aligned weighted CER | Total time | Average/page | Status |
|---|---:|---:|---:|---:|---:|---|
| Umi/RapidOCR CPU | 5 | 0.8691 | 0.8445 | 6.952s | 1.390s | Completed |
| GJ.cool | 5 | 1.6400 | 0.3582 | 223.942s | 44.788s | Completed |
| KanDianGuJi | 0 | - | - | - | - | API transport unstable from the development network |
| olmOCR | 0 | - | - | - | - | Kaggle/GPU package ready |

Strict CER penalizes every additional OCR character. Aligned CER compares the reference against the best matching contiguous span in the OCR output. Both are reported because some ChatGPT references appear shorter than the complete page text returned by GJ.cool.

Detailed results: [`benchmarks/no_gpu_first_pass/clean_set_benchmark_report.md`](benchmarks/no_gpu_first_pass/clean_set_benchmark_report.md)

## Benchmark Design

### Clean set

```text
44, 80, 160, 240, 320
```

These pages were selected because their text is sufficiently clear for a stable ChatGPT-assisted reference. Page `40` was rejected because one PDF rendering path produced an effectively blank image.

### Stress set

```text
5, 20, 52
```

These handwritten, degraded, or complex pages are retained for future stress testing. They are not included in the current aggregate quality score.

### Reference

The files under `benchmarks/no_gpu_first_pass/ground_truth/` are a **silver reference** created from ChatGPT-assisted OCR. They are not human-verified diplomatic transcriptions. This limitation matters when interpreting CER.

### Metrics

- **Strict CER**: Levenshtein edit distance divided by reference character count.
- **Aligned CER**: edit distance between the reference and the best matching contiguous OCR span.
- **Inference time**: end-to-end wall time as observed by the local runner or hosted API call.
- **OCR/reference ratio**: normalized OCR output length divided by normalized reference length.
- **Throughput**: normalized OCR characters per second.

Whitespace and common punctuation are removed before CER calculation. Traditional and variant Chinese characters are not normalized because variant handling is part of the OCR task.

## Repository Structure

```text
.
├── sample.pdf
├── artifacts/
│   ├── result/                         # ChatGPT-assisted reference source
│   └── page_samples/                   # Contact sheets and page previews
└── benchmarks/
    ├── no_gpu_first_pass/
    │   ├── input_images/               # Full-resolution rendered pages
    │   ├── input_images_gjcool_1800/   # GJ.cool API inputs
    │   ├── input_images_kandianguji_800/
    │   ├── ground_truth/
    │   ├── output/
    │   │   ├── umi_cpu/
    │   │   ├── gjcool/
    │   │   └── kandianguji/
    │   ├── render_pages.py
    │   ├── run_umi_cpu_rapidocr.py
    │   ├── run_gjcool_api.py
    │   ├── run_kandianguji_api.py
    │   └── score_ocr.py
    └── olmocr_first_pass/
        ├── KAGGLE.md
        ├── input_pages/
        ├── olmocr_clean_5_pages.pdf
        ├── run_olmocr_gpu.sh
        └── prepare_olmocr_results.py
```

## Quick Start

Python 3.9 or newer is sufficient for the CPU runners and scoring scripts. Commands use [`uv`](https://docs.astral.sh/uv/) to keep model dependencies isolated.

### Render benchmark pages

```bash
uv run --with pypdfium2 --with pillow \
  python benchmarks/no_gpu_first_pass/render_pages.py
```

### Run the CPU baseline

```bash
uv run --with rapidocr_onnxruntime --with pillow \
  python benchmarks/no_gpu_first_pass/run_umi_cpu_rapidocr.py
```

### Score an OCR output directory

```bash
python3 benchmarks/no_gpu_first_pass/score_ocr.py \
  --model-dir benchmarks/no_gpu_first_pass/output/umi_cpu \
  --out benchmarks/no_gpu_first_pass/output/umi_cpu/cer_scores.json
```

Run scorer tests:

```bash
python3 benchmarks/no_gpu_first_pass/test_score_ocr.py
```

## GJ.cool

Copy `.env.example` to `.env` and set the account-specific endpoint and access token:

```text
GJCOOL_BASE_URL=https://your-endpoint
GJCOOL_ACCESS_TOKEN=your-access-token
```

Run:

```bash
uv run --with requests \
  python benchmarks/no_gpu_first_pass/run_gjcool_api.py

python3 benchmarks/no_gpu_first_pass/score_ocr.py \
  --model-dir benchmarks/no_gpu_first_pass/output/gjcool \
  --out benchmarks/no_gpu_first_pass/output/gjcool/cer_scores.json
```

The benchmark sends grayscale images with a maximum side of 1800px. Larger RGB PNGs caused upload timeouts and broken connections in testing.

## KanDianGuJi

Set:

```text
KANDIANGUJI_TOKEN=your-token
KANDIANGUJI_EMAIL=your-account-email-or-phone
```

Run one page:

```bash
KANDIANGUJI_PAGES=44 \
  python3 benchmarks/no_gpu_first_pass/run_kandianguji_api.py
```

The implementation follows the documented Form Data API and uses `curl --http1.1` because Python TLS requests were unreliable from the original development network. Token status succeeded, but OCR calls remained intermittent. See `benchmarks/no_gpu_first_pass/output/kandianguji/run_status.md`.

## olmOCR on Kaggle

The olmOCR benchmark uses the same five pages and records GPU/model/timing metadata. Follow:

[`benchmarks/olmocr_first_pass/KAGGLE.md`](benchmarks/olmocr_first_pass/KAGGLE.md)

The short version:

```bash
bash benchmarks/olmocr_first_pass/run_kaggle.sh
```

Each run receives a unique workspace under `benchmarks/olmocr_first_pass/output/runs/`, preventing cached work from corrupting timing measurements.

## Reproducibility Notes

- Use the same five pages for every clean-set model comparison.
- Do not manually edit a model's output before scoring.
- Keep strict CER even when aligned CER is more representative.
- Record model identifier, image preprocessing, hardware, and wall time.
- Pre-download GPU models before starting timed inference.
- Do not reuse an olmOCR workspace for a timing run.

## Security

`.env` is ignored by Git and must never be committed. API tokens previously shared in chat should be rotated. Only `.env.example` with empty placeholders belongs in the repository.

## Limitations

- The reference is ChatGPT-assisted rather than human-verified.
- Some reference pages may contain less text than the complete page output from hosted OCR services.
- Hosted API timings include network latency.
- olmOCR timing includes model startup unless a persistent external server is used.
- The current set is small and should be expanded only after reference scope is made consistent.
