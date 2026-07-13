from __future__ import annotations

import subprocess
from pathlib import Path

import modal


APP_NAME = "advanced-nlp-kandianguji-book-004"
VOLUME_NAME = "advanced-nlp-kandianguji-ocr"
RUN_ID = "kandianguji-full-004"
REMOTE_ROOT = Path("/root/advanced_nlp")
OUTPUT_ROOT = Path("/mnt/kandianguji-output/ocr_runs")
BOOK_DIR = REMOTE_ROOT / "books_book4"


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
    .add_local_file("books/越南汉文燕行文献集成 第4册.pdf", str(BOOK_DIR / "越南汉文燕行文献集成 第4册.pdf"))
)


def run_page(page: int) -> None:
    subprocess.run(
        [
            "python",
            "scripts/run_kandianguji_full_ocr.py",
            "--books-dir",
            str(BOOK_DIR),
            "--output-root",
            str(OUTPUT_ROOT),
            "--run-id",
            RUN_ID,
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
    volumes={str(OUTPUT_ROOT.parent): volume},
    timeout=60 * 60 * 8,
)
def run_book4_all() -> None:
    for page in range(1, 369):
        run_page(page)

