from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.sentence_separation import book_sort_key


DEFAULT_MODEL_RUN_ROOT = Path("outputs/ner/ner-models-books-001-010-v001")
DEFAULT_VOTED_RUN = Path("outputs/ner/ner-agreement-vote-books-001-010-v001")
DEFAULT_OUTPUT_DIR = Path("outputs/ner/ner-release-candidate-books-001-010-v001")
MODEL_LABELS = ("ckip", "hanlp", "qwen25")
RELEASE_LABELS = ("PERSON", "LOCATION", "ORGANIZATION", "DATE", "TIME")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as input_file:
        for line_number, line in enumerate(input_file, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON") from exc
            if not isinstance(row, dict):
                raise ValueError(f"{path}:{line_number}: JSON row must be an object")
            rows.append(row)
    return rows


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as output_file:
        for row in rows:
            output_file.write(json.dumps(row, ensure_ascii=False) + "\n")
            count += 1
    return count


def sentence_sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        *book_sort_key(str(row.get("book_id", ""))),
        int(row.get("page_number", 0) or 0),
        int(row.get("sentence_number", 0) or 0),
        str(row.get("sentence_id", "")),
    )


def stable_key(row: dict[str, Any], entity: dict[str, Any] | None = None) -> str:
    parts = [str(row.get("sentence_id", ""))]
    if entity is not None:
        parts.extend(str(entity.get(key, "")) for key in ("start", "end", "label", "text"))
    return hashlib.sha256("\u241f".join(parts).encode("utf-8")).hexdigest()


def latest_valid_rows(paths: Iterable[Path]) -> tuple[dict[str, dict[str, Any]], int]:
    selected: dict[str, dict[str, Any]] = {}
    raw_count = 0
    for path in paths:
        for row in read_jsonl(path):
            raw_count += 1
            sentence_id = row.get("sentence_id")
            if not isinstance(sentence_id, str) or not sentence_id:
                raise ValueError(f"{path}: missing sentence_id")
            previous = selected.get(sentence_id)
            if previous is None or row.get("status") == "ok" or previous.get("status") != "ok":
                selected[sentence_id] = row
    return selected, raw_count


def copy_deduplicated_model_run(source_dir: Path, output_dir: Path) -> dict[str, Any]:
    source_sentences = source_dir / "sentences"
    rows, raw_count = latest_valid_rows(source_sentences.glob("*.jsonl"))
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows.values():
        book_id = row.get("book_id")
        if not isinstance(book_id, str) or not book_id:
            raise ValueError(f"{source_dir}: missing book_id")
        grouped[book_id].append(row)

    target_sentences = output_dir / "sentences"
    for book_id, book_rows in grouped.items():
        write_jsonl(target_sentences / f"{book_id}.jsonl", sorted(book_rows, key=sentence_sort_key))
    metadata_path = source_dir / "run_metadata.json"
    if metadata_path.exists():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata["release_copy"] = {"deduplicated": True, "raw_row_count": raw_count, "unique_sentence_count": len(rows)}
        (output_dir / "run_metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    summary = {
        "source_dir": str(source_dir),
        "raw_row_count": raw_count,
        "unique_sentence_count": len(rows),
        "duplicate_or_retry_rows_removed": raw_count - len(rows),
        "status_counts": dict(Counter(str(row.get("status")) for row in rows.values())),
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def validate_entity(row: dict[str, Any], entity: dict[str, Any]) -> bool:
    text = row.get("text")
    start = entity.get("start")
    end = entity.get("end")
    value = entity.get("text")
    return (
        isinstance(text, str)
        and isinstance(start, int)
        and not isinstance(start, bool)
        and isinstance(end, int)
        and not isinstance(end, bool)
        and isinstance(value, str)
        and 0 <= start < end <= len(text)
        and text[start:end] == value
    )


def release_rows(voted_dir: Path) -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]], Counter[str]]:
    releases: dict[str, list[dict[str, Any]]] = defaultdict(list)
    exclusions: dict[str, list[dict[str, Any]]] = defaultdict(list)
    label_counts: Counter[str] = Counter()
    for path in sorted((voted_dir / "sentences").glob("*.jsonl"), key=lambda item: book_sort_key(item.stem)):
        for row in read_jsonl(path):
            book_id = row.get("book_id")
            if not isinstance(book_id, str) or not book_id:
                raise ValueError(f"{path}: missing book_id")
            accepted = []
            excluded = []
            for entity in row.get("entities", []):
                if not isinstance(entity, dict) or not validate_entity(row, entity):
                    raise ValueError(f"{row.get('sentence_id')}: invalid voted entity")
                if entity.get("label") in RELEASE_LABELS:
                    accepted.append(entity)
                    label_counts[str(entity["label"])] += 1
                else:
                    excluded.append(entity)
            release_row = {
                **row,
                "entities": accepted,
                "release_schema": list(RELEASE_LABELS),
                "release_status": "automatically_voted_conservative",
            }
            releases[book_id].append(release_row)
            if excluded:
                exclusions[book_id].append(
                    {
                        "sentence_id": row.get("sentence_id"),
                        "book_id": book_id,
                        "page_number": row.get("page_number"),
                        "sentence_number": row.get("sentence_number"),
                        "text": row.get("text"),
                        "excluded_entities": excluded,
                        "reason": "excluded_from_conservative_release_schema",
                    }
                )
    return releases, exclusions, label_counts


