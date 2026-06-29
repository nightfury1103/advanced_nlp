# olmOCR First-Pass Run Status

Date: 2026-06-26

## Command Tested

```bash
uvx --from olmocr olmocr benchmarks/olmocr_first_pass/output \
  --markdown \
  --workers 1 \
  --pages_per_group 1 \
  --max_server_ready_timeout 5 \
  --pdfs benchmarks/olmocr_first_pass/olmocr_sample_8_pages.pdf
```

## Result

Status: blocked before inference.

Observed error:

```text
ERROR:olmocr.check:pdftoppm is not installed.
ERROR:olmocr.check:Check the README in the https://github.com/allenai/olmocr/blob/main/README.md for installation instructions
```

## Environment Notes

- `olmocr` is not installed on PATH.
- `uvx --from olmocr olmocr --help` works and confirms the CLI can be invoked through uv.
- `pdftoppm`/Poppler is missing.
- Homebrew is not installed.
- Hardware is Apple M1 with no CUDA GPU.
- PyTorch reports `cuda_available False` and `mps_available True`.
- No obvious remote inference variables were configured for `OLMOCR`, `OPENAI`, `DEEPINFRA`, `PARASAIL`, `CIRRASCALE`, `AI2`, or `VLLM`.

## Next Runnable Options

1. Run this benchmark on a CUDA machine with Poppler and `olmocr[gpu]`.
2. Run this benchmark against a remote OpenAI-compatible endpoint using `--server`, `--api_key`, and `--model`.

The prepared benchmark input is still valid:

```text
benchmarks/olmocr_first_pass/olmocr_sample_8_pages.pdf
```
