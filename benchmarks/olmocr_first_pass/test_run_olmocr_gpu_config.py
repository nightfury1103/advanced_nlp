from pathlib import Path
import unittest


SCRIPT = Path(__file__).with_name("run_olmocr_gpu.sh").read_text()


class RunOlmocrGpuConfigTest(unittest.TestCase):
    def test_validates_explicit_executable_paths_before_cd(self):
        self.assertIn("resolve_executable()", SCRIPT)
        self.assertIn('does not exist or is not executable', SCRIPT)
        self.assertIn('If this is a fresh Modal session', SCRIPT)
        self.assertLess(SCRIPT.index('olmocr_bin="$(resolve_executable'), SCRIPT.index('olmocr_bin_dir='))

    def test_adds_olmocr_bin_directory_to_path_for_vllm_subprocess(self):
        self.assertIn('olmocr_bin_dir="$(cd "$(dirname "$olmocr_bin")" && pwd)"', SCRIPT)
        self.assertIn('export PATH="$olmocr_bin_dir:$PATH"', SCRIPT)
        self.assertIn("command -v vllm", SCRIPT)

    def test_exposes_unversioned_libcuda_for_triton_linker(self):
        self.assertIn('cuda_link_dir="${run_root}/cuda-link"', SCRIPT)
        self.assertIn('ln -sf "$libcuda_path" "${cuda_link_dir}/libcuda.so"', SCRIPT)
        self.assertIn('export LIBRARY_PATH="${cuda_link_dir}', SCRIPT)
        self.assertIn('export LD_LIBRARY_PATH="${cuda_link_dir}', SCRIPT)

    def test_has_cheap_preflight_mode_before_model_run(self):
        self.assertIn('preflight_only="${OLMOCR_PREFLIGHT_ONLY:-0}"', SCRIPT)
        self.assertIn("python_include=", SCRIPT)
        self.assertIn("#include <Python.h>", SCRIPT)
        self.assertIn('gcc "${cuda_link_dir}/cuda_link_check.c"', SCRIPT)
        self.assertIn('if [[ "$preflight_only" == "1" ]]', SCRIPT)
        self.assertIn("olmOCR GPU preflight complete", SCRIPT)


if __name__ == "__main__":
    unittest.main()
