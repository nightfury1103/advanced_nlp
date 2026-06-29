from pathlib import Path
import unittest


SCRIPT = Path(__file__).with_name("run_olmocr_gpu.sh").read_text()


class RunOlmocrGpuConfigTest(unittest.TestCase):
    def test_adds_olmocr_bin_directory_to_path_for_vllm_subprocess(self):
        self.assertIn('olmocr_bin_dir="$(cd "$(dirname "$olmocr_bin")" && pwd)"', SCRIPT)
        self.assertIn('export PATH="$olmocr_bin_dir:$PATH"', SCRIPT)
        self.assertIn("command -v vllm", SCRIPT)


if __name__ == "__main__":
    unittest.main()
