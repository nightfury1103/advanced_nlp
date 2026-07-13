from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.jiayan_sentence_separation import (
    JiayanSentenceSegmenter,
    normalize_for_validation,
    write_jiayan_sentence_run,
)
from scripts.sentence_separation import PageText


class FakeSentencizer:
    def __init__(self, outputs: list[list[str]]):
        self.outputs = outputs

    def sentencize(self, text: str) -> list[str]:
        return self.outputs.pop(0)


class JiayanSentenceSeparationTest(unittest.TestCase):
    def test_jiayan_segmenter_uses_sentencizer_when_text_is_preserved(self):
        segmenter = JiayanSentenceSegmenter(sentencizer=FakeSentencizer([["甲乙", "丙丁"]]))

        segments = segmenter.segment_text("甲乙丙丁")

        self.assertEqual([segment.text for segment in segments], ["甲乙", "丙丁"])
        self.assertEqual({segment.method for segment in segments}, {"jiayan_sentencizer"})

    def test_jiayan_segmenter_falls_back_when_text_changes(self):
        segmenter = JiayanSentenceSegmenter(sentencizer=FakeSentencizer([["甲乙。", "丙丁"]]))

        segments = segmenter.segment_text("甲乙丙丁")

        self.assertEqual([segment.text for segment in segments], ["甲乙丙丁"])
        self.assertEqual({segment.method for segment in segments}, {"jiayan_fallback"})

    def test_normalize_for_validation_ignores_whitespace(self):
        self.assertEqual(normalize_for_validation("甲 乙\n丙"), "甲乙丙")

    def test_write_jiayan_sentence_run_records_model_metadata(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_path = root / "page_0001.txt"
            source_path.write_text("甲乙丙丁", encoding="utf-8")
            pages = [
                PageText(
                    input_run_id="agreement-run",
                    input_run_dir=root,
                    book_id="book_1",
                    page_number=1,
                    status="ok",
                    text="甲乙丙丁",
                    text_path=source_path,
                    agreement_ratio=0.9,
                    tie_count=0,
                )
            ]
            segmenter = JiayanSentenceSegmenter(sentencizer=FakeSentencizer([["甲乙", "丙丁"]]))

            summary = write_jiayan_sentence_run(
                pages,
                output_root=root / "sentences",
                run_id="jiayan-run",
                segmenter=segmenter,
            )

            payload_path = root / "sentences" / "jiayan-run" / "sentences_json" / "book_1" / "page_0001.json"
            payload = json.loads(payload_path.read_text(encoding="utf-8"))

        self.assertEqual(summary["written_sentences"], 2)
        self.assertEqual(payload["model"], "jiayan_sentence_separation")
        self.assertEqual(payload["segment_model"], "jiayan_crf_sentencizer")
        self.assertEqual(payload["sentences"][0]["method"], "jiayan_sentencizer")


if __name__ == "__main__":
    unittest.main()
