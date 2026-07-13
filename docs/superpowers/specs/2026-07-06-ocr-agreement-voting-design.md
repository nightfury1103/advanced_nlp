# OCR Agreement Voting Design

## Goal

Build a deterministic agreement-voting pipeline for full-book OCR outputs under
`outputs/ocr_runs`. The first version must work with the partial model set
available today and require no code changes when one or two additional model
runs are added later.

## Inputs

The pipeline reads one or more explicit run directories, each following
`docs/ocr_output_standard.md`:

```text
outputs/ocr_runs/<model_name>/<run_id>/
├── manifest.jsonl
├── pages_text/<book_id>/page_0001.txt
├── pages_json/<book_id>/page_0001.json
└── books_text/<book_id>.txt
```

Each run is identified from its manifest rows. The latest non-`skipped` row for
each `(book_id, page_number)` is used. If only `skipped` rows exist for a page,
the latest skipped row may be used as a fallback because the page text already
exists.

Manifest text paths may be absolute paths from a remote run. The pipeline must
resolve them in this order:

1. Use the manifest path if it exists locally.
2. Use the same relative path from the current repository root if it exists.
3. Fall back to `<run_dir>/pages_text/<book_id>/page_NNNN.txt`.

## Voting Scope

Voting is page based. A page is eligible when at least `--min-models` usable
source texts exist; default `--min-models` is `2`. Statuses `ok`, `blank`, and
`skipped` are usable. Status `error` is not usable.

This allows current partial coverage:

- `churro` and `qwen35` can vote across their shared 12-book coverage.
- `kandianguji` can join only for books/pages where its book IDs match the
  selected run set.
- Later model runs can be added by passing more `--run-dir` arguments.

## Voting Algorithm

The first version uses deterministic character-level voting:

1. Normalize line endings but do not remove characters from source text.
2. Align each model text to the first source text with `difflib.SequenceMatcher`.
3. For each aligned character position, collect non-gap candidate characters.
4. Select the character with the most votes.
5. If there is a tie, select the character from the configured model priority.
   By default, priority follows the order of `--run-dir` arguments.
6. Preserve newline characters when they win a position.

This is intentionally simple and auditable. It is not a scholarly correction
system and does not use LLM adjudication.

## Outputs

The pipeline writes a model-neutral agreement run:

```text
outputs/ocr_agreement/<agreement_run_id>/
├── manifest.jsonl
├── pages_text/<book_id>/page_0001.txt
├── pages_json/<book_id>/page_0001.json
└── books_text/<book_id>.txt
```

`manifest.jsonl` rows use model `agreement_vote`, status `ok` or `blank`, and
record `source_models`, `source_run_ids`, `voter_count`, and `agreement_ratio`.

Each page JSON contains source metadata, the selected text, per-position vote
summary counts, tie count, and agreement statistics. This gives later review
tools enough context to find low-confidence pages.

## CLI

Create `scripts/ocr_agreement_vote.py`:

```bash
python3 scripts/ocr_agreement_vote.py \
  --run-dir outputs/ocr_runs/churro/churro-full-001 \
  --run-dir outputs/ocr_runs/qwen35/qwen35-full-001 \
  --run-id agreement-vote-dev
```

Important options:

- `--run-dir`: repeatable source OCR run directory.
- `--output-root`: default `outputs/ocr_agreement`.
- `--run-id`: default timestamped id.
- `--min-models`: default `2`.
- `--book-id`: optional repeatable filter.
- `--model-priority`: optional comma-separated model names for tie breaking.
- `--dry-run`: print eligibility summary without writing outputs.

## Error Handling

The CLI exits with code `2` for invalid inputs such as missing manifests,
duplicate model/run identity, or fewer than two source run directories. Pages
below `--min-models` are skipped and summarized; they are not fatal.

## Testing

Unit tests cover manifest loading, latest-row selection, remote path fallback,
character voting with majority and ties, dry-run eligibility, and output layout.
Tests use temporary directories and do not depend on the large OCR output files.
