import json
import re
import shutil
import sys
from pathlib import Path


def read_real_seconds(path: Path) -> float:
    match = re.search(r"^real\s+([0-9.]+)$", path.read_text(encoding="utf-8"), re.MULTILINE)
    if not match:
        raise RuntimeError(f"Missing real time in {path}")
    return float(match.group(1))


def discover_markdown_outputs(markdown_root: Path) -> list[tuple[int, Path]]:
    outputs = []
    by_page = {}
    for source in markdown_root.rglob("page_*.md"):
        match = re.fullmatch(r"page_(\d+)\.md", source.name)
        if not match:
            continue
        page = int(match.group(1))
        by_page.setdefault(page, []).append(source)

    for page, matches in sorted(by_page.items()):
        if len(matches) != 1:
            raise RuntimeError(
                f"Expected one Markdown output for page {page:03d}, found {len(matches)}"
            )
        outputs.append((page, matches[0]))

    if not outputs:
        raise RuntimeError(f"No Markdown outputs found under {markdown_root}")
    return outputs


def prepare_run(run_root: Path) -> None:
    markdown_root = run_root / "workspace" / "markdown"
    text_dir = run_root / "text"
    text_dir.mkdir(parents=True, exist_ok=True)

    markdown_outputs = discover_markdown_outputs(markdown_root)
    total_seconds = read_real_seconds(run_root / "olmocr_timing.txt")
    average_seconds = total_seconds / len(markdown_outputs)
    summary = []

    for page, source in markdown_outputs:
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

    pages = [page for page, _ in markdown_outputs]
    (text_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (run_root / "benchmark_meta.json").write_text(
        json.dumps(
            {
                "pages": pages,
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


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: prepare_olmocr_results.py RUN_ROOT")

    prepare_run(Path(sys.argv[1]))


if __name__ == "__main__":
    main()
