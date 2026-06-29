# No-GPU OCR Benchmark Report

Date: 2026-06-26

## Current Status

This file is the general benchmark setup report. The clean-set CER report is now available at:

```text
benchmarks/no_gpu_first_pass/clean_set_benchmark_report.md
```

The reference used there is ChatGPT-assisted OCR output supplied in `artifacts/result`, not human-verified ground truth.

What exists now:

- A reproducible 8-page OCR sample.
- Runtime/smoke output for the local CPU baseline.
- CER scoring code.
- Empty ground-truth files waiting for manual transcription.

What is still required for a real benchmark:

- Fill `ground_truth/page_*.txt` with corrected transcription for each selected page.
- Run each OCR model on the same page images.
- Score each model using CER against the same ground truth.

## Benchmark Pages

```text
5, 20, 44, 52, 80, 160, 240, 320
```

Ground-truth files:

```text
benchmarks/no_gpu_first_pass/ground_truth/page_005.txt
benchmarks/no_gpu_first_pass/ground_truth/page_020.txt
benchmarks/no_gpu_first_pass/ground_truth/page_044.txt
benchmarks/no_gpu_first_pass/ground_truth/page_052.txt
benchmarks/no_gpu_first_pass/ground_truth/page_080.txt
benchmarks/no_gpu_first_pass/ground_truth/page_160.txt
benchmarks/no_gpu_first_pass/ground_truth/page_240.txt
benchmarks/no_gpu_first_pass/ground_truth/page_320.txt
```

## Real Accuracy Metric

Primary metric: character error rate, or CER.

```text
CER = edit_distance(ground_truth, ocr_output) / length(ground_truth)
```

The scorer normalizes whitespace and common punctuation before computing CER. It does not normalize variant characters, because variant handling is one of the things we need to evaluate for old Chinese OCR.

Run after ground truth is filled:

```bash
python3 benchmarks/no_gpu_first_pass/score_ocr.py \
  --model-dir benchmarks/no_gpu_first_pass/output/umi_cpu \
  --out benchmarks/no_gpu_first_pass/output/umi_cpu/cer_scores.json
```

## Smoke Results Only

These numbers are useful only for runtime and basic failure detection. They do not measure correctness.

| Model | Mode | Pages | Total Time | Avg/Page | Text Chars | OCR Items | Failed Pages | Status |
|---|---:|---:|---:|---:|---:|---:|---|---|
| Umi-OCR CPU baseline via RapidOCR ONNX Runtime | Local CPU | 8 | 10.781s | 1.348s | 1362 | 105 | - | Smoke run completed |
| KanDianGuJi | Hosted API | 0 | - | - | - | - | - | Blocked: missing credentials |
| GJ.cool | Hosted API | 0 | - | - | - | - | - | Blocked: missing credentials |
| olmOCR | GPU/remote | 0 | - | - | - | - | - | Deferred to GPU environment |

## Per-Page Smoke Output

| Page | Time | OCR Items | Text Chars |
|---:|---:|---:|---:|
| 5 | 1.263s | 9 | 139 |
| 20 | 1.329s | 24 | 168 |
| 44 | 2.503s | 11 | 387 |
| 52 | 1.237s | 22 | 157 |
| 80 | 1.247s | 11 | 127 |
| 160 | 0.936s | 7 | 102 |
| 240 | 1.098s | 10 | 121 |
| 320 | 1.168s | 11 | 161 |

## Page Set Correction

Page `040` was removed from the active benchmark because the rendered PNG was effectively blank. Page `044` replaces it as the printed vertical Chinese control page.

## Interpretation

The current CPU result should not be used to choose the best OCR model. It only shows that the local CPU baseline is runnable and that it visibly struggles on this document. A meaningful model decision requires CER scores from verified transcriptions.
