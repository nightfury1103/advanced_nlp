from pathlib import Path
import unittest


SCRIPT = Path(__file__).with_name("run_olmocr_gpu.sh").read_text()


class RunOlmocrGpuConfigTest(unittest.TestCase):
    def test_defaults_to_local_venv_when_available(self):
        self.assertIn('if [[ -z "${OLMOCR_BIN:-}" && -x "olmocr-venv/bin/olmocr" ]]', SCRIPT)
        self.assertIn('olmocr_bin="olmocr-venv/bin/olmocr"', SCRIPT)
        self.assertIn('python_bin="olmocr-venv/bin/python"', SCRIPT)

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

    def test_allows_modal_smoke_runs_to_choose_pdf_list(self):
        self.assertIn('if [[ -n "${OLMOCR_PDFS:-}" ]]', SCRIPT)
        self.assertIn('read -r -a pdf_paths <<< "$OLMOCR_PDFS"', SCRIPT)
        self.assertIn('"${pdf_paths[@]}"', SCRIPT)

    def test_allows_wall_clock_timeout_for_cost_control(self):
        self.assertIn('run_timeout="${OLMOCR_TIMEOUT:-0}"', SCRIPT)
        self.assertIn('if [[ "$run_timeout" != "0" ]]', SCRIPT)
        self.assertIn('timeout "$run_timeout"', SCRIPT)

    def test_writes_status_and_reports_missing_markdown(self):
        self.assertIn('status_file="${run_root}/run_status.txt"', SCRIPT)
        self.assertIn('olmocr_exit_code=', SCRIPT)
        self.assertIn('No Markdown outputs were produced', SCRIPT)
        self.assertIn('find "$workspace/markdown" -name', SCRIPT)


if __name__ == "__main__":
    unittest.main()