def copy_disagreements(source_dir: Path, target_dir: Path) -> int:
    target_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for path in sorted((source_dir / "disagreements").glob("*.jsonl"), key=lambda item: book_sort_key(item.stem)):
        target_path = target_dir / path.name
        shutil.copyfile(path, target_path)
        count += sum(1 for line in target_path.open(encoding="utf-8") if line.strip())
    return count


def write_review_samples(
    *,
    output_dir: Path,
    releases: dict[str, list[dict[str, Any]]],
    disagreements_dir: Path,
    sample_per_label: int,
    disagreement_sample_size: int,
) -> dict[str, int]:
    accepted_by_label: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for rows in releases.values():
        for row in rows:
            for entity in row["entities"]:
                accepted_by_label[entity["label"]].append({"sentence": row, "entity": entity})

    review_dir = output_dir / "manual_review"
    counts = {}
    for label, values in accepted_by_label.items():
        chosen = sorted(values, key=lambda item: stable_key(item["sentence"], item["entity"]))[:sample_per_label]
        rows = [
            {
                "review_type": "accepted_entity",
                "review_status": "unreviewed",
                "sentence_id": item["sentence"]["sentence_id"],
                "book_id": item["sentence"]["book_id"],
                "page_number": item["sentence"]["page_number"],
                "text": item["sentence"]["text"],
                "entity": item["entity"],
                "review_fields": ["span_correct", "label_correct", "notes"],
            }
            for item in chosen
        ]
        write_jsonl(review_dir / f"accepted_{label.lower()}.jsonl", rows)
        counts[f"accepted_{label.lower()}"] = len(rows)

    disagreements = [
        row
        for path in disagreements_dir.glob("*.jsonl")
        for row in read_jsonl(path)
    ]
    chosen_disagreements = sorted(disagreements, key=stable_key)[:disagreement_sample_size]
    review_rows = [
        {
            "review_type": "model_disagreement",
            "review_status": "unreviewed",
            **row,
            "review_fields": ["should_entity_exist", "correct_span", "correct_label", "notes"],
        }
        for row in chosen_disagreements
    ]
    write_jsonl(review_dir / "disagreements.jsonl", review_rows)
    counts["disagreements"] = len(review_rows)
    return counts


