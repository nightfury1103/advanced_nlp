from pathlib import Path
import unittest


SCRIPT = Path(__file__).with_name("run_kaggle.sh").read_text()


class RunKaggleConfigTest(unittest.TestCase):
    def test_working_root_is_not_hardcoded_to_kaggle_working(self):
        self.assertNotIn('KAGGLE_WORKING_ROOT:-/kaggle/working', SCRIPT)
        self.assertIn('elif [[ -d /kaggle/working ]]', SCRIPT)
        self.assertIn('working_root="$repo_root"', SCRIPT)

    def test_runs_preflight_before_downloading_model(self):
        preflight_index = SCRIPT.index("Running cheap vLLM/Triton linker preflight")
        download_index = SCRIPT.index("Pre-downloading model outside benchmark timing")
        self.assertLess(preflight_index, download_index)
        self.assertIn('OLMOCR_PREFLIGHT_ONLY=1', SCRIPT)

    def test_installs_build_tools_and_python_headers_for_triton(self):
        self.assertIn("build-essential", SCRIPT)
        self.assertIn("python3-dev", SCRIPT)
        self.assertIn("python3.11-dev", SCRIPT)


if __name__ == "__main__":
    unittest.main()
