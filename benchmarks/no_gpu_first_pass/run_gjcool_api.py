import json
import os
import sys
import time
from pathlib import Path

import requests


INPUT_DIR = Path("benchmarks/no_gpu_first_pass/input_images_gjcool_1800")
OUTPUT_DIR = Path("benchmarks/no_gpu_first_pass/output/gjcool")
PAGES = [44, 80, 160, 240, 320]


def load_dotenv(path: Path = Path(".env")) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        print(f"missing required environment variable: {name}", file=sys.stderr)
        sys.exit(2)
    return value


def extract_text(payload):
    if isinstance(payload, dict):
        for key in ("text", "ocr_text", "plain_text", "result", "data"):
            value = payload.get(key)
            if isinstance(value, str):
                return value
        return "\n".join(extract_text(value) for value in payload.values()).strip()
    if isinstance(payload, list):
        return "\n".join(extract_text(value) for value in payload).strip()
    return ""


def selected_pages() -> list[int]:
    value = os.environ.get("GJCOOL_PAGES")
    if not value:
        return PAGES
    return [int(part.strip()) for part in value.split(",") if part.strip()]


def main() -> None:
    load_dotenv()
    base_url = "".join(require_env("GJCOOL_BASE_URL").split()).split("/ocr_mod")[0].rstrip("/")
    access_token = require_env("GJCOOL_ACCESS_TOKEN")
    url = base_url if base_url.endswith("/ocr_pro") else f"{base_url}/ocr_pro"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary = []

    for page_number in selected_pages():
        image_path = INPUT_DIR / f"page_{page_number:03d}.png"
        started = time.perf_counter()
        with image_path.open("rb") as image_file:
            response = requests.post(
                url,
                headers={"Authorization": f"gjcool {access_token}"},
                data={"area": "[]"},
                files={
                    "img": (image_path.name, image_file, "image/png"),
                },
                timeout=600,
            )
        wall_time = time.perf_counter() - started
        response.raise_for_status()
        data = response.json()
        text = extract_text(data)

        json_path = OUTPUT_DIR / f"page_{page_number:03d}.json"
        text_path = OUTPUT_DIR / f"page_{page_number:03d}.txt"
        json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        text_path.write_text(text, encoding="utf-8")
        summary.append(
            {
                "page": page_number,
                "wall_time_seconds": round(wall_time, 3),
                "text_chars": len(text),
                "item_count": data.get("CharNumber"),
                "line_count": data.get("LineNumber"),
                "json": str(json_path),
                "txt": str(text_path),
            }
        )
        (OUTPUT_DIR / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"page_{page_number:03d}: {len(text)} chars, {wall_time:.3f}s", flush=True)

    (OUTPUT_DIR / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
