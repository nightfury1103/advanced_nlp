from __future__ import annotations

import argparse
import base64
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path


API_URL = "https://ocr.kandianguji.com/ocr_api"
MODEL_NAME = "kandianguji"
DEFAULT_OUTPUT_ROOT = Path("outputs/ocr_runs")
DEFAULT_BOOKS_DIR = Path("books")


@dataclass(frozen=True)
class OutputPaths:
    json_path: Path
    text_path: Path
    error_path: Path


def load_dotenv(path: Path = Path(".env")) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        print(f"missing required environment variable: {name}", file=sys.stderr)
        sys.exit(2)
    return value


def env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    return int(value) if value else default


def book_id_from_path(path: Path) -> str:
    stem = unicodedata.normalize("NFKC", path.stem).strip()
    stem = re.sub(r"\s+", "_", stem)
    stem = re.sub(r"[\\/:\*\?\"<>\|]+", "_", stem)
    stem = re.sub(r"_+", "_", stem).strip("._")
    return stem or "book"


def page_output_paths(run_root: Path, book_id: str, page_number: int) -> OutputPaths:
    filename = f"page_{page_number:04d}"
    return OutputPaths(
        json_path=run_root / "pages_json" / book_id / f"{filename}.json",
        text_path=run_root / "pages_text" / book_id / f"{filename}.txt",
        error_path=run_root / "logs" / book_id / f"{filename}.error.txt",
    )


def extract_text(payload) -> str:
    if isinstance(payload, list):
        return "\n".join(str(value).strip() for value in payload if str(value).strip()).strip()
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, list):
            return extract_text(data)
        for key in ("text", "ocr_text", "plain_text", "result"):
            value = payload.get(key)
            if isinstance(value, str):
                return value.strip()
        return "\n".join(
            value for value in (extract_text(value) for value in payload.values()) if value
        ).strip()
    return ""


def manifest_row(
    *,
    model: str,
    run_id: str,
    book_id: str,
    source_pdf: Path,
    page_number: int,
    status: str,
    text_path: Path | None,
    json_path: Path | None,
    char_count: int,
    wall_time_seconds: float,
    error: str | None,
) -> dict:
    return {
        "model": model,
        "run_id": run_id,
        "book_id": book_id,
        "source_pdf": str(source_pdf),
        "page_number": page_number,
        "status": status,
        "text_path": str(text_path) if text_path else None,
        "json_path": str(json_path) if json_path else None,
        "char_count": char_count,
        "wall_time_seconds": round(wall_time_seconds, 3),
        "error": error,
    }


def append_manifest_row(manifest_path: Path, row: dict) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("a", encoding="utf-8") as manifest_file:
        manifest_file.write(json.dumps(row, ensure_ascii=False) + "\n")


def is_page_complete(paths: OutputPaths) -> bool:
    return paths.text_path.exists()


def assemble_book_text(run_root: Path, book_id: str) -> Path:
    page_dir = run_root / "pages_text" / book_id
    output_path = run_root / "books_text" / f"{book_id}.txt"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    page_paths = sorted(page_dir.glob("page_*.txt"))

    with output_path.open("w", encoding="utf-8") as output_file:
        for page_path in page_paths:
            output_file.write(f"=== {page_path.stem} ===\n")
            output_file.write(page_path.read_text(encoding="utf-8").strip())
            output_file.write("\n")
            if page_path != page_paths[-1]:
                output_file.write("\n")
    return output_path


def parse_pages(value: str | None) -> set[int] | None:
    if not value:
        return None
    pages: set[int] = set()
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start, end = part.split("-", 1)
            pages.update(range(int(start), int(end) + 1))
        else:
            pages.add(int(part))
    return pages


def find_pdfs(books_dir: Path) -> list[Path]:
    return sorted(books_dir.glob("*.pdf"))


def render_page_to_image(pdf_path: Path, page_index: int, output_path: Path, max_side: int) -> None:
    try:
        import pypdfium2 as pdfium
    except ImportError as exc:
        raise RuntimeError(
            "pypdfium2 is required for rendering. Run with: "
            "uv run --with pypdfium2 --with pillow python scripts/run_kandianguji_full_ocr.py"
        ) from exc

    output_path.parent.mkdir(parents=True, exist_ok=True)
    pdf = pdfium.PdfDocument(str(pdf_path))
    try:
        page = pdf[page_index]
        image = page.render(scale=2).to_pil().convert("RGB")
        image.thumbnail((max_side, max_side))
        image.save(output_path, format="PNG", optimize=True)
    finally:
        pdf.close()


def page_count(pdf_path: Path) -> int:
    try:
        import pypdfium2 as pdfium
    except ImportError as exc:
        raise RuntimeError("pypdfium2 is required to count PDF pages") from exc

    pdf = pdfium.PdfDocument(str(pdf_path))
    try:
        return len(pdf)
    finally:
        pdf.close()


