from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.sentence_separation import book_sort_key


NER_AGREEMENT_MODEL = "ner_agreement_vote"
DEFAULT_LABELS = ["ckip", "hanlp", "qwen25"]
DEFAULT_OUTPUT_ROOT = Path("outputs/ner")


@dataclass(frozen=True)
class NerRun:
    label: str
    run_dir: Path
    model: str
    run_id: str
    sentences: dict[str, dict[str, Any]]


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


def load_ner_run(run_dir: Path, *, label: str) -> NerRun:
    run_dir = run_dir.resolve()
    metadata_path = run_dir / "run_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
    sentences_dir = run_dir / "sentences"
    if not sentences_dir.exists():
        raise FileNotFoundError(f"missing sentences directory: {sentences_dir}")

    sentences: dict[str, dict[str, Any]] = {}
    for path in sorted(sentences_dir.glob("*.jsonl"), key=lambda item: book_sort_key(item.stem)):
        for row in read_jsonl(path):
            sentence_id = row.get("sentence_id")
            if not isinstance(sentence_id, str) or not sentence_id:
                raise ValueError(f"{path}: missing sentence_id")
            previous = sentences.get(sentence_id)
            if previous is None or row.get("status") == "ok" or previous.get("status") != "ok":
                sentences[sentence_id] = row

    return NerRun(
        label=label,
        run_dir=run_dir,
        model=str(metadata.get("model") or ""),
        run_id=str(metadata.get("run_id") or ""),
        sentences=sentences,
    )


def valid_entity(text: str, value: Any) -> tuple[int, int, str] | None:
    if not isinstance(value, dict):
        return None
    start = value.get("start")
    end = value.get("end")
    label = value.get("label")
    if isinstance(start, bool) or isinstance(end, bool):
        return None
    if not isinstance(start, int) or not isinstance(end, int) or not isinstance(label, str) or not label:
        return None
    if not 0 <= start < end <= len(text):
        return None
    entity_text = value.get("text")
    if not isinstance(entity_text, str) or entity_text != text[start:end]:
        return None
    return start, end, label


def sentence_sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        *book_sort_key(str(row.get("book_id", ""))),
        int(row.get("page_number", 0) or 0),
        int(row.get("sentence_number", 0) or 0),
        str(row.get("sentence_id", "")),
    )


def choose_reference(rows_by_label: dict[str, dict[str, Any]], labels: list[str]) -> dict[str, Any]:
    for label in labels:
        row = rows_by_label.get(label)
        if row and row.get("status") == "ok":
            return row
    return next(iter(rows_by_label.values()))


