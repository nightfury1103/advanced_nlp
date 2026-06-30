# Advanced NLP: OCR Benchmark for Historical Chinese Books

This repository benchmarks OCR systems on vertically written historical Chinese text from a scanned Vietnamese collection. It focuses on reproducible model comparison rather than a single OCR demo.

The benchmark currently covers:

- Umi-OCR-style local CPU inference through RapidOCR ONNX Runtime
- GJ.cool hosted ancient-book OCR
- KanDianGuJi hosted OCR integration and transport diagnostics
- olmOCR GPU preparation for Kaggle or another NVIDIA environment

## Current Results

The clean evaluation set contains PDF pages `44`, `80`, `160`, `240`, and `320`. All models are compared against the same ChatGPT-assisted OCR reference.

### Main finding

KanDianGuJi is the strongest complete system in this benchmark: it scored all five clean pages and achieved the best weighted aligned CER. olmOCR on an NVIDIA L4 is competitive on the four pages it completed, but page `044` repeatedly produced no text output and is treated as a failed page rather than a scored result.

| Model | Scored pages | Strict weighted CER | Aligned weighted CER | Total time | Average/page | Notes |
|---|---:|---:|---:|---:|---:|---|
| KanDianGuJi | 5/5 | 0.2845 | 0.2527 | 58.433s | 11.687s | Best complete run; handles page `044` |
| olmOCR L4 FP8 | 4/5 | 0.3031 | 0.3031 | partial/manual | partial/manual | Page `044` produced no text output |
| Umi/RapidOCR CPU | 5/5 | 0.8691 | 0.8445 | 6.952s | 1.390s | Fast baseline, poor quality on historical vertical text |
| GJ.cool | 5/5 | 1.6400 | 0.3582 | 223.942s | 44.788s | Extra page text hurts strict CER; aligned CER is more representative |

Strict CER penalizes every additional OCR character. Aligned CER compares the reference against the best matching contiguous span in the OCR output. Both are reported because some ChatGPT references appear shorter than the complete page text returned by GJ.cool.

### KanDianGuJi page-level results

| Page | Strict CER | Aligned CER | Wall time | Status |
|---:|---:|---:|---:|---|
| 044 | 0.1765 | 0.1724 | 5.495s | Scored |
| 080 | 0.3286 | 0.2643 | 11.787s | Scored |
| 160 | 0.5782 | 0.5102 | 10.397s | Scored |
| 240 | 0.3582 | 0.3060 | 18.116s | Scored |
| 320 | 0.2527 | 0.2151 | 12.638s | Scored |

KanDianGuJi quality is usable for rough transcription and search, but it is not yet high-quality scholarly transcription. Pages `160` and `240` are the weakest pages. A retry with a different image size produced identical CER values, so image-size tuning did not improve quality.

### olmOCR L4 page-level results

| Page | Strict CER | Aligned CER | Status |
|---:|---:|---:|---|
| 044 | - | - | No text output / timeout problem |
| 080 | 0.2143 | 0.2143 | Scored |
| 160 | 0.5442 | 0.5442 | Scored |
| 240 | 0.2761 | 0.2761 | Scored |
| 320 | 0.1989 | 0.1989 | Scored |

olmOCR is competitive on the pages it completes, especially pages `080`, `240`, and `320`, but the page `044` failure makes the run incomplete. The benchmark does not synthesize or manually create a replacement `page_044.txt`.

### Model agreement

Agreement measures how similar two OCR outputs are to each other after the same normalization used for CER. Strict agreement is `1 - edit_distance / max(output_length)`. Aligned agreement compares the shorter output against the best contiguous span in the longer output, which is more appropriate when one system returns extra headers or page text.

All-model agreement on pages `080`, `160`, `240`, and `320`:

| Pair | Shared pages | Strict agreement | Aligned agreement |
|---|---:|---:|---:|
| KanDianGuJi vs olmOCR L4 FP8 | 4 | 0.7195 | 0.7701 |
| KanDianGuJi vs GJ.cool | 4 | 0.2161 | 0.5311 |
| olmOCR L4 FP8 vs GJ.cool | 4 | 0.2045 | 0.5080 |
| KanDianGuJi vs Umi/RapidOCR CPU | 4 | 0.0684 | 0.1495 |
| olmOCR L4 FP8 vs Umi/RapidOCR CPU | 4 | 0.0749 | 0.1495 |
| Umi/RapidOCR CPU vs GJ.cool | 4 | 0.0354 | 0.1158 |

Complete-model agreement on pages `044`, `080`, `160`, `240`, and `320`:

| Pair | Shared pages | Strict agreement | Aligned agreement |
|---|---:|---:|---:|
| KanDianGuJi vs GJ.cool | 5 | 0.3485 | 0.6902 |
| KanDianGuJi vs Umi/RapidOCR CPU | 5 | 0.0976 | 0.1574 |
| Umi/RapidOCR CPU vs GJ.cool | 5 | 0.0554 | 0.1415 |

The agreement results support the CER conclusion. KanDianGuJi and olmOCR are the closest systems on the four shared pages, while Umi/RapidOCR has low agreement with every other model. GJ.cool agrees better after alignment than under strict comparison because it often returns substantially more surrounding page text.

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
    │   ├── input_images_kandianguji_1200/
    │   ├── ground_truth/
    │   ├── output/
    │   │   ├── umi_cpu/
    │   │   ├── gjcool/
    │   │   ├── kandianguji/
    │   │   ├── olmocr_l4_smoke/
    │   │   └── agreement_scores.json
    │   ├── render_pages.py
    │   ├── agreement_ocr.py
    │   ├── run_umi_cpu_rapidocr.py
    │   ├── run_gjcool_api.py
    │   ├── run_kandianguji_api.py
    │   ├── run_kandianguji_modal.sh
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

Compute pairwise model agreement:

```bash
python3 benchmarks/no_gpu_first_pass/agreement_ocr.py \
  --out benchmarks/no_gpu_first_pass/output/agreement_scores.json
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

Run the clean set from a server environment:

```bash
KANDIANGUJI_PAGES=44,80,160,240,320 \
KANDIANGUJI_MAX_ATTEMPTS=5 \
KANDIANGUJI_CURL_MAX_TIME=300 \
KANDIANGUJI_RETRY_SLEEP_SECONDS=20 \
bash benchmarks/no_gpu_first_pass/run_kandianguji_modal.sh
```

The implementation follows the documented Form Data API and uses `curl --http1.1` because Python TLS requests were unreliable from the original development network. The local network was unstable, but the Modal/server run completed all five clean pages. See `benchmarks/no_gpu_first_pass/output/kandianguji/run_status.md`.

## olmOCR on Kaggle

The olmOCR benchmark uses the same five pages and records GPU/model/timing metadata. Follow:

[`benchmarks/olmocr_first_pass/KAGGLE.md`](benchmarks/olmocr_first_pass/KAGGLE.md)

The short version:

```bash
bash benchmarks/olmocr_first_pass/run_kaggle.sh
```

Each run receives a unique workspace under `benchmarks/olmocr_first_pass/output/runs/`, preventing cached work from corrupting timing measurements.

The recorded L4 smoke result used `allenai/olmOCR-2-7B-1025-FP8` with tensor parallel size `1` on one NVIDIA L4. Pages `080`, `160`, `240`, and `320` produced scored text outputs; page `044` produced no text output after retry and is counted as a missing prediction.

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
- The olmOCR L4 smoke run is incomplete because page `044` produced no text output.
- KanDianGuJi completed all pages, but pages `160` and `240` still have high CER.
- The current set is small and should be expanded only after reference scope is made consistent.
