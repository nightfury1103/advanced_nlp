import json
import re
import shutil
import sys
from pathlib import Path


PAGES = [44, 80, 160, 240, 320]


def read_real_seconds(path: Path) -> float:
    match = re.search(r"^real\s+([0-9.]+)$", path.read_text(encoding="utf-8"), re.MULTILINE)
    if not match:
        raise RuntimeError(f"Missing real time in {path}")
    return float(match.group(1))


def find_markdown(markdown_root: Path, page: int) -> Path:
    matches = list(markdown_root.rglob(f"page_{page:03d}.md"))
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected one Markdown output for page {page:03d}, found {len(matches)}"
        )
    return matches[0]


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: prepare_olmocr_results.py RUN_ROOT")

    run_root = Path(sys.argv[1])
    markdown_root = run_root / "workspace" / "markdown"
    text_dir = run_root / "text"
    text_dir.mkdir(parents=True, exist_ok=True)

    total_seconds = read_real_seconds(run_root / "olmocr_timing.txt")
    average_seconds = total_seconds / len(PAGES)
    summary = []

    for page in PAGES:
        source = find_markdown(markdown_root, page)
        target = text_dir / f"page_{page:03d}.txt"
        shutil.copyfile(source, target)
        text = target.read_text(encoding="utf-8")
        summary.append(
            {
                "page": page,
                "wall_time_seconds": round(average_seconds, 3),
                "timing_estimated": True,
                "timing_scope": "equal share of end-to-end batch wall time",
                "text_chars": len(text),
                "json": None,
                "txt": str(target),
            }
        )

    (text_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (run_root / "benchmark_meta.json").write_text(
        json.dumps(
            {
                "pages": PAGES,
                "end_to_end_wall_time_seconds": total_seconds,
                "average_wall_time_seconds_per_page": average_seconds,
                "timing_includes_model_startup": True,
                "timing_excludes_model_download_only_if_precached": True,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Prepared text outputs in {text_dir}")


if __name__ == "__main__":
    main()
