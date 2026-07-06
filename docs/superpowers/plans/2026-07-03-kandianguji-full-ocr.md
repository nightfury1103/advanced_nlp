# KanDianGuJi Full-Book OCR Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a resumable full-book KanDianGuJi OCR runner that writes model-neutral outputs for later agreement and voting.

**Architecture:** Add a focused full-book runner under `scripts/` and keep the existing benchmark runner unchanged. The runner renders one temporary page image at a time, calls the existing KanDianGuJi form API shape, writes page JSON/text immediately, and appends manifest rows.

**Tech Stack:** Python standard library, `pypdfium2` for rendering, `Pillow` for image encoding, `curl` for API transport, `unittest` for tests.

---

### Task 1: Output Contract Helpers

**Files:**
- Create: `scripts/run_kandianguji_full_ocr.py`
- Create: `tests/test_kandianguji_full_ocr.py`

- [ ] Write failing tests for `book_id_from_path`, output path creation, manifest row creation, and text extraction from `{"data": ["line"]}` payloads.
- [ ] Run `python3 tests/test_kandianguji_full_ocr.py` and confirm it fails because `scripts.run_kandianguji_full_ocr` does not exist.
- [ ] Implement the helper functions in `scripts/run_kandianguji_full_ocr.py`.
- [ ] Run `python3 tests/test_kandianguji_full_ocr.py` and confirm helper tests pass.

### Task 2: Resume and Book Assembly

**Files:**
- Modify: `scripts/run_kandianguji_full_ocr.py`
- Modify: `tests/test_kandianguji_full_ocr.py`

- [ ] Write failing tests that completed page files are detected and that `books_text/<book_id>.txt` concatenates pages in numeric order with page markers.
- [ ] Run `python3 tests/test_kandianguji_full_ocr.py` and confirm the new tests fail because resume and book assembly are missing.
- [ ] Implement completed-page detection and book text assembly.
- [ ] Run `python3 tests/test_kandianguji_full_ocr.py` and confirm all tests pass.

### Task 3: CLI Runner

**Files:**
- Modify: `scripts/run_kandianguji_full_ocr.py`
- Modify: `README.md`

- [ ] Add CLI arguments for `--books-dir`, `--output-root`, `--run-id`, `--pages`, `--force`, `--keep-cache`, and `--continue-on-error`.
- [ ] Add KanDianGuJi environment loading using `.env`, requiring `KANDIANGUJI_TOKEN` and `KANDIANGUJI_EMAIL`.
- [ ] Render each PDF page to a temporary JPEG/PNG, call KanDianGuJi through `curl --http1.1`, save raw JSON/text, append manifest rows, and assemble book text at the end.
- [ ] Update `README.md` with the full-book OCR command and output layout.
- [ ] Run tests and a dry-run/import check.

### Task 4: Verification

**Files:**
- Existing test and script files.

- [ ] Run `python3 tests/test_kandianguji_full_ocr.py`.
- [ ] Run existing benchmark tests that do not require API tokens.
- [ ] Run `python3 scripts/run_kandianguji_full_ocr.py --help`.
- [ ] Report exact commands and results.
