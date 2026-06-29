import unittest

from score_ocr import (
    aggregate_scores,
    aligned_character_error_rate,
    character_error_rate,
    normalize_text,
)


class ScoreOcrTest(unittest.TestCase):
    def test_normalize_text_removes_spaces_and_ascii_punctuation(self):
        self.assertEqual(normalize_text(" 越 南，漢 文\nOCR! "), "越南漢文OCR")

    def test_character_error_rate_counts_insert_delete_substitute(self):
        self.assertEqual(character_error_rate("漢文", "漢文"), 0.0)
        self.assertEqual(character_error_rate("漢文", "漢"), 0.5)
        self.assertEqual(character_error_rate("漢文", "漢字"), 0.5)
        self.assertEqual(character_error_rate("漢文", "漢文字"), 0.5)

    def test_aligned_character_error_rate_ignores_extra_prefix_suffix(self):
        self.assertEqual(aligned_character_error_rate("漢文", "xx漢文yy"), 0.0)
        self.assertEqual(aligned_character_error_rate("漢文", "xx漢字yy"), 0.5)
        self.assertEqual(aligned_character_error_rate("漢文", "xx漢文字符"), 0.0)

    def test_aggregate_scores_uses_weighted_cer_and_timing(self):
        rows = [
            {
                "status": "scored",
                "reference_chars": 10,
                "prediction_chars": 8,
                "edit_distance": 2,
                "aligned_edit_distance": 1,
                "wall_time_seconds": 1.5,
            },
            {
                "status": "scored",
                "reference_chars": 30,
                "prediction_chars": 20,
                "edit_distance": 12,
                "aligned_edit_distance": 5,
                "wall_time_seconds": 2.5,
            },
            {"status": "missing_ground_truth"},
        ]

        self.assertEqual(
            aggregate_scores(rows),
            {
                "scored_pages": 2,
                "missing_ground_truth_pages": 1,
                "missing_prediction_pages": 0,
                "reference_chars": 40,
                "prediction_chars": 28,
                "edit_distance": 14,
                "weighted_cer": 0.35,
                "aligned_edit_distance": 6,
                "weighted_aligned_cer": 0.15,
                "total_wall_time_seconds": 4.0,
                "avg_wall_time_seconds": 2.0,
                "reference_chars_per_second": 10.0,
                "prediction_chars_per_second": 7.0,
                "prediction_reference_char_ratio": 0.7,
            },
        )


if __name__ == "__main__":
    unittest.main()
