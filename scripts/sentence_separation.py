from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable


SENTENCE_MODEL = "sentence_separation"
DEFAULT_OUTPUT_ROOT = Path("outputs/sentence_separation")
USABLE_STATUSES = {"ok", "blank", "skipped"}
BOUNDARY_PUNCTUATION = set("。！？；!?;．.")
CLOSING_PUNCTUATION = set("」』》）】〕〗”’\"'")


@dataclass(frozen=True)
class PageText:
    input_run_id: str
    input_run_dir: Path
    book_id: str
    page_number: int
    status: str
    text: str
    text_path: Path
    agreement_ratio: float | None
    tie_count: int | None


@dataclass(frozen=True)
class SentenceSegment:
    text: str
    method: str


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


def latest_rows_by_page(rows: Iterable[dict]) -> dict[tuple[str, int], dict]:
    latest_non_skipped: dict[tuple[str, int], dict] = {}
    skipped_fallbacks: dict[tuple[str, int], dict] = {}
    for row in rows:
        book_id = row.get("book_id")
        page_number = row.get("page_number")
        status = row.get("status")
        if not isinstance(book_id, str) or not isinstance(page_number, int):
            raise ValueError("manifest row missing book_id or integer page_number")
        key = (book_id, page_number)
        if status == "skipped":
            skipped_fallbacks[key] = row
        else:
            latest_non_skipped[key] = row

    selected = {
        key: row
        for key, row in latest_non_skipped.items()
        if row.get("status") in USABLE_STATUSES
    }
    for key, row in skipped_fallbacks.items():
        selected.setdefault(key, row)
    return selected


def resolve_text_path(row: dict, run_dir: Path, repo_root: Path) -> Path:
    raw_path = row.get("text_path")
    if isinstance(raw_path, str) and raw_path:
        manifest_path = Path(raw_path)
        if manifest_path.exists():
            return manifest_path
        repo_relative = repo_root / manifest_path
        if repo_relative.exists():
            return repo_relative
        run_relative = run_dir / manifest_path
        if run_relative.exists():
            return run_relative

    book_id = row["book_id"]
    page_number = row["page_number"]
    fallback = run_dir / "pages_text" / book_id / f"page_{page_number:04d}.txt"
    if fallback.exists():
        return fallback
    raise FileNotFoundError(f"cannot resolve text for {book_id} page_{page_number:04d}")


def book_sort_key(book_id: str) -> tuple[int, str]:
    match = re.search(r"第(\d+)册", book_id)
    if match:
        return int(match.group(1)), book_id
    return sys.maxsize, book_id


def load_manifest_pages(run_dirs: list[Path], repo_root: Path | None = None) -> list[PageText]:
    repo_root = (repo_root or Path.cwd()).resolve()
    pages = []
    for run_dir in run_dirs:
        run_dir = run_dir.resolve()
        manifest_path = run_dir / "manifest.jsonl"
        if not manifest_path.exists():
            raise FileNotFoundError(f"missing manifest: {manifest_path}")
        rows = read_jsonl(manifest_path)
        for row in latest_rows_by_page(rows).values():
            text_path = resolve_text_path(row, run_dir, repo_root)
            run_id = row.get("run_id")
            status = row.get("status")
            if not isinstance(run_id, str) or not run_id:
                raise ValueError(f"{manifest_path}: manifest row missing run_id")
            if not isinstance(status, str) or status not in USABLE_STATUSES:
                continue
            pages.append(
                PageText(
                    input_run_id=run_id,
                    input_run_dir=run_dir,
                    book_id=row["book_id"],
                    page_number=row["page_number"],
                    status=status,
                    text=text_path.read_text(encoding="utf-8"),
                    text_path=text_path,
                    agreement_ratio=row.get("agreement_ratio"),
                    tie_count=row.get("tie_count"),
                )
            )

    return sorted(pages, key=lambda page: (*book_sort_key(page.book_id), page.page_number))


def has_boundary_punctuation(text: str) -> bool:
    return any(char in BOUNDARY_PUNCTUATION for char in text)


def segment_text(text: str) -> list[SentenceSegment]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if not normalized.strip():
        return []
    if not has_boundary_punctuation(normalized):
        return [
            SentenceSegment(line.strip(), "line_fallback")
            for line in normalized.splitlines()
            if line.strip()
        ]

    compact = "".join(line.strip() for line in normalized.splitlines())
    segments = []
    buffer: list[str] = []
    index = 0
    while index < len(compact):
        char = compact[index]
        buffer.append(char)
        if char in BOUNDARY_PUNCTUATION:
            index += 1
            while index < len(compact) and compact[index] in CLOSING_PUNCTUATION:
                buffer.append(compact[index])
                index += 1
            sentence = "".join(buffer).strip()
            if sentence:
                segments.append(SentenceSegment(sentence, "punctuation"))
            buffer = []
            continue
        index += 1

    trailing = "".join(buffer).strip()
    if trailing:
        segments.append(SentenceSegment(trailing, "punctuation"))
    return segments


