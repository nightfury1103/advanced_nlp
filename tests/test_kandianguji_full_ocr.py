import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.run_kandianguji_full_ocr import (
    OutputPaths,
    append_manifest_row,
    assemble_book_text,
    book_id_from_path,
    extract_text,
    is_page_complete,
    manifest_row,
    page_output_paths,
)


class KanDianGuJiFullOcrTest(unittest.TestCase):
    def test_book_id_from_path_keeps_readable_unicode_and_normalizes_spaces(self):
        self.assertEqual(
            book_id_from_path(Path("books/越南汉文燕行文献集成 第1册-1.pdf")),
            "越南汉文燕行文献集成_第1册-1",
        )

    def test_page_output_paths_follow_model_neutral_layout(self):
        root = Path("outputs/ocr_runs/kandianguji/run-a")

        paths = page_output_paths(root, "book_a", 12)

        self.assertEqual(
            paths,
            OutputPaths(
                json_path=root / "pages_json" / "book_a" / "page_0012.json",
                text_path=root / "pages_text" / "book_a" / "page_0012.txt",
                error_path=root / "logs" / "book_a" / "page_0012.error.txt",
            ),
        )

    def test_extract_text_joins_kandianguji_data_lines(self):
        payload = {
            "data": ["三疊山", "行人三疊唱陽關", ""],
            "id": "abc",
            "message": "success",
        }

        self.assertEqual(extract_text(payload), "三疊山\n行人三疊唱陽關")

    def test_manifest_row_contains_voting_ready_fields(self):
        row = manifest_row(
            model="kandianguji",
            run_id="run-a",
            book_id="book_a",
            source_pdf=Path("books/book a.pdf"),
            page_number=3,
            status="ok",
            text_path=Path("outputs/text.txt"),
            json_path=Path("outputs/raw.json"),
            char_count=42,
            wall_time_seconds=1.23456,
            error=None,
        )

        self.assertEqual(
            row,
            {
                "model": "kandianguji",
                "run_id": "run-a",
                "book_id": "book_a",
                "source_pdf": "books/book a.pdf",
                "page_number": 3,
                "status": "ok",
                "text_path": "outputs/text.txt",
                "json_path": "outputs/raw.json",
                "char_count": 42,
                "wall_time_seconds": 1.235,
                "error": None,
            },
        )

    def test_append_manifest_row_writes_jsonl(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest = Path(temp_dir) / "manifest.jsonl"
            row = {"page_number": 1, "status": "ok"}

            append_manifest_row(manifest, row)
            append_manifest_row(manifest, {"page_number": 2, "status": "blank"})

            self.assertEqual(
                [json.loads(line) for line in manifest.read_text(encoding="utf-8").splitlines()],
                [row, {"page_number": 2, "status": "blank"}],
            )

    def test_is_page_complete_requires_text_output_for_voting(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = page_output_paths(root, "book_a", 1)
            self.assertFalse(is_page_complete(paths))

            paths.json_path.parent.mkdir(parents=True)
            paths.json_path.write_text("{}", encoding="utf-8")
            self.assertFalse(is_page_complete(paths))

            paths.text_path.parent.mkdir(parents=True)
            paths.text_path.write_text("done", encoding="utf-8")
            self.assertTrue(is_page_complete(paths))

    def test_assemble_book_text_orders_pages_with_markers(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            page_2 = page_output_paths(root, "book_a", 2)
            page_1 = page_output_paths(root, "book_a", 1)
            page_2.text_path.parent.mkdir(parents=True)
            page_2.text_path.write_text("second", encoding="utf-8")
            page_1.text_path.write_text("first", encoding="utf-8")

            output_path = assemble_book_text(root, "book_a")

            self.assertEqual(output_path, root / "books_text" / "book_a.txt")
            self.assertEqual(
                output_path.read_text(encoding="utf-8"),
                "=== page_0001 ===\nfirst\n\n=== page_0002 ===\nsecond\n",
            )


if __name__ == "__main__":
    unittest.main()
