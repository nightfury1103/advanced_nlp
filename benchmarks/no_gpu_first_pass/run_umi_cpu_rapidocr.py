import json
import time
from pathlib import Path

from rapidocr_onnxruntime import RapidOCR


INPUT_DIR = Path("benchmarks/no_gpu_first_pass/input_images")
OUTPUT_DIR = Path("benchmarks/no_gpu_first_pass/output/umi_cpu")
PAGES = [5, 20, 44, 52, 80, 160, 240, 320]


def normalize_item(item):
    box, text, score = item
    return {
        "box": box,
        "text": text,
        "score": score,
    }


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ocr = RapidOCR()
    summary = []

    for page_number in PAGES:
        image_path = INPUT_DIR / f"page_{page_number:03d}.png"
        started = time.perf_counter()
        result, engine_elapsed = ocr(str(image_path))
        wall_time = time.perf_counter() - started
        items = [normalize_item(item) for item in result] if result else []
        text = "\n".join(item["text"] for item in items)

        json_path = OUTPUT_DIR / f"page_{page_number:03d}.json"
        text_path = OUTPUT_DIR / f"page_{page_number:03d}.txt"
        json_path.write_text(
            json.dumps(
                {
                    "page": page_number,
                    "image": str(image_path),
                    "wall_time_seconds": wall_time,
                    "engine_elapsed": engine_elapsed,
                    "item_count": len(items),
                    "items": items,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        text_path.write_text(text, encoding="utf-8")
        summary.append(
            {
                "page": page_number,
                "wall_time_seconds": round(wall_time, 3),
                "item_count": len(items),
                "text_chars": len(text),
                "json": str(json_path),
                "txt": str(text_path),
            }
        )
        print(
            f"page_{page_number:03d}: "
            f"{len(items)} items, {len(text)} chars, {wall_time:.3f}s"
        )

    (OUTPUT_DIR / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
