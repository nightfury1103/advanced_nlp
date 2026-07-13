from __future__ import annotations

import argparse
import datetime as dt
import difflib
import json
import sys
from collections import Counter, OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


AGREEMENT_MODEL = "agreement_vote"
USABLE_STATUSES = {"ok", "blank", "skipped"}
DEFAULT_OUTPUT_ROOT = Path("outputs/ocr_agreement")


@dataclass(frozen=True)
class PageCandidate:
    model: str
    run_id: str
    book_id: str
    page_number: int
    text: str
    status: str
    text_path: Path


@dataclass(frozen=True)
class OcrRun:
    model: str
    run_id: str
    run_dir: Path
    pages: dict[tuple[str, int], PageCandidate]


@dataclass(frozen=True)
class VoteResult:
    text: str
    voter_count: int
    position_count: int
    unanimous_count: int
    tie_count: int
    agreement_ratio: float
    positions: list[dict]


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


def row_identity(row: dict) -> tuple[str, str]:
    model = row.get("model")
    run_id = row.get("run_id")
    if not isinstance(model, str) or not model:
        raise ValueError("manifest row missing non-empty model")
    if not isinstance(run_id, str) or not run_id:
        raise ValueError("manifest row missing non-empty run_id")
    return model, run_id


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

    selected: dict[tuple[str, int], dict] = {}
    for key, row in latest_non_skipped.items():
        if row.get("status") in USABLE_STATUSES:
            selected[key] = row
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

    book_id = row["book_id"]
    page_number = row["page_number"]
    fallback = run_dir / "pages_text" / book_id / f"page_{page_number:04d}.txt"
    if fallback.exists():
        return fallback

    for alias in book_id_aliases(book_id):
        alias_path = run_dir / "pages_text" / alias / f"page_{page_number:04d}.txt"
        if alias_path.exists():
            return alias_path

    raise FileNotFoundError(
        f"cannot resolve text for {row.get('model')} {row.get('run_id')} "
        f"{book_id} page_{page_number:04d}"
    )


def book_id_aliases(book_id: str) -> list[str]:
    aliases = []
    if book_id.endswith("-1"):
        aliases.append(book_id[:-2])
    else:
        aliases.append(f"{book_id}-1")
    return aliases


def load_ocr_run(run_dir: Path, repo_root: Path | None = None) -> OcrRun:
    run_dir = run_dir.resolve()
    repo_root = (repo_root or Path.cwd()).resolve()
    manifest_path = run_dir / "manifest.jsonl"
    if not manifest_path.exists():
        raise FileNotFoundError(f"missing manifest: {manifest_path}")

    rows = read_jsonl(manifest_path)
    if not rows:
        raise ValueError(f"empty manifest: {manifest_path}")
    model, run_id = row_identity(rows[0])
    for row in rows[1:]:
        current_model, current_run_id = row_identity(row)
        if (current_model, current_run_id) != (model, run_id):
            raise ValueError(
                f"{manifest_path} mixes identities: "
                f"{model}/{run_id} and {current_model}/{current_run_id}"
            )

    pages = {}
    for key, row in latest_rows_by_page(rows).items():
        text_path = resolve_text_path(row, run_dir, repo_root)
        pages[key] = PageCandidate(
            model=model,
            run_id=run_id,
            book_id=row["book_id"],
            page_number=row["page_number"],
            text=text_path.read_text(encoding="utf-8"),
            status=row["status"],
            text_path=text_path,
        )
    return OcrRun(model=model, run_id=run_id, run_dir=run_dir, pages=pages)


