from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.model_sentence_separation import (
    ModelSentenceSegmenter,
    OpenAICompatibleClient,
    load_dotenv,
    parse_model_sentences,
    write_model_sentence_run,
)
from scripts.sentence_separation import PageText


class FakeClient:
    def __init__(self, responses: list[str]):
        self.responses = responses
        self.requests: list[str] = []

    def complete(self, prompt: str) -> str:
        self.requests.append(prompt)
        return self.responses.pop(0)


class ModelSentenceSeparationTest(unittest.TestCase):
    def test_openai_client_can_disable_response_format_for_vllm(self):
        captured_payloads = []

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return json.dumps(
                    {"choices": [{"message": {"content": '{"sentences":["甲乙"]}'}}]}
                ).encode("utf-8")

        def fake_urlopen(request, timeout):
            captured_payloads.append(json.loads(request.data.decode("utf-8")))
            return FakeResponse()

        client = OpenAICompatibleClient(
            api_key="dummy",
            model="qwen25-14b-awq-sentence",
            base_url="https://modal.example/v1",
            use_response_format=False,
        )

        with patch("urllib.request.urlopen", fake_urlopen):
            response = client.complete("甲乙")

        self.assertEqual(response, '{"sentences":["甲乙"]}')
        self.assertNotIn("response_format", captured_payloads[0])

    def test_load_dotenv_sets_missing_values_without_overwriting_existing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text(
                "MODEL_BASE_URL=https://example.test/v1\n"
                "MODEL_API_KEY=from-file\n",
                encoding="utf-8",
            )
            import os

            old_base = os.environ.get("MODEL_BASE_URL")
            old_key = os.environ.get("MODEL_API_KEY")
            os.environ["MODEL_API_KEY"] = "already-set"
            os.environ.pop("MODEL_BASE_URL", None)
            try:
                load_dotenv(env_path)

                self.assertEqual(os.environ["MODEL_BASE_URL"], "https://example.test/v1")
                self.assertEqual(os.environ["MODEL_API_KEY"], "already-set")
            finally:
                if old_base is None:
                    os.environ.pop("MODEL_BASE_URL", None)
                else:
                    os.environ["MODEL_BASE_URL"] = old_base
                if old_key is None:
                    os.environ.pop("MODEL_API_KEY", None)
                else:
                    os.environ["MODEL_API_KEY"] = old_key

    def test_parse_model_sentences_accepts_json_object(self):
        sentences = parse_model_sentences('{"sentences":["甲乙","丙丁"]}')

        self.assertEqual(sentences, ["甲乙", "丙丁"])

    def test_parse_model_sentences_accepts_fenced_json(self):
        sentences = parse_model_sentences('```json\n{"sentences":["甲乙。","丙丁"]}\n```')

        self.assertEqual(sentences, ["甲乙。", "丙丁"])

    def test_model_segmenter_uses_model_when_segments_cover_input(self):
        segmenter = ModelSentenceSegmenter(
            client=FakeClient(['{"sentences":["甲乙","丙丁"]}']),
            model_name="fake-model",
        )

        segments = segmenter.segment_text("甲乙丙丁")

        self.assertEqual([segment.text for segment in segments], ["甲乙", "丙丁"])
        self.assertEqual({segment.method for segment in segments}, {"model"})

    def test_model_segmenter_falls_back_when_model_changes_text(self):
        segmenter = ModelSentenceSegmenter(
            client=FakeClient(['{"sentences":["甲乙。","丙丁"]}']),
            model_name="fake-model",
        )

        segments = segmenter.segment_text("甲乙丙丁")

        self.assertEqual([segment.text for segment in segments], ["甲乙丙丁"])
        self.assertEqual({segment.method for segment in segments}, {"model_fallback"})

    def test_write_model_sentence_run_records_model_metadata(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_path = root / "page_0001.txt"
            source_path.write_text("甲乙丙丁", encoding="utf-8")
            pages = [
                PageText(
                    input_run_id="agreement-run",
                    input_run_dir=root,
                    book_id="book_1",
                    page_number=1,
                    status="ok",
                    text="甲乙丙丁",
                    text_path=source_path,
                    agreement_ratio=0.9,
                    tie_count=0,
                )
            ]
            segmenter = ModelSentenceSegmenter(
                client=FakeClient(['{"sentences":["甲乙","丙丁"]}']),
                model_name="fake-model",
            )

            summary = write_model_sentence_run(
                pages,
                output_root=root / "sentences",
                run_id="model-sentence-run",
                segmenter=segmenter,
                max_workers=2,
            )

            payload_path = root / "sentences" / "model-sentence-run" / "sentences_json" / "book_1" / "page_0001.json"
            payload = json.loads(payload_path.read_text(encoding="utf-8"))

        self.assertEqual(summary["written_sentences"], 2)
        self.assertEqual(payload["model"], "model_sentence_separation")
        self.assertEqual(payload["segment_model"], "fake-model")
        self.assertEqual(payload["sentences"][0]["method"], "model")
        self.assertEqual(payload["sentences"][0]["segment_model"], "fake-model")


if __name__ == "__main__":
    unittest.main()
