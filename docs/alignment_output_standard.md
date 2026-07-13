# Hán--Việt Sentence Alignment Standard

This phase builds an auditable parallel Hán--Việt corpus from two already
sentence-segmented documents. It follows the midterm requirement: image inputs
must complete OCR and sentence separation first; text inputs must complete
sentence separation first.

The runner is [`scripts/parallel_alignment.py`](../scripts/parallel_alignment.py).
It uses LaBSE sentence embeddings and a monotonic dynamic-programming decoder.
It can emit 1-1, 1-2, 2-1, and 2-2 matches, while preserving omissions as 1-0
or 0-1 rows for human review.

## Inputs

Create one UTF-8 JSONL sentence file for each side. Every row must contain a
stable `sentence_id` and non-empty `text`; extra provenance fields are allowed.

```json
{"sentence_id":"han-book-001-s0001","text":"臣謹奏。"}
{"sentence_id":"vi-book-001-s0001","text":"Thần kính tâu."}
```

The completed NER-agreement release is the preferred Hán source for this phase:

```text
outputs/ner/ner-agreement-vote-books-001-010-v001/sentences/
```

Those files preserve the sentence IDs, original Hán text, and agreed NER
annotations. They are valid directly as `source_path` values; alignment reads
only `sentence_id` and `text` and keeps the source IDs in every output row.
The Vietnamese translation must be supplied separately as matching JSONL files.

Create a JSONL document-pair manifest. Paths are resolved relative to the
manifest file.

```json
{"pair_id":"book-001","source_path":"../../outputs/ner/ner-agreement-vote-books-001-010-v001/sentences/越南汉文燕行文献集成_第1册.jsonl","target_path":"viet/book-001.jsonl"}
```

`pair_id` must identify a translation-equivalent document or section. Do not
pair files merely because their page counts happen to match.

## Run

```bash
uv run --with sentence-transformers --with torch --with numpy \
  python scripts/parallel_alignment.py \
  --pair-manifest data/alignment/pairs.jsonl \
  --run-id labse-han-viet-v001 \
  --device mps
```

Use `--device cpu` when no accelerator is available. The embedding model is
`sentence-transformers/LaBSE` by default. The first run downloads its weights.

## Outputs

```text
outputs/parallel_alignment/<run_id>/
├── manifest.jsonl
└── alignments/
    └── <pair_id>.jsonl
```

Each alignment row preserves both source and target IDs and text:

```json
{
  "alignment_id":"book-001-a00001",
  "pair_id":"book-001",
  "source_sentence_ids":["han-book-001-s0001"],
  "target_sentence_ids":["vi-book-001-s0001"],
  "source_text":"臣謹奏。",
  "target_text":"Thần kính tâu.",
  "relation":"1-1",
  "similarity":0.91,
  "confidence":"high",
  "review_required":false,
  "alignment_model":"labse_monotonic_sentence_alignment",
  "embedding_model":"sentence-transformers/LaBSE"
}
```

All rows marked `review_required: true` must be reviewed before releasing the
parallel corpus. This includes 1-N/N-1/N-N relations, low-similarity matches,
and unmatched source or target sentences.

## Validation protocol

Before a full run, manually annotate at least 100 document-local links sampled
from the target corpus. Compare predicted links to that gold sample using strict
precision, recall, and F1. Tune `--min-match-score` only on a development split;
keep a held-out sample for the reported final score.
