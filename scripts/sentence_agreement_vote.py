from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from scripts.sentence_separation import DEFAULT_OUTPUT_ROOT, book_sort_key, sentence_id, write_json


SENTENCE_AGREEMENT_MODEL = "sentence_agreement_vote"
RUN_LABELS = ["rule", "jiayan", "qwen"]
DEFAULT_PRIORITY_LABELS = ["qwen", "rule", "jiayan"]


@dataclass(frozen=True)
class SourcePage:
    label: str
    run_id: str
    book_id: str
    page_number: int
    status: str
    sentences: list[str]
    source_text_path: str
    source_run_id: str | None
    source_status: str | None
    source_agreement_ratio: float | None
    source_tie_count: int | None
    json_path: Path


@dataclass(frozen=True)
class SentenceRun:
    label: str
    run_dir: Path
    run_id: str
    pages: dict[tuple[str, int], SourcePage]


@dataclass(frozen=True)
class BoundaryVoteResult:
    boundaries: list[int]
    boundary_vote_counts: dict[int, int]
    valid_labels: list[str]
    invalid_labels: list[str]


@dataclass(frozen=True)
class AgreementSegment:
    text: str
    method: str
    boundary_vote_count: int | None


@dataclass(frozen=True)
class AgreementPageResult:
    segments: list[AgreementSegment]
    method: str
    boundaries: list[int]
    boundary_vote_counts: dict[int, int]
    valid_labels: list[str]
    invalid_labels: list[str]


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as input_file:
        for line_number, line in enumerate(input_file, start=1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSONL row") from exc
    return rows


def compact_text(text: str) -> str:
    return "".join(text.split())


def flatten_sentence_text(text: str) -> str:
    return "".join(line.strip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")).strip()


def sentence_boundaries(sentences: list[str], reference_text: str) -> list[int]:
    reference_length = len(compact_text(reference_text))
    boundaries = []
    offset = 0
    for sentence in sentences:
        offset += len(compact_text(sentence))
        if offset < reference_length:
            boundaries.append(offset)
    if offset != reference_length:
        raise ValueError("sentences do not cover reference text")
    return boundaries


def boundary_votes(
    *,
    reference_text: str,
    sentence_lists: dict[str, list[str]],
    threshold: int,
) -> BoundaryVoteResult:
    counts: Counter[int] = Counter()
    valid_labels = []
    invalid_labels = []
    for label, sentences in sentence_lists.items():
        try:
            boundaries = sentence_boundaries(sentences, reference_text)
        except ValueError:
            invalid_labels.append(label)
            continue
        valid_labels.append(label)
        counts.update(boundaries)

    voted_boundaries = sorted(boundary for boundary, count in counts.items() if count >= threshold)
    return BoundaryVoteResult(
        boundaries=voted_boundaries,
        boundary_vote_counts={boundary: counts[boundary] for boundary in voted_boundaries},
        valid_labels=valid_labels,
        invalid_labels=invalid_labels,
    )


def split_reference_text(reference_text: str, boundaries: list[int], vote_counts: dict[int, int]) -> list[AgreementSegment]:
    segments = []
    boundary_set = set(boundaries)
    current = []
    nonspace_count = 0
    for char in reference_text.replace("\r\n", "\n").replace("\r", "\n"):
        current.append(char)
        if not char.isspace():
            nonspace_count += 1
        if nonspace_count in boundary_set:
            text = flatten_sentence_text("".join(current))
            if text:
                segments.append(AgreementSegment(text=text, method="agreement_vote", boundary_vote_count=vote_counts[nonspace_count]))
            current = []
    trailing = flatten_sentence_text("".join(current))
    if trailing:
        segments.append(AgreementSegment(text=trailing, method="agreement_vote", boundary_vote_count=None))
    return segments


def fallback_segments(sentences: list[str]) -> list[AgreementSegment]:
    return [
        AgreementSegment(text=flatten_sentence_text(sentence), method="agreement_fallback", boundary_vote_count=None)
        for sentence in sentences
        if flatten_sentence_text(sentence)
    ]


def sentence_agreement_vote(
    *,
    reference_text: str,
    sentence_lists: dict[str, list[str]],
    threshold: int,
    priority_labels: list[str] | None = None,
) -> AgreementPageResult:
    vote = boundary_votes(reference_text=reference_text, sentence_lists=sentence_lists, threshold=threshold)
    if len(vote.valid_labels) >= threshold:
        segments = split_reference_text(reference_text, vote.boundaries, vote.boundary_vote_counts)
        return AgreementPageResult(
            segments=segments,
            method="agreement_vote",
            boundaries=vote.boundaries,
            boundary_vote_counts=vote.boundary_vote_counts,
            valid_labels=vote.valid_labels,
            invalid_labels=vote.invalid_labels,
        )

    priority_labels = priority_labels or DEFAULT_PRIORITY_LABELS
    for label in priority_labels:
        if label in sentence_lists:
            segments = fallback_segments(sentence_lists[label])
            return AgreementPageResult(
                segments=segments,
                method="agreement_fallback",
                boundaries=[],
                boundary_vote_counts={},
                valid_labels=vote.valid_labels,
                invalid_labels=vote.invalid_labels,
            )
    return AgreementPageResult([], "agreement_fallback", [], {}, vote.valid_labels, vote.invalid_labels)


def load_sentence_run(run_dir: Path, *, label: str) -> SentenceRun:
    run_dir = run_dir.resolve()
    manifest_path = run_dir / "manifest.jsonl"
    if not manifest_path.exists():
        raise FileNotFoundError(f"missing manifest: {manifest_path}")

    pages = {}
    run_id = ""
    for row in read_jsonl(manifest_path):
        book_id = row.get("book_id")
        page_number = row.get("page_number")
        json_path = row.get("json_path")
        if not isinstance(book_id, str) or not isinstance(page_number, int) or not isinstance(json_path, str):
            raise ValueError(f"{manifest_path}: invalid sentence manifest row")
        resolved_json_path = Path(json_path)
        if not resolved_json_path.exists():
            resolved_json_path = run_dir / json_path
        payload = json.loads(resolved_json_path.read_text(encoding="utf-8"))
        sentences = [
            sentence["text"]
            for sentence in payload.get("sentences", [])
            if isinstance(sentence, dict) and isinstance(sentence.get("text"), str)
        ]
        row_run_id = row.get("run_id")
        if isinstance(row_run_id, str) and row_run_id:
            run_id = row_run_id
        pages[(book_id, page_number)] = SourcePage(
            label=label,
            run_id=row_run_id or payload.get("run_id") or "",
            book_id=book_id,
            page_number=page_number,
            status=row.get("status", "ok"),
            sentences=sentences,
            source_text_path=row.get("source_text_path") or payload.get("source_text_path") or "",
            source_run_id=row.get("source_run_id") or payload.get("source_run_id"),
            source_status=row.get("source_status") or payload.get("source_status"),
            source_agreement_ratio=row.get("source_agreement_ratio"),
            source_tie_count=row.get("source_tie_count"),
            json_path=resolved_json_path,
        )
    return SentenceRun(label=label, run_dir=run_dir, run_id=run_id, pages=pages)


def resolve_source_text_path(path_text: str, repo_root: Path) -> Path:
    path = Path(path_text)
    if path.exists():
        return path
    repo_path = repo_root / path
    if repo_path.exists():
        return repo_path
    raise FileNotFoundError(f"cannot resolve source text path: {path_text}")


def all_page_keys(runs: list[SentenceRun]) -> list[tuple[str, int]]:
    keys = set()
    for run in runs:
        keys.update(run.pages)
    return sorted(keys, key=lambda key: (*book_sort_key(key[0]), key[1]))


def priority_page(pages: dict[str, SourcePage], priority_labels: list[str]) -> SourcePage:
    for label in priority_labels:
        page = pages.get(label)
        if page is not None:
            return page
    return next(iter(pages.values()))


def write_sentence_agreement_run(
    *,
    run_dirs: list[Path],
    labels: list[str],
    output_root: Path,
    run_id: str,
    threshold: int,
    priority_labels: list[str],
) -> dict:
    if len(run_dirs) != len(labels):
        raise ValueError("run_dirs and labels must have the same length")
    runs = [load_sentence_run(run_dir, label=label) for run_dir, label in zip(run_dirs, labels)]
    run_root = output_root / run_id
    manifest_path = run_root / "manifest.jsonl"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    if manifest_path.exists():
        manifest_path.unlink()

    page_payloads_by_book: dict[str, list[dict]] = {}
    method_counts: Counter[str] = Counter()
    written_pages = 0
    written_sentences = 0
    blank_pages = 0
    repo_root = Path.cwd()

    for book_id, page_number in all_page_keys(runs):
        pages_by_label = {
            run.label: run.pages[(book_id, page_number)]
            for run in runs
            if (book_id, page_number) in run.pages
        }
        page_for_metadata = priority_page(pages_by_label, priority_labels)
        source_text_path = resolve_source_text_path(page_for_metadata.source_text_path, repo_root)
        reference_text = source_text_path.read_text(encoding="utf-8")
        sentence_lists = {label: page.sentences for label, page in pages_by_label.items()}
        result = sentence_agreement_vote(
            reference_text=reference_text,
            sentence_lists=sentence_lists,
            threshold=threshold,
            priority_labels=priority_labels,
        )

        sentences = [
            {
                "sentence_id": sentence_id(book_id, page_number, index),
                "book_id": book_id,
                "page_number": page_number,
                "sentence_number": index,
                "text": segment.text,
                "method": segment.method,
                "boundary_vote_count": segment.boundary_vote_count,
                "source_text_path": str(source_text_path),
                "source_run_id": page_for_metadata.source_run_id,
                "source_agreement_ratio": page_for_metadata.source_agreement_ratio,
                "source_tie_count": page_for_metadata.source_tie_count,
                "voter_runs": {label: page.run_id for label, page in pages_by_label.items()},
            }
            for index, segment in enumerate(result.segments, start=1)
        ]

        source_run_ids = {label: page.run_id for label, page in pages_by_label.items()}
        page_payload = {
            "model": SENTENCE_AGREEMENT_MODEL,
            "run_id": run_id,
            "book_id": book_id,
            "page_number": page_number,
            "source_run_id": page_for_metadata.source_run_id,
            "source_text_path": str(source_text_path),
            "source_status": page_for_metadata.source_status,
            "sentence_count": len(sentences),
            "sentences": sentences,
            "vote_threshold": threshold,
            "vote_method": result.method,
            "voter_labels": labels,
            "valid_voter_labels": result.valid_labels,
            "invalid_voter_labels": result.invalid_labels,
            "source_run_ids": source_run_ids,
            "boundary_vote_counts": {str(key): value for key, value in result.boundary_vote_counts.items()},
        }
        page_name = f"page_{page_number:04d}"
        json_path = run_root / "sentences_json" / book_id / f"{page_name}.json"
        text_path = run_root / "sentences_text" / book_id / f"{page_name}.txt"
        write_json(json_path, page_payload)
        text_path.parent.mkdir(parents=True, exist_ok=True)
        text_path.write_text("\n".join(sentence["text"] for sentence in sentences), encoding="utf-8")

        row = {
            "model": SENTENCE_AGREEMENT_MODEL,
            "run_id": run_id,
            "book_id": book_id,
            "page_number": page_number,
            "status": "ok" if sentences else "blank",
            "text_path": str(text_path),
            "json_path": str(json_path),
            "sentence_count": len(sentences),
            "source_run_id": page_for_metadata.source_run_id,
            "source_text_path": str(source_text_path),
            "source_status": page_for_metadata.source_status,
            "source_agreement_ratio": page_for_metadata.source_agreement_ratio,
            "source_tie_count": page_for_metadata.source_tie_count,
            "vote_threshold": threshold,
            "vote_method": result.method,
            "voter_labels": labels,
            "valid_voter_labels": result.valid_labels,
            "invalid_voter_labels": result.invalid_labels,
            "source_run_ids": source_run_ids,
        }
        with manifest_path.open("a", encoding="utf-8") as manifest_file:
            manifest_file.write(json.dumps(row, ensure_ascii=False) + "\n")
        page_payloads_by_book.setdefault(book_id, []).append(page_payload)
        method_counts.update(sentence["method"] for sentence in sentences)
        written_pages += 1
        written_sentences += len(sentences)
        blank_pages += not sentences

    for book_id, payloads in page_payloads_by_book.items():
        output_path = run_root / "books_sentences" / f"{book_id}.jsonl"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as output_file:
            for payload in sorted(payloads, key=lambda item: item["page_number"]):
                for sentence in payload["sentences"]:
                    output_file.write(json.dumps(sentence, ensure_ascii=False) + "\n")

    return {
        "run_root": str(run_root),
        "written_books": len(page_payloads_by_book),
        "written_pages": written_pages,
        "written_sentences": written_sentences,
        "blank_pages": blank_pages,
        "method_counts": dict(method_counts),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Vote sentence boundaries across sentence-separation runs.")
    parser.add_argument("--input-run-dir", action="append", type=Path, required=True)
    parser.add_argument("--label", action="append", required=True, help="Label for the corresponding input run.")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument(
        "--run-id",
        default="sentence-agreement-vote-" + dt.datetime.now().strftime("%Y%m%d-%H%M%S"),
    )
    parser.add_argument("--threshold", type=int, default=2)
    parser.add_argument("--priority-label", action="append", default=None)
    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    return build_parser().parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    priority_labels = args.priority_label or DEFAULT_PRIORITY_LABELS
    try:
        summary = write_sentence_agreement_run(
            run_dirs=args.input_run_dir,
            labels=args.label,
            output_root=args.output_root,
            run_id=args.run_id,
            threshold=args.threshold,
            priority_labels=priority_labels,
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