def post_ocr_with_curl(payload: dict[str, str], image_path: Path) -> dict:
    with tempfile.NamedTemporaryFile("w", delete=False) as image_base64_file:
        image_base64_file.write(base64.b64encode(image_path.read_bytes()).decode("ascii"))
        image_base64_path = image_base64_file.name

    max_time = str(env_int("KANDIANGUJI_CURL_MAX_TIME", 300))
    max_attempts = env_int("KANDIANGUJI_MAX_ATTEMPTS", 5)
    retry_sleep = env_int("KANDIANGUJI_RETRY_SLEEP_SECONDS", 20)

    command = [
        "curl",
        "-sS",
        "--http1.1",
        "--max-time",
        max_time,
        "-X",
        "POST",
        API_URL,
    ]
    for key, value in payload.items():
        command.extend(["-F", f"{key}={value}"])
    command.extend(["-F", f"image=<{image_base64_path}"])

    try:
        last_error = ""
        for attempt in range(1, max_attempts + 1):
            result = subprocess.run(command, capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                return json.loads(result.stdout)
            last_error = result.stderr.strip() or f"curl exited {result.returncode}"
            if attempt < max_attempts:
                time.sleep(retry_sleep * attempt)
        raise RuntimeError(last_error)
    finally:
        Path(image_base64_path).unlink(missing_ok=True)


def process_page(
    *,
    pdf_path: Path,
    page_number: int,
    book_id: str,
    run_root: Path,
    run_id: str,
    token: str,
    email: str,
    image_size: int,
    force: bool,
    cache_dir: Path,
    keep_cache: bool,
) -> dict:
    paths = page_output_paths(run_root, book_id, page_number)
    if not force and is_page_complete(paths):
        existing_text = paths.text_path.read_text(encoding="utf-8") if paths.text_path.exists() else ""
        return manifest_row(
            model=MODEL_NAME,
            run_id=run_id,
            book_id=book_id,
            source_pdf=pdf_path,
            page_number=page_number,
            status="skipped",
            text_path=paths.text_path,
            json_path=paths.json_path,
            char_count=len(existing_text),
            wall_time_seconds=0.0,
            error=None,
        )

    image_path = cache_dir / book_id / f"page_{page_number:04d}.png"
    started = time.perf_counter()
    try:
        render_page_to_image(pdf_path, page_number - 1, image_path, image_size)
        payload = {
            "token": token,
            "email": email,
            "version": "v2",
            "image_size": str(image_size),
        }
        data = post_ocr_with_curl(payload, image_path)
        text = extract_text(data)
        status = "ok" if text else "blank"

        paths.json_path.parent.mkdir(parents=True, exist_ok=True)
        paths.text_path.parent.mkdir(parents=True, exist_ok=True)
        paths.json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        paths.text_path.write_text(text, encoding="utf-8")
        return manifest_row(
            model=MODEL_NAME,
            run_id=run_id,
            book_id=book_id,
            source_pdf=pdf_path,
            page_number=page_number,
            status=status,
            text_path=paths.text_path,
            json_path=paths.json_path,
            char_count=len(text),
            wall_time_seconds=time.perf_counter() - started,
            error=None,
        )
    except Exception as exc:
        paths.error_path.parent.mkdir(parents=True, exist_ok=True)
        paths.error_path.write_text(str(exc), encoding="utf-8")
        return manifest_row(
            model=MODEL_NAME,
            run_id=run_id,
            book_id=book_id,
            source_pdf=pdf_path,
            page_number=page_number,
            status="error",
            text_path=paths.text_path,
            json_path=paths.json_path,
            char_count=0,
            wall_time_seconds=time.perf_counter() - started,
            error=str(paths.error_path),
        )
    finally:
        if not keep_cache:
            image_path.unlink(missing_ok=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run full-book KanDianGuJi OCR and write voting-ready page outputs."
    )
    parser.add_argument("--books-dir", type=Path, default=DEFAULT_BOOKS_DIR)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--run-id", default=time.strftime("kandianguji-full-%Y%m%d-%H%M%S"))
    parser.add_argument("--pages", help="Optional pages to run, e.g. 1,3,10-20")
    parser.add_argument("--image-size", type=int, default=800)
    parser.add_argument("--force", action="store_true", help="Re-run pages even if output exists")
    parser.add_argument("--keep-cache", action="store_true", help="Keep rendered upload images")
    parser.add_argument(
        "--continue-on-error",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Continue after page errors and record them in the manifest",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    load_dotenv()
    token = require_env("KANDIANGUJI_TOKEN")
    email = require_env("KANDIANGUJI_EMAIL")

    pdfs = find_pdfs(args.books_dir)
    if not pdfs:
        print(f"no PDFs found in {args.books_dir}", file=sys.stderr)
        return 2

    run_root = args.output_root / MODEL_NAME / args.run_id
    manifest_path = run_root / "manifest.jsonl"
    cache_dir = run_root / "cache"
    selected_pages = parse_pages(args.pages)
    run_root.mkdir(parents=True, exist_ok=True)

    for pdf_path in pdfs:
        book_id = book_id_from_path(pdf_path)
        total_pages = page_count(pdf_path)
        pages = selected_pages or set(range(1, total_pages + 1))
        for page_number in sorted(page for page in pages if 1 <= page <= total_pages):
            row = process_page(
                pdf_path=pdf_path,
                page_number=page_number,
                book_id=book_id,
                run_root=run_root,
                run_id=args.run_id,
                token=token,
                email=email,
                image_size=args.image_size,
                force=args.force,
                cache_dir=cache_dir,
                keep_cache=args.keep_cache,
            )
            append_manifest_row(manifest_path, row)
            print(
                f"{book_id} page_{page_number:04d}: "
                f"{row['status']} {row['char_count']} chars {row['wall_time_seconds']:.3f}s",
                flush=True,
            )
            if row["status"] == "error" and not args.continue_on_error:
                return 1
        assemble_book_text(run_root, book_id)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