def sentence_id(book_id: str, page_number: int, index: int) -> str:
    return f"{book_id}-page_{page_number:04d}-s{index:04d}"


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def assemble_book_sentences(run_root: Path, book_id: str, page_payloads: list[dict]) -> None:
    output_path = run_root / "books_sentences" / f"{book_id}.jsonl"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as output_file:
        for page_payload in sorted(page_payloads, key=lambda payload: payload["page_number"]):
            for sentence in page_payload["sentences"]:
                output_file.write(json.dumps(sentence, ensure_ascii=False) + "\n")


def write_sentence_run(
    pages: list[PageText],
    *,
    output_root: Path,
    run_id: str,
    segmenter: Callable[[str], list[SentenceSegment]] | None = None,
    output_model: str = SENTENCE_MODEL,
    page_metadata: dict | None = None,
    sentence_metadata: dict | None = None,
    max_workers: int = 1,
) -> dict:
    run_root = output_root / run_id
    manifest_path = run_root / "manifest.jsonl"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    if manifest_path.exists():
        manifest_path.unlink()

    segmenter = segmenter or segment_text
    page_metadata = page_metadata or {}
    sentence_metadata = sentence_metadata or {}
    page_payloads_by_book: dict[str, list[dict]] = {}
    written_pages = 0
    written_sentences = 0
    blank_pages = 0

    def build_page_payload(page: PageText) -> dict:
        segments = segmenter(page.text)
        sentences = [
            {
                "sentence_id": sentence_id(page.book_id, page.page_number, index),
                "book_id": page.book_id,
                "page_number": page.page_number,
                "sentence_number": index,
                "text": segment.text,
                "method": segment.method,
                "source_text_path": str(page.text_path),
                "source_run_id": page.input_run_id,
                "source_agreement_ratio": page.agreement_ratio,
                "source_tie_count": page.tie_count,
                **sentence_metadata,
            }
            for index, segment in enumerate(segments, start=1)
        ]
        page_payload = {
            "model": output_model,
            "run_id": run_id,
            "book_id": page.book_id,
            "page_number": page.page_number,
            "source_run_id": page.input_run_id,
            "source_text_path": str(page.text_path),
            "source_status": page.status,
            "sentence_count": len(sentences),
            "sentences": sentences,
            **page_metadata,
        }
        return page_payload

    if max_workers > 1:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            page_payloads = list(executor.map(build_page_payload, pages))
    else:
        page_payloads = [build_page_payload(page) for page in pages]

    for page, page_payload in zip(pages, page_payloads):
        page_name = f"page_{page.page_number:04d}"
        sentences = page_payload["sentences"]
        json_path = run_root / "sentences_json" / page.book_id / f"{page_name}.json"
        text_path = run_root / "sentences_text" / page.book_id / f"{page_name}.txt"
        write_json(json_path, page_payload)
        text_path.parent.mkdir(parents=True, exist_ok=True)
        text_path.write_text("\n".join(sentence["text"] for sentence in sentences), encoding="utf-8")

        row = {
            "model": output_model,
            "run_id": run_id,
            "book_id": page.book_id,
            "page_number": page.page_number,
            "status": "ok" if sentences else "blank",
            "text_path": str(text_path),
            "json_path": str(json_path),
            "sentence_count": len(sentences),
            "source_run_id": page.input_run_id,
            "source_text_path": str(page.text_path),
            "source_status": page.status,
            "source_agreement_ratio": page.agreement_ratio,
            "source_tie_count": page.tie_count,
            **page_metadata,
        }
        with manifest_path.open("a", encoding="utf-8") as manifest_file:
            manifest_file.write(json.dumps(row, ensure_ascii=False) + "\n")

        page_payloads_by_book.setdefault(page.book_id, []).append(page_payload)
        written_pages += 1
        written_sentences += len(sentences)
        blank_pages += not sentences

    for book_id, page_payloads in page_payloads_by_book.items():
        assemble_book_sentences(run_root, book_id, page_payloads)

    return {
        "run_root": str(run_root),
        "written_books": len(page_payloads_by_book),
        "written_pages": written_pages,
        "written_sentences": written_sentences,
        "blank_pages": blank_pages,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Separate voted OCR output into sentence units.")
    parser.add_argument("--input-run-dir", action="append", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument(
        "--run-id",
        default="sentence-separation-" + dt.datetime.now().strftime("%Y%m%d-%H%M%S"),
    )
    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    return build_parser().parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        pages = load_manifest_pages(args.input_run_dir, repo_root=Path.cwd())
        summary = write_sentence_run(pages, output_root=args.output_root, run_id=args.run_id)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
