import tempfile
import unittest
from pathlib import Path

from agreement_ocr import (
    aligned_pair_agreement,
    score_pair,
    strict_pair_agreement,
)


class AgreementOcrTest(unittest.TestCase):
    def test_strict_agreement_penalizes_extra_text(self):
        result = strict_pair_agreement("漢文", "漢文字")

        self.assertEqual(result["edit_distance"], 1)
        self.assertEqual(result["denominator"], 3)
        self.assertEqual(result["agreement"], 0.6667)

    def test_aligned_agreement_ignores_extra_prefix_or_suffix(self):
        result = aligned_pair_agreement("漢文", "題漢文頁")

        self.assertEqual(result["edit_distance"], 0)
        self.assertEqual(result["denominator"], 2)
        self.assertEqual(result["agreement"], 1.0)

    def test_score_pair_uses_only_pages_present_for_both_models(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            model_a = root / "model_a"
            model_b = root / "model_b"
            model_a.mkdir()
            model_b.mkdir()
            (model_a / "page_044.txt").write_text("甲乙", encoding="utf-8")
            (model_a / "page_080.txt").write_text("漢文", encoding="utf-8")
            (model_b / "page_080.txt").write_text("漢文字", encoding="utf-8")

            row = score_pair("model_a", model_a, "model_b", model_b, [44, 80])

        self.assertEqual(row["model_a"], "model_a")
        self.assertEqual(row["model_b"], "model_b")
        self.assertEqual(row["pages"], [80])
        self.assertEqual(row["page_count"], 1)
        self.assertEqual(row["strict_agreement"], 0.6667)
        self.assertEqual(row["aligned_agreement"], 1.0)


if __name__ == "__main__":
    unittest.main()
