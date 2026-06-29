from pathlib import Path

import pypdfium2 as pdfium


PAGES = [5, 20, 44, 52, 80, 160, 240, 320]
SOURCE = Path("sample.pdf")
OUTPUT_DIR = Path("benchmarks/no_gpu_first_pass/input_images")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    doc = pdfium.PdfDocument(str(SOURCE))
    for page_number in PAGES:
        page = doc[page_number - 1]
        bitmap = page.render(scale=2.0)
        image = bitmap.to_pil()
        out_path = OUTPUT_DIR / f"page_{page_number:03d}.png"
        image.save(out_path)
        print(f"{out_path}\t{image.size[0]}x{image.size[1]}")


if __name__ == "__main__":
    main()
