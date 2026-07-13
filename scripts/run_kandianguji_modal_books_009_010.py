from __future__ import annotations

import os
import subprocess
from pathlib import Path

import modal


APP_NAME = "advanced-nlp-kandianguji-books-009-010"
VOLUME_NAME = "advanced-nlp-kandianguji-ocr"
REMOTE_ROOT = Path("/root/advanced_nlp")
VOLUME_ROOT = Path("/mnt/kandianguji-output")
OUTPUT_ROOT = VOLUME_ROOT / "ocr_runs"
BOOKS_ROOT = VOLUME_ROOT / "books"


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
)


def use_second_account() -> None:
    os.environ["KANDIANGUJI_TOKEN"] = os.environ["KANDIANGUJI_TOKEN_2"]
    os.environ["KANDIANGUJI_EMAIL"] = os.environ["KANDIANGUJI_EMAIL_2"]


def run_page(*, books_dir: Path, run_id: str, page: int) -> None:
    subprocess.run(
        [
            "python",
            "scripts/run_kandianguji_full_ocr.py",
            "--books-dir",
            str(books_dir),
            "--output-root",
            str(OUTPUT_ROOT),
            "--run-id",
            run_id,
            "--pages",
            str(page),
            "--image-size",
            "800",
            "--continue-on-error",
        ],
        cwd=REMOTE_ROOT,
        check=True,
    )
    volume.commit()


@app.function(
    image=image,
    env=ocr_env,
    secrets=[modal.Secret.from_dotenv()],
    volumes={str(VOLUME_ROOT): volume},
    timeout=60 * 60 * 8,
)
def run_book9_all() -> None:
    use_second_account()
    books_dir = BOOKS_ROOT / "book9"
    books_dir.mkdir(parents=True, exist_ok=True)
    pdf = BOOKS_ROOT / "越南汉文燕行文献集成 第9册.pdf"
    link = books_dir / pdf.name
    if not link.exists():
        link.symlink_to(pdf)
    for page in range(1, 329):
        run_page(books_dir=books_dir, run_id="kandianguji-full-009", page=page)


@app.function(
    image=image,
    env=ocr_env,
    secrets=[modal.Secret.from_dotenv()],
    volumes={str(VOLUME_ROOT): volume},
    timeout=60 * 60 * 8,
)
def run_book10_all() -> None:
    books_dir = BOOKS_ROOT / "book10"
    books_dir.mkdir(parents=True, exist_ok=True)
    pdf = BOOKS_ROOT / "越南汉文燕行文献集成 第10册.pdf"
    link = books_dir / pdf.name
    if not link.exists():
        link.symlink_to(pdf)
    for page in range(1, 361):
        run_page(books_dir=books_dir, run_id="kandianguji-full-010", page=page)
