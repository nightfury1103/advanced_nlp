import base64
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path


API_URL = "https://ocr.kandianguji.com/ocr_api"
INPUT_DIR = Path("benchmarks/no_gpu_first_pass/input_images_kandianguji_800")
OUTPUT_DIR = Path("benchmarks/no_gpu_first_pass/output/kandianguji")
PAGES = [44, 80, 160, 240, 320]


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


def extract_text(payload):
    if isinstance(payload, list):
        return "\n".join(str(value) for value in payload).strip()
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, list):
            return "\n".join(str(value) for value in data).strip()
        for key in ("text", "ocr_text", "plain_text", "result"):
            value = payload.get(key)
            if isinstance(value, str):
                return value
        return "\n".join(extract_text(value) for value in payload.values()).strip()
    return ""


def selected_pages() -> list[int]:
    value = os.environ.get("KANDIANGUJI_PAGES")
    if not value:
        return PAGES
    return [int(part.strip()) for part in value.split(",") if part.strip()]


def post_ocr_with_curl(payload: dict[str, str], image_path: Path) -> dict:
    with tempfile.NamedTemporaryFile("w", delete=False) as image_base64_file:
        image_base64_file.write(base64.b64encode(image_path.read_bytes()).decode("ascii"))
        image_base64_path = image_base64_file.name

    command = [
        "curl",
        "-sS",
        "--http1.1",
        "--max-time",
        "240",
        "-X",
        "POST",
        API_URL,
    ]
    for key, value in payload.items():
        command.extend(["-F", f"{key}={value}"])
    command.extend(["-F", f"image=<{image_base64_path}"])

    try:
        last_error = ""
        for attempt in range(1, 3):
            result = subprocess.run(command, capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                return json.loads(result.stdout)
            last_error = result.stderr.strip() or f"curl exited {result.returncode}"
            if attempt < 2:
                time.sleep(10 * attempt)
        raise RuntimeError(last_error)
    finally:
        Path(image_base64_path).unlink(missing_ok=True)


def main() -> None:
    load_dotenv()
    token = require_env("KANDIANGUJI_TOKEN")
    email = require_env("KANDIANGUJI_EMAIL")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary = []

    for page_number in selected_pages():
        image_path = INPUT_DIR / f"page_{page_number:03d}.png"
        payload = {
            "token": token,
            "email": email,
            "version": "v2",
            "image_size": "800",
        }

        started = time.perf_counter()
        data = post_ocr_with_curl(payload, image_path)
        wall_time = time.perf_counter() - started
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
