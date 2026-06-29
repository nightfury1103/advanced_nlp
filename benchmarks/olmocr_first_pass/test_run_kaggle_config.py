from pathlib import Path
import unittest


SCRIPT = Path(__file__).with_name("run_kaggle.sh").read_text()


class RunKaggleConfigTest(unittest.TestCase):
    def test_working_root_is_not_hardcoded_to_kaggle_working(self):
        self.assertNotIn('KAGGLE_WORKING_ROOT:-/kaggle/working', SCRIPT)
        self.assertIn('elif [[ -d /kaggle/working ]]', SCRIPT)
        self.assertIn('working_root="$repo_root"', SCRIPT)


if __name__ == "__main__":
    unittest.main()
