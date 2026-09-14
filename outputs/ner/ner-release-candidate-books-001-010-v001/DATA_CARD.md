# NER release candidate: books 1–10 v001

## Status

This is an automatically generated **release candidate**, not a human-validated scholarly dataset. It is suitable for internal evaluation and controlled pilot use only until the manual-review sample is annotated and quality metrics are reported.

## Scope

- Input: 29,474 agreed OCR sentence records from the books 1–10 sentence-vote run.
- NER ensemble: CKIP BERT, HanLP MSRA ELECTRA, and Qwen2.5-14B-Instruct-AWQ.
- Acceptance rule: exact span and canonical label agreement from at least two of three models.
- Public release schema: `PERSON`, `LOCATION`, `ORGANIZATION`, `DATE`, `TIME`.
- Included entities: 7,907 (`ORGANIZATION` (171), `LOCATION` (4159), `PERSON` (2715), `DATE` (843), `TIME` (19)).
- Excluded from the primary schema: 2,091 `NUMBER`/`MISC` candidates, retained in `audit/excluded_entities/`.

## Provenance

Each entity preserves its sentence identifier, book/page/sentence position, voter labels, raw model labels, and source run identifiers. Full model-level outputs are in `model_runs/`; unresolved model candidates are in `audit/disagreements/`.

## Known limitations

1. OCR errors are retained from upstream processing and can affect entity boundaries and labels.
2. The selected models were not fine-tuned on this Vietnamese historical Hán corpus.
3. Agreement is a confidence heuristic, not a substitute for human annotation.
4. Rights to source PDFs and third-party model licenses must be confirmed before public distribution.

## Required release gate

Annotate `manual_review/` using the supplied review fields, report per-label precision/recall (or at minimum precision with confidence intervals), and document the source-data rights and release license.