def data_card(summary: dict[str, Any]) -> str:
    labels = ", ".join(f"`{label}` ({count})" for label, count in summary["release_label_counts"].items())
    return f"""# NER release candidate: books 1–10 v001

## Status

This is an automatically generated **release candidate**, not a human-validated scholarly dataset. It is suitable for internal evaluation and controlled pilot use only until the manual-review sample is annotated and quality metrics are reported.

## Scope

- Input: {summary['sentence_count']:,} agreed OCR sentence records from the books 1–10 sentence-vote run.
- NER ensemble: CKIP BERT, HanLP MSRA ELECTRA, and Qwen2.5-14B-Instruct-AWQ.
- Acceptance rule: exact span and canonical label agreement from at least two of three models.
- Public release schema: {', '.join(f'`{label}`' for label in RELEASE_LABELS)}.
- Included entities: {summary['release_entity_count']:,} ({labels}).
- Excluded from the primary schema: {summary['excluded_entity_count']:,} `NUMBER`/`MISC` candidates, retained in `audit/excluded_entities/`.

## Provenance

Each entity preserves its sentence identifier, book/page/sentence position, voter labels, raw model labels, and source run identifiers. Full model-level outputs are in `model_runs/`; unresolved model candidates are in `audit/disagreements/`.

## Known limitations

1. OCR errors are retained from upstream processing and can affect entity boundaries and labels.
2. The selected models were not fine-tuned on this Vietnamese historical Hán corpus.
3. Agreement is a confidence heuristic, not a substitute for human annotation.
4. Rights to source PDFs and third-party model licenses must be confirmed before public distribution.

## Required release gate

Annotate `manual_review/` using the supplied review fields, report per-label precision/recall (or at minimum precision with confidence intervals), and document the source-data rights and release license.
"""


def prepare_release(
    *,
    model_run_root: Path,
    voted_dir: Path,
    output_dir: Path,
    sample_per_label: int,
    disagreement_sample_size: int,
) -> dict[str, Any]:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    model_summaries = {}
    for label in MODEL_LABELS:
        source = model_run_root / label
        model_summaries[label] = copy_deduplicated_model_run(source, output_dir / "model_runs" / label)

    releases, exclusions, label_counts = release_rows(voted_dir)
    sentence_count = 0
    release_entity_count = 0
    excluded_entity_count = 0
    for book_id, rows in releases.items():
        rows = sorted(rows, key=sentence_sort_key)
        write_jsonl(output_dir / "entities" / f"{book_id}.jsonl", rows)
        sentence_count += len(rows)
        release_entity_count += sum(len(row["entities"]) for row in rows)
    for book_id, rows in exclusions.items():
        write_jsonl(output_dir / "audit" / "excluded_entities" / f"{book_id}.jsonl", rows)
        excluded_entity_count += sum(len(row["excluded_entities"]) for row in rows)

    disagreement_count = copy_disagreements(voted_dir, output_dir / "audit" / "disagreements")
    review_counts = write_review_samples(
        output_dir=output_dir,
        releases=releases,
        disagreements_dir=output_dir / "audit" / "disagreements",
        sample_per_label=sample_per_label,
        disagreement_sample_size=disagreement_sample_size,
    )
    summary = {
        "release_candidate": True,
        "status": "requires_manual_quality_review_and_rights_confirmation",
        "source_model_run_root": str(model_run_root),
        "source_voted_run": str(voted_dir),
        "sentence_count": sentence_count,
        "release_entity_count": release_entity_count,
        "release_label_counts": dict(label_counts),
        "excluded_entity_count": excluded_entity_count,
        "disagreement_audit_count": disagreement_count,
        "model_runs": model_summaries,
        "manual_review_sample_counts": review_counts,
        "release_schema": list(RELEASE_LABELS),
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "DATA_CARD.md").write_text(data_card(summary), encoding="utf-8")
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare a conservative, reviewable NER release candidate.")
    parser.add_argument("--model-run-root", type=Path, default=DEFAULT_MODEL_RUN_ROOT)
    parser.add_argument("--voted-dir", type=Path, default=DEFAULT_VOTED_RUN)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--sample-per-label", type=int, default=50)
    parser.add_argument("--disagreement-sample-size", type=int, default=200)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        summary = prepare_release(
            model_run_root=args.model_run_root,
            voted_dir=args.voted_dir,
            output_dir=args.output_dir,
            sample_per_label=args.sample_per_label,
            disagreement_sample_size=args.disagreement_sample_size,
        )
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
