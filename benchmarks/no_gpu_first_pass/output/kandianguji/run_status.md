# KanDianGuJi Run Status

Date: 2026-06-30

Status: completed from the Modal/server environment.

The local development network produced intermittent TLS and empty-reply errors
against the KanDianGuJi OCR endpoint. The same runner completed successfully
from the Modal environment, which confirms the API format and credentials were
usable and that the earlier failures were transport-related.

Run settings:

```text
KANDIANGUJI_PAGES=44,80,160,240,320
KANDIANGUJI_MAX_ATTEMPTS=5
KANDIANGUJI_CURL_MAX_TIME=300
KANDIANGUJI_RETRY_SLEEP_SECONDS=20
```

Outputs:

```text
benchmarks/no_gpu_first_pass/output/kandianguji/page_044.txt
benchmarks/no_gpu_first_pass/output/kandianguji/page_080.txt
benchmarks/no_gpu_first_pass/output/kandianguji/page_160.txt
benchmarks/no_gpu_first_pass/output/kandianguji/page_240.txt
benchmarks/no_gpu_first_pass/output/kandianguji/page_320.txt
benchmarks/no_gpu_first_pass/output/kandianguji/cer_scores.json
```

Result summary:

```text
scored_pages: 5
weighted_cer: 0.2845
weighted_aligned_cer: 0.2527
total_wall_time_seconds: 58.433
avg_wall_time_seconds: 11.687
```

An additional image-size retry produced identical CER values, so the benchmark
uses this completed output set as the KanDianGuJi result.
