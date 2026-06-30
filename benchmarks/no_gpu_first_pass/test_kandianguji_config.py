from pathlib import Path
import unittest


RUNNER = Path(__file__).with_name("run_kandianguji_api.py").read_text()
MODAL = Path(__file__).with_name("run_kandianguji_modal.sh").read_text()


class KanDianGuJiConfigTest(unittest.TestCase):
    def test_runner_has_configurable_retries_for_unstable_api(self):
        self.assertIn('KANDIANGUJI_MAX_ATTEMPTS', RUNNER)
        self.assertIn('KANDIANGUJI_CURL_MAX_TIME', RUNNER)
        self.assertIn('KANDIANGUJI_RETRY_SLEEP_SECONDS', RUNNER)

    def test_runner_can_continue_after_page_failure(self):
        self.assertIn('KANDIANGUJI_CONTINUE_ON_ERROR', RUNNER)
        self.assertIn('error_path.write_text', RUNNER)
        self.assertIn('"status": "error"', RUNNER)

    def test_modal_wrapper_runs_api_and_scores_results(self):
        self.assertIn('run_kandianguji_api.py', MODAL)
        self.assertIn('score_ocr.py', MODAL)
        self.assertIn('kandianguji/cer_scores.json', MODAL)


if __name__ == "__main__":
    unittest.main()
