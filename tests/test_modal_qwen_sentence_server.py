from __future__ import annotations

import unittest

from scripts.modal_qwen_sentence_server import (
    DEFAULT_MODEL_NAME,
    SERVED_MODEL_NAME,
    build_vllm_command,
    modal_python_packages,
)


class ModalQwenSentenceServerTest(unittest.TestCase):
    def test_build_vllm_command_serves_qwen_awq_with_openai_api(self):
        command = build_vllm_command(api_key="test-key")

        self.assertEqual(command[:3], ["python", "-m", "vllm.entrypoints.openai.api_server"])
        self.assertIn(DEFAULT_MODEL_NAME, command)
        self.assertIn(SERVED_MODEL_NAME, command)
        self.assertIn("--api-key", command)
        self.assertIn("test-key", command)

    def test_build_vllm_command_can_run_without_api_key(self):
        command = build_vllm_command(api_key="")

        self.assertNotIn("--api-key", command)
        self.assertIn("--quantization", command)
        self.assertIn("awq", command)

    def test_build_vllm_command_uses_outlines_guided_decoding(self):
        command = build_vllm_command()

        self.assertIn("--guided-decoding-backend", command)
        backend_index = command.index("--guided-decoding-backend") + 1
        self.assertEqual(command[backend_index], "outlines")

    def test_modal_image_pins_transformers_below_next_major(self):
        packages = modal_python_packages()

        self.assertIn("vllm==0.6.6.post1", packages)
        self.assertIn("transformers==4.47.1", packages)
        self.assertNotIn("transformers>=4.47.0", packages)


if __name__ == "__main__":
    unittest.main()