def vote_sentence(
    *,
    rows_by_label: dict[str, dict[str, Any]],
    labels: list[str],
    threshold: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    reference = choose_reference(rows_by_label, labels)
    text = reference.get("text")
    if not isinstance(text, str):
        raise ValueError(f"{reference.get('sentence_id')}: missing sentence text")

    usable_labels = [
        label
        for label, row in rows_by_label.items()
        if row.get("status") == "ok" and row.get("text") == text
    ]
    invalid_labels = sorted(set(rows_by_label) - set(usable_labels))
    candidates: dict[tuple[int, int, str], list[tuple[str, dict[str, Any]]]] = defaultdict(list)

    for label in usable_labels:
        seen = set()
        for entity in rows_by_label[label].get("entities", []):
            key = valid_entity(text, entity)
            if key is None or key in seen:
                continue
            seen.add(key)
            candidates[key].append((label, entity))

    agreed = []
    rejected = []
    for (start, end, label), voters in sorted(candidates.items()):
        models = sorted(model_label for model_label, _ in voters)
        raw_labels = {
            model_label: entity.get("raw_label")
            for model_label, entity in voters
            if isinstance(entity.get("raw_label"), str)
        }
        scores = {
            model_label: entity.get("score")
            for model_label, entity in voters
            if isinstance(entity.get("score"), (int, float)) and not isinstance(entity.get("score"), bool)
        }
        payload = {
            "text": text[start:end],
            "start": start,
            "end": end,
            "label": label,
            "vote_count": len(voters),
            "voter_models": models,
            "raw_labels": raw_labels,
        }
        if scores:
            payload["scores"] = scores
        if len(voters) >= threshold:
            agreed.append(payload)
        else:
            rejected.append(payload)

    sentence = {
        "model": NER_AGREEMENT_MODEL,
        "sentence_id": reference.get("sentence_id"),
        "book_id": reference.get("book_id"),
        "page_number": reference.get("page_number"),
        "sentence_number": reference.get("sentence_number"),
        "text": text,
        "entities": agreed,
        "status": "ok" if len(usable_labels) >= threshold else "incomplete",
        "vote_threshold": threshold,
        "voter_labels": labels,
        "usable_voter_labels": usable_labels,
        "invalid_voter_labels": invalid_labels,
        "source_run_id": reference.get("source_run_id"),
        "source_agreement_ratio": reference.get("source_agreement_ratio"),
        "source_models": {label: row.get("model") for label, row in rows_by_label.items()},
        "source_run_ids": {label: row.get("run_id") for label, row in rows_by_label.items()},
    }
    audit = {
        "sentence_id": sentence["sentence_id"],
        "book_id": sentence["book_id"],
        "page_number": sentence["page_number"],
        "sentence_number": sentence["sentence_number"],
        "text": text,
        "status": sentence["status"],
        "agreed_entities": agreed,
        "unagreed_candidates": rejected,
        "usable_voter_labels": usable_labels,
        "invalid_voter_labels": invalid_labels,
    }
    return sentence, audit


def write_ner_agreement_run(
    *,
    run_dirs: list[Path],
    labels: list[str],
    output_root: Path,
    run_id: str,
    threshold: int = 2,
) -> dict[str, Any]:
    if len(run_dirs) != len(labels):
        raise ValueError("run_dirs and labels must have the same length")
    if threshold < 2 or threshold > len(labels):
        raise ValueError("threshold must be between 2 and the number of model runs")

    runs = [load_ner_run(run_dir, label=label) for run_dir, label in zip(run_dirs, labels)]
    all_ids = set().union(*(run.sentences for run in runs))
    output_dir = output_root / run_id
    sentences_dir = output_dir / "sentences"
    disagreements_dir = output_dir / "disagreements"
    sentences_dir.mkdir(parents=True, exist_ok=True)
    disagreements_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "manifest.jsonl"
    manifest_path.write_text("", encoding="utf-8")

    grouped_sentences: dict[str, list[dict[str, Any]]] = defaultdict(list)
    grouped_audits: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for sentence_id in all_ids:
        rows_by_label = {
            run.label: run.sentences[sentence_id]
            for run in runs
            if sentence_id in run.sentences
        }
        sentence, audit = vote_sentence(rows_by_label=rows_by_label, labels=labels, threshold=threshold)
        book_id = sentence.get("book_id")
        if not isinstance(book_id, str) or not book_id:
            raise ValueError(f"{sentence_id}: missing book_id")
        grouped_sentences[book_id].append(sentence)
        if audit["unagreed_candidates"] or audit["invalid_voter_labels"]:
            grouped_audits[book_id].append(audit)

    summary = {
        "run_id": run_id,
        "models": {run.label: run.model for run in runs},
        "source_run_ids": {run.label: run.run_id for run in runs},
        "vote_threshold": threshold,
        "books": {},
        "sentence_count": 0,
        "entity_count": 0,
        "incomplete_sentence_count": 0,
        "disagreement_sentence_count": 0,
    }
    with manifest_path.open("a", encoding="utf-8") as manifest_file:
        for book_id in sorted(grouped_sentences, key=book_sort_key):
            sentences = sorted(grouped_sentences[book_id], key=sentence_sort_key)
            audits = sorted(grouped_audits[book_id], key=sentence_sort_key)
            sentence_path = sentences_dir / f"{book_id}.jsonl"
            audit_path = disagreements_dir / f"{book_id}.jsonl"
            with sentence_path.open("w", encoding="utf-8") as output_file:
                for sentence in sentences:
                    output_file.write(json.dumps(sentence, ensure_ascii=False) + "\n")
            with audit_path.open("w", encoding="utf-8") as output_file:
                for audit in audits:
                    output_file.write(json.dumps(audit, ensure_ascii=False) + "\n")

            entity_count = sum(len(sentence["entities"]) for sentence in sentences)
            incomplete_count = sum(sentence["status"] != "ok" for sentence in sentences)
            row = {
                "model": NER_AGREEMENT_MODEL,
                "run_id": run_id,
                "book_id": book_id,
                "status": "ok" if incomplete_count == 0 else "partial",
                "sentence_path": str(sentence_path),
                "disagreement_path": str(audit_path),
                "sentence_count": len(sentences),
                "entity_count": entity_count,
                "incomplete_sentence_count": incomplete_count,
                "disagreement_sentence_count": len(audits),
                "vote_threshold": threshold,
                "source_models": {run.label: run.model for run in runs},
                "source_run_ids": {run.label: run.run_id for run in runs},
            }
            manifest_file.write(json.dumps(row, ensure_ascii=False) + "\n")
            summary["books"][book_id] = row
            summary["sentence_count"] += len(sentences)
            summary["entity_count"] += entity_count
            summary["incomplete_sentence_count"] += incomplete_count
            summary["disagreement_sentence_count"] += len(audits)

    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Vote exact NER spans and canonical labels across model runs.")
    parser.add_argument("--run-dir", action="append", type=Path, required=True)
    parser.add_argument("--label", action="append", help="Model labels in --run-dir order.")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument(
        "--run-id",
        default="ner-agreement-vote-" + dt.datetime.now().strftime("%Y%m%d-%H%M%S"),
    )
    parser.add_argument("--threshold", type=int, default=2)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    labels = args.label or DEFAULT_LABELS[: len(args.run_dir)]
    try:
        summary = write_ner_agreement_run(
            run_dirs=args.run_dir,
            labels=labels,
            output_root=args.output_root,
            run_id=args.run_id,
            threshold=args.threshold,
        )
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
