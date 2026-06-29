# No-GPU OCR First-Pass Run Status

Date: 2026-06-26

## Completed

Rendered 8 benchmark pages to PNG:

```text
page_005.png
page_020.png
page_044.png
page_052.png
page_080.png
page_160.png
page_240.png
page_320.png
```

Ran the local CPU OCR baseline through RapidOCR ONNX Runtime:

```bash
uv run --with rapidocr_onnxruntime --with pillow \
  python benchmarks/no_gpu_first_pass/run_umi_cpu_rapidocr.py
```

Summary:

```text
page_005: 9 items, 139 chars, 1.263s
page_020: 24 items, 168 chars, 1.329s
page_044: 11 items, 387 chars, 2.503s
page_052: 22 items, 157 chars, 1.237s
page_080: 11 items, 127 chars, 1.247s
page_160: 7 items, 102 chars, 0.936s
page_240: 10 items, 121 chars, 1.098s
page_320: 11 items, 161 chars, 1.168s
```

Output:

```text
benchmarks/no_gpu_first_pass/output/umi_cpu/
```

## Blocked By Credentials

KanDianGuJi:

```text
missing required environment variable: KANDIANGUJI_TOKEN
```

GJ.cool:

```text
missing required environment variable: GJCOOL_BASE_URL
```

## Initial Quality Note

The local CPU baseline is fast but weak for this material. It returned partial/noisy text on most old-book pages. Hosted ancient-book OCR APIs should be tested next once credentials are available.

Page `040` was removed from the active benchmark because the rendered input image was effectively blank. Page `044` replaces it.