def collect_eligible_pages(
    runs: list[OcrRun],
    *,
    min_models: int,
    book_ids: list[str] | None,
) -> OrderedDict[tuple[str, int], list[PageCandidate]]:
    allowed_books = {canonical_book_id(book_id) for book_id in book_ids} if book_ids else None
    pages_by_run = []
    for run in runs:
        normalized = {}
        for (book_id, page_number), candidate in run.pages.items():
            normalized[(canonical_book_id(book_id), page_number)] = candidate
        pages_by_run.append(normalized)

    keys = sorted(
        {
            key
            for pages in pages_by_run
            for key in pages
            if allowed_books is None or key[0] in allowed_books
        },
        key=lambda item: (item[0], item[1]),
    )

    pages: OrderedDict[tuple[str, int], list[PageCandidate]] = OrderedDict()
    for key in keys:
        candidates = [run_pages[key] for run_pages in pages_by_run if key in run_pages]
        if len(candidates) >= min_models:
            pages[key] = candidates
    return pages


def canonical_book_id(book_id: str) -> str:
    if book_id.endswith("-1"):
        return book_id[:-2]
    return book_id


def candidate_alignment(
    base: str,
    candidate: str,
) -> tuple[dict[tuple[str, int, int], str], dict[int, list[str]]]:
    aligned: dict[tuple[str, int, int], str] = {}
    insertions: dict[int, list[str]] = {}
    matcher = difflib.SequenceMatcher(a=base, b=candidate, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "insert":
            insertions.setdefault(i1, []).extend(candidate[j1:j2])
            continue
        if tag == "delete":
            continue
        left = base[i1:i2]
        right = candidate[j1:j2]
        width = min(len(left), len(right))
        for offset in range(width):
            aligned[("base", i1 + offset, 0)] = right[offset]
        if len(right) > len(left):
            insertions.setdefault(i2, []).extend(right[len(left) :])
    return aligned, insertions


def build_alignment_columns(
    base: str,
    candidates: list[PageCandidate],
) -> tuple[list[tuple[str, int, int]], dict[str, dict[tuple[str, int, int], str]]]:
    aligned_by_model = {}
    insertions_by_model = {}
    max_insertions: Counter[int] = Counter()

    for candidate in candidates:
        aligned, insertions = candidate_alignment(base, candidate.text)
        aligned_by_model[candidate.model] = aligned
        insertions_by_model[candidate.model] = insertions
        for anchor, chars in insertions.items():
            max_insertions[anchor] = max(max_insertions[anchor], len(chars))

    columns = []
    for anchor in range(len(base) + 1):
        for offset in range(max_insertions[anchor]):
            key = ("insert", anchor, offset)
            columns.append(key)
            for candidate in candidates:
                chars = insertions_by_model[candidate.model].get(anchor, [])
                if offset < len(chars):
                    aligned_by_model[candidate.model][key] = chars[offset]
        if anchor < len(base):
            columns.append(("base", anchor, 0))

    return columns, aligned_by_model


def priority_index(model: str, model_priority: list[str]) -> int:
    try:
        return model_priority.index(model)
    except ValueError:
        return len(model_priority)


def choose_vote(
    votes: list[tuple[str, str | None]],
    model_priority: list[str],
) -> tuple[str | None, bool, int]:
    counts = Counter(char for _, char in votes)
    high_count = max(counts.values())
    winners = {char for char, count in counts.items() if count == high_count}
    tied = len(winners) > 1
    for model, char in sorted(votes, key=lambda item: priority_index(item[0], model_priority)):
        if char in winners:
            return char, tied, high_count
    return votes[0][1], tied, high_count


def vote_text(
    candidates: list[PageCandidate],
    model_priority: list[str] | None = None,
    min_votes: int | None = None,
) -> VoteResult:
    if not candidates:
        raise ValueError("cannot vote without candidates")
    model_priority = model_priority or [candidate.model for candidate in candidates]
    min_votes = min_votes or (len(candidates) // 2 + 1)
    base_candidate = max(
        candidates,
        key=lambda candidate: (len(candidate.text), -priority_index(candidate.model, model_priority)),
    )
    base = base_candidate.text.replace("\r\n", "\n").replace("\r", "\n")
    normalized_candidates = [
        PageCandidate(
            candidate.model,
            candidate.run_id,
            candidate.book_id,
            candidate.page_number,
            candidate.text.replace("\r\n", "\n").replace("\r", "\n"),
            candidate.status,
            candidate.text_path,
        )
        for candidate in candidates
    ]

    if not base:
        return VoteResult(
            text="",
            voter_count=len(candidates),
            position_count=0,
            unanimous_count=0,
            tie_count=0,
            agreement_ratio=1.0,
            positions=[],
        )

    columns, aligned_by_model = build_alignment_columns(base, normalized_candidates)
    output_chars = []
    positions = []
    unanimous_count = 0
    tie_count = 0
    agreement_sum = 0.0

    for index, column in enumerate(columns):
        votes = [
            (candidate.model, aligned_by_model[candidate.model].get(column))
            for candidate in normalized_candidates
        ]
        if not votes:
            continue

        selected, tied, selected_count = choose_vote(votes, model_priority)
        if selected is None:
            continue
        vote_counts = Counter(char for _, char in votes)
        output_chars.append(selected)
        if len(vote_counts) == 1 and len(votes) == len(candidates):
            unanimous_count += 1
        if tied:
            tie_count += 1
        agreement_sum += selected_count / len(candidates)
        positions.append(
            {
                "index": index,
                "selected": selected,
                "votes": {
                    "<gap>" if char is None else char: count
                    for char, count in sorted(
                        vote_counts.items(),
                        key=lambda item: (-item[1], "" if item[0] is None else item[0]),
                    )
                },
                "voter_count": len(votes),
                "tied": tied,
            }
        )

    position_count = len(positions)
    return VoteResult(
        text="".join(output_chars),
        voter_count=len(candidates),
        position_count=position_count,
        unanimous_count=unanimous_count,
        tie_count=tie_count,
        agreement_ratio=round(agreement_sum / position_count, 4) if position_count else 1.0,
        positions=positions,
    )


def assemble_book_text(run_root: Path, book_id: str) -> Path:
    page_dir = run_root / "pages_text" / book_id
    output_path = run_root / "books_text" / f"{book_id}.txt"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    page_paths = sorted(page_dir.glob("page_*.txt"))
    with output_path.open("w", encoding="utf-8") as output_file:
        for index, page_path in enumerate(page_paths):
            output_file.write(f"=== {page_path.stem} ===\n")
            output_file.write(page_path.read_text(encoding="utf-8").strip())
            output_file.write("\n")
            if index != len(page_paths) - 1:
                output_file.write("\n")
    return output_path


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_agreement_run(
    pages: dict[tuple[str, int], list[PageCandidate]],
    *,
    output_root: Path,
    run_id: str,
    model_priority: list[str],
    min_models: int | None = None,
) -> dict:
    run_root = output_root / run_id
    manifest_path = run_root / "manifest.jsonl"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    if manifest_path.exists():
        manifest_path.unlink()

    written_books = set()
    written_pages = 0
    blank_pages = 0
    for (book_id, page_number), candidates in pages.items():
        result = vote_text(candidates, model_priority=model_priority, min_votes=min_models)
        page_name = f"page_{page_number:04d}"
        text_path = run_root / "pages_text" / book_id / f"{page_name}.txt"
        json_path = run_root / "pages_json" / book_id / f"{page_name}.json"
        text_path.parent.mkdir(parents=True, exist_ok=True)
        text_path.write_text(result.text, encoding="utf-8")

        source_models = [candidate.model for candidate in candidates]
        source_run_ids = [candidate.run_id for candidate in candidates]
        status = "ok" if result.text else "blank"
        page_payload = {
            "model": AGREEMENT_MODEL,
            "run_id": run_id,
            "book_id": book_id,
            "page_number": page_number,
            "text": result.text,
            "status": status,
            "voter_count": result.voter_count,
            "source_models": source_models,
            "source_run_ids": source_run_ids,
            "agreement_ratio": result.agreement_ratio,
            "position_count": result.position_count,
            "unanimous_count": result.unanimous_count,
            "tie_count": result.tie_count,
            "sources": [
                {
                    "model": candidate.model,
                    "run_id": candidate.run_id,
                    "status": candidate.status,
                    "text_path": str(candidate.text_path),
                    "char_count": len(candidate.text),
                }
                for candidate in candidates
            ],
            "positions": result.positions,
        }
        write_json(json_path, page_payload)

        row = {
            "model": AGREEMENT_MODEL,
            "run_id": run_id,
            "book_id": book_id,
            "source_pdf": None,
            "page_number": page_number,
            "status": status,
            "text_path": str(text_path),
            "json_path": str(json_path),
            "char_count": len(result.text),
            "wall_time_seconds": 0.0,
            "error": None,
            "source_models": source_models,
            "source_run_ids": source_run_ids,
            "voter_count": result.voter_count,
            "agreement_ratio": result.agreement_ratio,
            "tie_count": result.tie_count,
        }
        with manifest_path.open("a", encoding="utf-8") as manifest_file:
            manifest_file.write(json.dumps(row, ensure_ascii=False) + "\n")

        written_books.add(book_id)
        written_pages += 1
        blank_pages += status == "blank"

    for book_id in sorted(written_books):
        assemble_book_text(run_root, book_id)

    return {
        "run_root": str(run_root),
        "written_pages": written_pages,
        "written_books": len(written_books),
        "blank_pages": blank_pages,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = build_parser()
    return parser.parse_args(argv)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Vote across full-book OCR runs and write an agreement OCR run."
    )
    parser.add_argument("--run-dir", action="append", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument(
        "--run-id",
        default="agreement-vote-" + dt.datetime.now().strftime("%Y%m%d-%H%M%S"),
    )
    parser.add_argument(
        "--min-models",
        type=int,
        default=None,
        help="Minimum source models per page. Defaults to unique model majority: num_models // 2 + 1.",
    )
    parser.add_argument("--book-id", action="append")
    parser.add_argument("--model-priority", help="Comma-separated model priority for tie breaks")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def validate_args(args: argparse.Namespace) -> None:
    if len(args.run_dir) < 2:
        raise ValueError("at least two --run-dir values are required")
    if args.min_models is not None and args.min_models < 2:
        raise ValueError("--min-models must be at least 2")
    if args.min_models is not None and args.min_models > len(args.run_dir):
        raise ValueError("--min-models cannot exceed the number of --run-dir values")


def effective_min_models(model_names: list[str], requested_min_models: int | None) -> int:
    if requested_min_models is not None:
        return requested_min_models
    unique_model_count = len(set(model_names))
    return unique_model_count // 2 + 1


def summarize_inputs(runs: list[OcrRun], eligible_pages: dict[tuple[str, int], list[PageCandidate]]) -> dict:
    books = sorted({book_id for book_id, _ in eligible_pages})
    return {
        "source_runs": [
            {
                "model": run.model,
                "run_id": run.run_id,
                "run_dir": str(run.run_dir),
                "page_count": len(run.pages),
            }
            for run in runs
        ],
        "eligible_books": len(books),
        "eligible_pages": len(eligible_pages),
        "books": books,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        validate_args(args)
        repo_root = Path.cwd()
        runs = [load_ocr_run(run_dir, repo_root) for run_dir in args.run_dir]
        identities = [(run.model, run.run_id) for run in runs]
        if len(set(identities)) != len(identities):
            raise ValueError("duplicate model/run identity in --run-dir inputs")
        min_models = effective_min_models([run.model for run in runs], args.min_models)
        model_priority = (
            [value.strip() for value in args.model_priority.split(",") if value.strip()]
            if args.model_priority
            else [run.model for run in runs]
        )
        eligible_pages = collect_eligible_pages(
            runs,
            min_models=min_models,
            book_ids=args.book_id,
        )
        summary = summarize_inputs(runs, eligible_pages)
        summary["min_models"] = min_models
        if args.dry_run:
            print(json.dumps(summary, ensure_ascii=False, indent=2))
            return 0
        write_summary = write_agreement_run(
            eligible_pages,
            output_root=args.output_root,
            run_id=args.run_id,
            model_priority=model_priority,
            min_models=min_models,
        )
        print(json.dumps({**summary, **write_summary}, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
