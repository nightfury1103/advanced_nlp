from __future__ import annotations

import subprocess
from pathlib import Path

import modal


APP_NAME = "advanced-nlp-kandianguji-books-002-003"
VOLUME_NAME = "advanced-nlp-kandianguji-ocr"
RUN_ID = "kandianguji-full-002-003"
REMOTE_ROOT = Path("/root/advanced_nlp")
OUTPUT_ROOT = Path("/mnt/kandianguji-output/ocr_runs")


app = modal.App(APP_NAME)
volume = modal.Volume.from_name(VOLUME_NAME, create_if_missing=True)
ocr_env = {
    "KANDIANGUJI_CURL_MAX_TIME": "300",
    "KANDIANGUJI_MAX_ATTEMPTS": "2",
    "KANDIANGUJI_RETRY_SLEEP_SECONDS": "15",
}

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("curl", "ca-certificates")
    .pip_install("pypdfium2", "pillow")
    .add_local_file("scripts/run_kandianguji_full_ocr.py", str(REMOTE_ROOT / "scripts/run_kandianguji_full_ocr.py"))
    .add_local_file("books/越南汉文燕行文献集成 第2册.pdf", str(REMOTE_ROOT / "books_book2/越南汉文燕行文献集成 第2册.pdf"))
    .add_local_file("books/越南汉文燕行文献集成 第3册.pdf", str(REMOTE_ROOT / "books_book3/越南汉文燕行文献集成 第3册.pdf"))
)


def run_command(command: list[str]) -> None:
    subprocess.run(command, cwd=REMOTE_ROOT, check=True)


def parse_pages(value: str) -> list[int]:
    pages: list[int] = []
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start, end = part.split("-", 1)
            pages.extend(range(int(start), int(end) + 1))
        else:
            pages.append(int(part))
    return pages


def run_pages(books_dir: Path, pages: list[int]) -> None:
    for page in pages:
        run_command(
            [
                "python",
                "scripts/run_kandianguji_full_ocr.py",
                "--books-dir",
                str(books_dir),
                "--output-root",
                str(OUTPUT_ROOT),
                "--run-id",
                RUN_ID,
                "--pages",
                str(page),
                "--image-size",
                "800",
                "--continue-on-error",
            ]
        )
        volume.commit()


@app.function(
    image=image,
    env=ocr_env,
    secrets=[modal.Secret.from_dotenv()],
    volumes={str(OUTPUT_ROOT.parent): volume},
    timeout=60 * 60 * 8,
)
def run_book2_remaining() -> None:
    run_pages(REMOTE_ROOT / "books_book2", parse_pages("37,39-42,45-384"))


@app.function(
    image=image,
    env=ocr_env,
    secrets=[modal.Secret.from_dotenv()],
    volumes={str(OUTPUT_ROOT.parent): volume},
    timeout=60 * 60 * 8,
)
def run_book3_all() -> None:
    run_pages(REMOTE_ROOT / "books_book3", list(range(1, 320)))


@app.local_entrypoint()
def main() -> None:
    book2_call = run_book2_remaining.spawn()
    book3_call = run_book3_all.spawn()
    print(f"Book 2 function call: {book2_call.object_id}")
    print(f"Book 3 function call: {book3_call.object_id}")
    print(f"Modal output volume: {VOLUME_NAME}")
    print(f"Download path: ocr_runs/kandianguji/{RUN_ID}")
