from __future__ import annotations

import json
import time
import tempfile
import unittest
from pathlib import Path

from scripts.sentence_separation import (
    SentenceSegment,
    load_manifest_pages,
    segment_text,
    write_sentence_run,
)


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def write_page(run_dir: Path, book_id: str, page_number: int, text: str) -> Path:
    path = run_dir / "pages_text" / book_id / f"page_{page_number:04d}.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def manifest_row(
    run_dir: Path,
    *,
    book_id: str,
    page_number: int,
    status: str = "ok",
) -> dict:
    return {
        "model": "agreement_vote",
        "run_id": "agreement-run",
        "book_id": book_id,
        "source_pdf": None,
        "page_number": page_number,
        "status": status,
        "text_path": str(run_dir / "pages_text" / book_id / f"page_{page_number:04d}.txt"),
        "json_path": str(run_dir / "pages_json" / book_id / f"page_{page_number:04d}.json"),
        "char_count": 1,
        "wall_time_seconds": 0.0,
        "error": None,
    }


class SentenceSeparationTest(unittest.TestCase):
    def test_segment_text_uses_sentence_punctuation_when_present(self):
        segments = segment_text("甲乙。丙丁！戊己？庚辛；壬癸")

        self.assertEqual([segment.text for segment in segments], ["甲乙。", "丙丁！", "戊己？", "庚辛；", "壬癸"])
        self.assertEqual({segment.method for segment in segments}, {"punctuation"})

    def test_segment_text_keeps_closing_quote_after_punctuation(self):
        segments = segment_text("曰：「可。」又行。")

        self.assertEqual([segment.text for segment in segments], ["曰：「可。」", "又行。"])

    def test_segment_text_falls_back_to_non_empty_ocr_lines_without_punctuation(self):
        segments = segment_text("甲乙\n丙丁\n\n戊己")

        self.assertEqual([segment.text for segment in segments], ["甲乙", "丙丁", "戊己"])
        self.assertEqual({segment.method for segment in segments}, {"line_fallback"})

    def test_load_manifest_pages_reads_multiple_agreement_runs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            run_a = root / "run-a"
            run_b = root / "run-b"
            write_page(run_a, "book_1", 1, "甲乙。")
            write_page(run_b, "book_2", 1, "丙丁")
            write_jsonl(run_a / "manifest.jsonl", [manifest_row(run_a, book_id="book_1", page_number=1)])
            write_jsonl(run_b / "manifest.jsonl", [manifest_row(run_b, book_id="book_2", page_number=1)])

            pages = load_manifest_pages([run_a, run_b], repo_root=root)

        self.assertEqual([(page.book_id, page.page_number, page.text) for page in pages], [
            ("book_1", 1, "甲乙。"),
            ("book_2", 1, "丙丁"),
        ])

    def test_write_sentence_run_preserves_page_provenance(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_run = root / "agreement"
            write_page(input_run, "book_1", 1, "甲乙。丙丁")
            write_jsonl(input_run / "manifest.jsonl", [manifest_row(input_run, book_id="book_1", page_number=1)])
            pages = load_manifest_pages([input_run], repo_root=root)

            summary = write_sentence_run(
                pages,
                output_root=root / "sentences",
                run_id="sentence-run",
            )

            page_json = root / "sentences" / "sentence-run" / "sentences_json" / "book_1" / "page_0001.json"
            payload = json.loads(page_json.read_text(encoding="utf-8"))

        self.assertEqual(summary["written_books"], 1)
        self.assertEqual(summary["written_pages"], 1)
        self.assertEqual(summary["written_sentences"], 2)
        self.assertEqual(payload["sentences"][0]["sentence_id"], "book_1-page_0001-s0001")
        self.assertEqual(payload["sentences"][0]["text"], "甲乙。")
        self.assertEqual(payload["sentences"][1]["text"], "丙丁")

    def test_write_sentence_run_with_workers_preserves_manifest_order(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_run = root / "agreement"
            for page_number, text in [(1, "甲乙"), (2, "丙丁"), (3, "戊己")]:
                write_page(input_run, "book_1", page_number, text)
            write_jsonl(
                input_run / "manifest.jsonl",
                [
                    manifest_row(input_run, book_id="book_1", page_number=1),
                    manifest_row(input_run, book_id="book_1", page_number=2),
                    manifest_row(input_run, book_id="book_1", page_number=3),
                ],
            )
            pages = load_manifest_pages([input_run], repo_root=root)

            def delayed_segmenter(text: str) -> list[SentenceSegment]:
                if text == "甲乙":
                    time.sleep(0.03)
                return [SentenceSegment(text, "model")]

            summary = write_sentence_run(
                pages,
                output_root=root / "sentences",
                run_id="sentence-run",
                segmenter=delayed_segmenter,
                max_workers=2,
            )
            rows = [
                json.loads(line)
                for line in (root / "sentences" / "sentence-run" / "manifest.jsonl").read_text(encoding="utf-8").splitlines()
            ]

        self.assertEqual(summary["written_pages"], 3)
        self.assertEqual([row["page_number"] for row in rows], [1, 2, 3])


if __name__ == "__main__":
    unittest.main()
