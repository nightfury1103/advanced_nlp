from __future__ import annotations

import base64
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

import modal


API_URL = "https://ocr.kandianguji.com/ocr_api"
APP_NAME = "advanced-nlp-kandianguji-book-005-probe"
VOLUME_NAME = "advanced-nlp-kandianguji-ocr"
RUN_ID = "kandianguji-quota-probe-005-modal"
REMOTE_ROOT = Path("/root/advanced_nlp")
RUN_ROOT = Path("/mnt/kandianguji-output/ocr_runs/kandianguji") / RUN_ID


app = modal.App(APP_NAME)
volume = modal.Volume.from_name(VOLUME_NAME, create_if_missing=True)

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("curl", "ca-certificates")
    .add_local_file("artifacts/book5_probe/page_0001.png", str(REMOTE_ROOT / "book5_probe/page_0001.png"))
    .add_local_file("artifacts/book5_probe/page_0002.png", str(REMOTE_ROOT / "book5_probe/page_0002.png"))
    .add_local_file("artifacts/book5_probe/page_0003.png", str(REMOTE_ROOT / "book5_probe/page_0003.png"))
    .add_local_file("artifacts/book5_probe/page_0004.png", str(REMOTE_ROOT / "book5_probe/page_0004.png"))
    .add_local_file("artifacts/book5_probe/page_0005.png", str(REMOTE_ROOT / "book5_probe/page_0005.png"))
)


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"missing required environment variable: {name}")
    return value


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
        return "\n".join(value for value in (extract_text(value) for value in payload.values()) if value).strip()
    return ""


def post_image(image_path: Path) -> dict:
    with tempfile.NamedTemporaryFile("w", delete=False) as image_base64_file:
        image_base64_file.write(base64.b64encode(image_path.read_bytes()).decode("ascii"))
        image_base64_path = image_base64_file.name

    command = [
        "curl",
        "-sS",
        "--http1.1",
        "--max-time",
        "180",
        "-X",
        "POST",
        API_URL,
        "-F",
        f"token={require_env('KANDIANGUJI_TOKEN')}",
        "-F",
        f"email={require_env('KANDIANGUJI_EMAIL')}",
        "-F",
        "version=v2",
        "-F",
        "image_size=800",
        "-F",
        f"image=<{image_base64_path}",
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or f"curl exited {result.returncode}")
        if not result.stdout.strip():
            raise RuntimeError("empty API response")
        return json.loads(result.stdout)
    finally:
        Path(image_base64_path).unlink(missing_ok=True)


@app.function(
    image=image,
    secrets=[modal.Secret.from_dotenv()],
    volumes={"/mnt/kandianguji-output": volume},
    timeout=60 * 10,
)
def probe_book5() -> None:
    manifest = RUN_ROOT / "manifest.jsonl"
    book_id = "越南汉文燕行文献集成_第5册"
    for page_number in [3, 4, 5]:
        image_path = REMOTE_ROOT / "book5_probe" / f"page_{page_number:04d}.png"
        started = time.perf_counter()
        text = ""
        error = None
        status = "error"
        json_path = RUN_ROOT / "pages_json" / book_id / f"page_{page_number:04d}.json"
        text_path = RUN_ROOT / "pages_text" / book_id / f"page_{page_number:04d}.txt"
        error_path = RUN_ROOT / "logs" / book_id / f"page_{page_number:04d}.error.txt"
        try:
            data = post_image(image_path)
            text = extract_text(data)
            status = "ok" if text else "blank"
            json_path.parent.mkdir(parents=True, exist_ok=True)
            text_path.parent.mkdir(parents=True, exist_ok=True)
            json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            text_path.write_text(text, encoding="utf-8")
            error_path.unlink(missing_ok=True)
        except Exception as exc:
            error_path.parent.mkdir(parents=True, exist_ok=True)
            error_path.write_text(str(exc), encoding="utf-8")
            error = str(error_path)

        row = {
            "model": "kandianguji",
            "run_id": RUN_ID,
            "book_id": book_id,
            "source_pdf": "books/越南汉文燕行文献集成 第5册.pdf",
            "page_number": page_number,
            "status": status,
            "text_path": str(text_path),
            "json_path": str(json_path),
            "char_count": len(text),
            "wall_time_seconds": round(time.perf_counter() - started, 3),
            "error": error,
        }
        manifest.parent.mkdir(parents=True, exist_ok=True)
        with manifest.open("a", encoding="utf-8") as manifest_file:
            manifest_file.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"{book_id} page_{page_number:04d}: {status} {len(text)} chars {row['wall_time_seconds']:.3f}s", flush=True)
        volume.commit()
