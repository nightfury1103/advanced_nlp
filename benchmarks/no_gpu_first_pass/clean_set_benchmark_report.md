# Clean-Set OCR Benchmark Report

Date: 2026-06-29

## Reference

Reference type: ChatGPT-assisted OCR output supplied in `artifacts/result`.

This is a silver reference, not human-verified ground truth. It is still useful for comparing OCR models consistently, as long as every model is scored against the same reference.

Imported reference files:

```text
benchmarks/no_gpu_first_pass/ground_truth/page_044.txt
benchmarks/no_gpu_first_pass/ground_truth/page_080.txt
benchmarks/no_gpu_first_pass/ground_truth/page_160.txt
benchmarks/no_gpu_first_pass/ground_truth/page_240.txt
benchmarks/no_gpu_first_pass/ground_truth/page_320.txt
```

## Scored Pages

Clean benchmark pages:

```text
044, 080, 160, 240, 320
```

Excluded from this clean-set score:

```text
005, 020, 052
```

These are harder manuscript/degraded pages and should be handled in a later stress-test set.

## Model Comparison

| Model | Pages | Strict Weighted CER | Aligned Weighted CER | Total Time | Avg/Page | Ref Chars | OCR Chars | OCR/Ref Ratio | Notes |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Umi-OCR CPU baseline via RapidOCR | 5 | 0.8691 | 0.8445 | 6.952s | 1.390s | 1100 | 813 | 0.7391 | Fast, inaccurate, misses text |
| GJ.cool | 5 | 1.6400 | 0.3582 | 223.942s | 44.788s | 1100 | 2672 | 2.4291 | Much stronger when extra full-page output is aligned |
| KanDianGuJi | 0 | - | - | - | - | - | - | - | Blocked by SSL/connection reset from this environment |
| olmOCR | 0 | - | - | - | - | - | - | - | Clean five-page GPU package prepared; run pending |

Strict CER penalizes all extra OCR text. Aligned CER compares the reference against the best matching contiguous span inside the OCR output. Aligned CER is useful here because the ChatGPT reference may cover less text than GJ.cool returned.

## Umi-OCR CPU Baseline

Implementation used: RapidOCR ONNX Runtime CPU baseline.

### Summary

| Metric | Value |
|---|---:|
| Scored pages | 5 |
| Missing reference pages | 3 |
| Reference chars | 1100 |
| OCR chars | 813 |
| Edit distance | 956 |
| Weighted CER | 0.8691 |
| Aligned edit distance | 929 |
| Aligned weighted CER | 0.8445 |
| Total inference time | 6.952s |
| Average inference time/page | 1.390s |
| Reference chars/sec | 158.23 |
| OCR chars/sec | 116.94 |
| OCR/reference char ratio | 0.7391 |

### Per Page

| Page | Reference Chars | OCR Chars | Char Ratio | Edit Distance | CER | Aligned CER | Time | OCR Items | OCR Chars/Sec |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 044 | 493 | 338 | 0.6856 | 426 | 0.8641 | 0.8600 | 2.503s | 11 | 135.04 |
| 080 | 140 | 117 | 0.8357 | 121 | 0.8643 | 0.8143 | 1.247s | 11 | 93.83 |
| 160 | 147 | 96 | 0.6531 | 121 | 0.8231 | 0.8231 | 0.936s | 7 | 102.56 |
| 240 | 134 | 112 | 0.8358 | 126 | 0.9403 | 0.8507 | 1.098s | 10 | 102.00 |
| 320 | 186 | 150 | 0.8065 | 162 | 0.8710 | 0.8387 | 1.168s | 11 | 128.42 |

Weighted CER:

```text
0.8691
```

Inference time:

```text
total: 6.952s
average/page: 1.390s
```

## Interpretation

The CPU baseline is fast, but not accurate enough for this old Chinese book OCR task. A CER around `0.87` means most characters differ from the ChatGPT-assisted reference after normalization. The output length ratio is also low at `0.7391`, so the model is likely missing substantial text in addition to substituting characters.

## GJ.cool

Implementation used: hosted GJ.cool `/ocr_pro` API.

Input preprocessing for API stability:

```text
grayscale, max side 1800px
```

The original full-resolution PNGs caused timeout/broken-pipe failures on larger pages. The resized inputs are stored in:

```text
benchmarks/no_gpu_first_pass/input_images_gjcool_1800/
```

### Summary

| Metric | Value |
|---|---:|
| Scored pages | 5 |
| Missing reference pages | 3 |
| Reference chars | 1100 |
| OCR chars | 2672 |
| Edit distance | 1804 |
| Weighted CER | 1.6400 |
| Aligned edit distance | 394 |
| Aligned weighted CER | 0.3582 |
| Total inference time | 223.942s |
| Average inference time/page | 44.788s |
| Reference chars/sec | 4.91 |
| OCR chars/sec | 11.93 |
| OCR/reference char ratio | 2.4291 |

### Per Page

| Page | Reference Chars | OCR Chars | Char Ratio | Edit Distance | CER | Aligned CER | Time | OCR Items | OCR Chars/Sec |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 044 | 493 | 555 | 1.1258 | 73 | 0.1481 | 0.1460 | 12.972s | 555 | 42.78 |
| 080 | 140 | 1406 | 10.0429 | 1306 | 9.3286 | 0.8786 | 65.642s | 1290 | 21.42 |
| 160 | 147 | 133 | 0.9048 | 69 | 0.4694 | 0.4694 | 46.398s | 133 | 2.87 |
| 240 | 134 | 407 | 3.0373 | 320 | 2.3881 | 0.7015 | 61.494s | 365 | 6.62 |
| 320 | 186 | 171 | 0.9194 | 36 | 0.1935 | 0.1935 | 37.436s | 171 | 4.57 |

### Interpretation

GJ.cool is clearly stronger than the CPU baseline on page `044` and page `320`. Its strict aggregate weighted CER is worse because it over-generates heavily on pages `080` and `240`. With aligned CER, which ignores extra prefix/suffix text and finds the best matching span, GJ.cool improves from `1.6400` to `0.3582`.

This may be a real OCR/layout failure, but it may also indicate that the ChatGPT reference for those pages covers only part of the page while GJ.cool returned the whole page. CER is only fair when OCR output and reference cover the same region.

The next useful comparison is to run olmOCR in the GPU environment against the same five-page clean set. KanDianGuJi now has credentials configured, but remains blocked by API transport errors from this environment.

## Score Commands

```bash
python3 benchmarks/no_gpu_first_pass/score_ocr.py \
  --model-dir benchmarks/no_gpu_first_pass/output/umi_cpu \
  --out benchmarks/no_gpu_first_pass/output/umi_cpu/cer_scores.json

python3 benchmarks/no_gpu_first_pass/score_ocr.py \
  --model-dir benchmarks/no_gpu_first_pass/output/gjcool \
  --out benchmarks/no_gpu_first_pass/output/gjcool/cer_scores.json
```
