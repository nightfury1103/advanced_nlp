import json
import tempfile
from pathlib import Path
import unittest

from benchmarks.olmocr_first_pass import prepare_olmocr_results


class PrepareOlmocrResultsTest(unittest.TestCase):
    def test_prepares_only_markdown_pages_present_in_run(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            run_root = Path(tmpdir)
            markdown_dir = run_root / "workspace" / "markdown" / "doc"
            markdown_dir.mkdir(parents=True)
            (markdown_dir / "page_080.md").write_text("recognized text", encoding="utf-8")
            (run_root / "olmocr_timing.txt").write_text("real 12.0\n", encoding="utf-8")

            prepare_olmocr_results.prepare_run(run_root)

            self.assertEqual(
                (run_root / "text" / "page_080.txt").read_text(encoding="utf-8"),
                "recognized text",
            )
            summary = json.loads(
                (run_root / "text" / "summary.json").read_text(encoding="utf-8")
            )
            self.assertEqual([item["page"] for item in summary], [80])
            self.assertEqual(summary[0]["wall_time_seconds"], 12.0)

    def test_fails_when_no_markdown_outputs_exist(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            run_root = Path(tmpdir)
            (run_root / "workspace" / "markdown").mkdir(parents=True)
            (run_root / "olmocr_timing.txt").write_text("real 12.0\n", encoding="utf-8")

            with self.assertRaisesRegex(RuntimeError, "No Markdown outputs found"):
                prepare_olmocr_results.prepare_run(run_root)


if __name__ == "__main__":
    unittest.main()
