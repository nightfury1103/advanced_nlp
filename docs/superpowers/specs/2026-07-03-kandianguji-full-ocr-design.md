# KanDianGuJi Full-Book OCR Design

## Scope

This phase builds only the OCR extraction layer for full-book KanDianGuJi runs.
It does not perform sentence segmentation, NER, OCR correction, translation, or
final voting. Its job is to produce complete, resumable, page-level OCR outputs
that can later be compared with outputs from other OCR models.

## Requirement Context

`MidTerm_Requirement.pdf` requires OCR for image input in the monolingual Han
historical corpus task. The document does not require preserving rendered page
images as a dataset artifact. Original PDFs under `books/` remain the source
image evidence.

## Output Contract

Each OCR model should eventually write the same page-level layout:

```text
outputs/ocr_runs/<model>/<run_id>/
├── manifest.jsonl
├── pages_json/<book_id>/page_0001.json
├── pages_text/<book_id>/page_0001.txt
├── books_text/<book_id>.txt
└── logs/
```

KanDianGuJi is the first model implemented in this contract. Each manifest row
is JSON and includes:

```json
{
  "model": "kandianguji",
  "run_id": "kandianguji-full-YYYYMMDD",
  "book_id": "book_slug",
  "source_pdf": "books/source.pdf",
  "page_number": 1,
  "status": "ok",
  "text_path": "outputs/ocr_runs/kandianguji/run/pages_text/book_slug/page_0001.txt",
  "json_path": "outputs/ocr_runs/kandianguji/run/pages_json/book_slug/page_0001.json",
  "char_count": 123,
  "wall_time_seconds": 10.5,
  "error": null
}
```

Allowed statuses are `ok`, `blank`, `error`, and `skipped`.

## Runner Behavior

The runner reads PDFs from `books/`, processes every page, and writes outputs
after each page. It renders only one temporary page image at a time, uploads it
to KanDianGuJi, saves raw JSON and extracted text, appends a manifest row, and
continues. A resumed run skips pages that already have text output, unless
forced. Raw JSON without text is not considered complete because voting needs
the page text artifact.

Temporary rendered images are not primary outputs. They may be stored under a
cache directory during execution, but they should not be committed or treated as
the corpus.

## Agreement/Voting Preparation

This phase keeps raw OCR untouched. Later agreement and voting should normalize
text consistently across model outputs, compute page-level agreement, and write
a separate voted output. No later stage should overwrite `pages_json` or
`pages_text`.

## Error Handling

Per-page API failures write an error log and a manifest row with `status:
"error"` when continue-on-error is enabled. Blank text responses write empty
text files and use `status: "blank"` so pages remain auditable.

## Verification

Tests cover the model-neutral path layout, book slug generation, KanDianGuJi text
extraction from observed payloads, manifest row fields, and resume detection.
