# olmOCR Clean-Set Benchmark

This folder prepares the same five-page clean set used for Umi/RapidOCR and GJ.cool.

## Input

- Pages: `44, 80, 160, 240, 320`
- Combined PDF: `olmocr_clean_5_pages.pdf`
- Recommended benchmark inputs: five individual files in `input_pages/page_*.pdf`
- ChatGPT-assisted reference: `../no_gpu_first_pass/ground_truth/page_*.txt`

Using individual one-page PDFs gives one Markdown output per source page while loading the model only once.

## Requirements

- Recent NVIDIA GPU with at least 12GB VRAM; L4, RTX 4090, L40S, A100, or H100 is preferred.
- Approximately 30GB free disk space.
- Internet enabled for package/model download.
- Poppler installed.

Official installation command:

```bash
pip install "olmocr[gpu]" --extra-index-url https://download.pytorch.org/whl/cu128
```

See `KAGGLE.md` for the notebook workflow.

After cloning this repository into Kaggle, the complete workflow can be run with one command:

```bash
bash benchmarks/olmocr_first_pass/run_kaggle.sh
```

## GPU Run

Run from the repository root:

```bash
export OLMOCR_BIN="/path/to/venv/bin/olmocr"
export OLMOCR_MODEL="allenai/olmOCR-2-7B-1025-FP8"
export OLMOCR_TP_SIZE=1
export OLMOCR_RUN_ID="kaggle-run-1"

bash benchmarks/olmocr_first_pass/run_olmocr_gpu.sh
```

For a Kaggle T4x2 session, `OLMOCR_TP_SIZE=2` can be attempted, but T4/P100 are not among the officially tested GPUs and may fail with the current FP8/vLLM stack.

Each run gets a new directory:

```text
benchmarks/olmocr_first_pass/output/runs/<run-id>/
```

It contains:

- `gpu_info.txt`
- `model.txt`
- `olmocr_timing.txt`
- `benchmark_meta.json`
- `workspace/markdown/page_*.md`
- `text/page_*.txt`
- `text/summary.json`

Timing is end-to-end batch wall time. It includes model startup and excludes model download only when the model was pre-cached before starting the timed script.

## Scoring

```bash
python3 benchmarks/no_gpu_first_pass/score_ocr.py \
  --model-dir benchmarks/olmocr_first_pass/output/runs/<run-id>/text \
  --out benchmarks/olmocr_first_pass/output/runs/<run-id>/text/cer_scores.json
```

## Remote Server

For an OpenAI-compatible endpoint, use `run_olmocr_remote.sh`. Provider model names vary, so set `OLMOCR_MODEL` to the identifier expected by that provider.
