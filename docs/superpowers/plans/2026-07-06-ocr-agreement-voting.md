# OCR Agreement Voting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic CLI pipeline that votes across existing full-book OCR runs and writes a reusable agreement output run.

**Architecture:** Add a focused script at `scripts/ocr_agreement_vote.py` with pure functions for manifest loading, page text resolution, voting, and output writing. Add unit tests in `tests/test_ocr_agreement_vote.py` using temporary files so behavior is reproducible without large OCR artifacts.

**Tech Stack:** Python 3 standard library: `argparse`, `json`, `dataclasses`, `datetime`, `difflib`, `pathlib`, `tempfile`, `unittest`.

---

### Task 1: Manifest Loading And Page Resolution

**Files:**
- Create: `tests/test_ocr_agreement_vote.py`
- Create: `scripts/ocr_agreement_vote.py`

- [ ] **Step 1: Write failing tests**

Add tests for latest manifest row selection and local fallback when manifest
paths point to a remote mount.

- [ ] **Step 2: Run tests to verify failure**

Run: `python3 -m unittest tests.test_ocr_agreement_vote -v`

Expected: import failure because `scripts.ocr_agreement_vote` does not exist.

- [ ] **Step 3: Implement minimal manifest functions**

Create dataclasses for OCR runs and page inputs, load `manifest.jsonl`, choose
latest usable rows, and resolve page text paths.

- [ ] **Step 4: Run tests to verify pass**

Run: `python3 -m unittest tests.test_ocr_agreement_vote -v`

Expected: manifest tests pass.

### Task 2: Character Voting

**Files:**
- Modify: `tests/test_ocr_agreement_vote.py`
- Modify: `scripts/ocr_agreement_vote.py`

- [ ] **Step 1: Write failing tests**

Add tests for majority voting, tie-breaking by model priority, and blank source
handling.

- [ ] **Step 2: Run tests to verify failure**

Run: `python3 -m unittest tests.test_ocr_agreement_vote -v`

Expected: failures for missing voting functions.

- [ ] **Step 3: Implement voting**

Use `difflib.SequenceMatcher` to align each source against the first source and
choose per-position winners by vote count and model priority.

- [ ] **Step 4: Run tests to verify pass**

Run: `python3 -m unittest tests.test_ocr_agreement_vote -v`

Expected: all current tests pass.

### Task 3: Agreement Output Writer

**Files:**
- Modify: `tests/test_ocr_agreement_vote.py`
- Modify: `scripts/ocr_agreement_vote.py`

- [ ] **Step 1: Write failing tests**

Add tests that `write_agreement_run` creates `pages_text`, `pages_json`,
`books_text`, and `manifest.jsonl` in the standard layout.

- [ ] **Step 2: Run tests to verify failure**

Run: `python3 -m unittest tests.test_ocr_agreement_vote -v`

Expected: failure for missing output writer.

- [ ] **Step 3: Implement writer**

Write one page text and JSON file per eligible page, append manifest rows, and
assemble combined book text with `=== page_NNNN ===` markers.

- [ ] **Step 4: Run tests to verify pass**

Run: `python3 -m unittest tests.test_ocr_agreement_vote -v`

Expected: all unit tests pass.

### Task 4: CLI And Real-Data Smoke Test

**Files:**
- Modify: `tests/test_ocr_agreement_vote.py`
- Modify: `scripts/ocr_agreement_vote.py`

- [ ] **Step 1: Write failing CLI tests**

Add parser tests for repeated `--run-dir`, `--min-models`, `--book-id`, and
`--dry-run`.

- [ ] **Step 2: Run tests to verify failure**

Run: `python3 -m unittest tests.test_ocr_agreement_vote -v`

Expected: parser-related failures.

- [ ] **Step 3: Implement CLI**

Add `build_parser`, `main`, validation, dry-run summary, and write-mode summary.

- [ ] **Step 4: Verify tests and smoke run**

Run:

```bash
python3 -m unittest tests.test_ocr_agreement_vote -v
python3 scripts/ocr_agreement_vote.py \
  --run-dir outputs/ocr_runs/churro/churro-full-001 \
  --run-dir outputs/ocr_runs/qwen35/qwen35-full-001 \
  --run-id agreement-vote-smoke \
  --book-id 越南汉文燕行文献集成_第1册 \
  --min-models 2
```

Expected: tests pass and the smoke output appears under
`outputs/ocr_agreement/agreement-vote-smoke/`.

### Self-Review

- Spec coverage: tasks cover manifest loading, path fallback, voting, output
  layout, CLI filters, dry-run, and real-data smoke verification.
- Placeholder scan: no unresolved placeholders remain.
- Type consistency: functions will use `OcrRun`, `PageCandidate`, and
  `VoteResult` consistently across tests and implementation.
