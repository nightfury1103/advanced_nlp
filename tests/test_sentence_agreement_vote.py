from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.sentence_agreement_vote import (
    RUN_LABELS,
    boundary_votes,
    load_sentence_run,
    sentence_agreement_vote,
    write_sentence_agreement_run,
)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_sentence_page(
    run_dir: Path,
    *,
    book_id: str = "book_1",
    page_number: int = 1,
    sentences: list[str],
    source_text: str = "甲乙丙丁戊己",
    model: str = "test_sentence_model",
    run_id: str = "test-run",
) -> None:
    source_path = run_dir / "source" / book_id / f"page_{page_number:04d}.txt"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text(source_text, encoding="utf-8")
    json_path = run_dir / "sentences_json" / book_id / f"page_{page_number:04d}.json"
    text_path = run_dir / "sentences_text" / book_id / f"page_{page_number:04d}.txt"
    payload = {
        "model": model,
        "run_id": run_id,
        "book_id": book_id,
        "page_number": page_number,
        "source_run_id": "source-run",
        "source_text_path": str(source_path),
        "source_status": "ok",
        "sentence_count": len(sentences),
        "sentences": [
            {
                "sentence_id": f"{book_id}-page_{page_number:04d}-s{index:04d}",
                "book_id": book_id,
                "page_number": page_number,
                "sentence_number": index,
                "text": text,
                "method": "test",
            }
            for index, text in enumerate(sentences, start=1)
        ],
    }
    write_json(json_path, payload)
    text_path.parent.mkdir(parents=True, exist_ok=True)
    text_path.write_text("\n".join(sentences), encoding="utf-8")
    row = {
        "model": model,
        "run_id": run_id,
        "book_id": book_id,
        "page_number": page_number,
        "status": "ok" if sentences else "blank",
        "text_path": str(text_path),
        "json_path": str(json_path),
        "sentence_count": len(sentences),
        "source_run_id": "source-run",
        "source_text_path": str(source_path),
        "source_status": "ok",
        "source_agreement_ratio": 0.9,
        "source_tie_count": 0,
    }
    (run_dir / "manifest.jsonl").write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")


class SentenceAgreementVoteTest(unittest.TestCase):
    def test_boundary_votes_keeps_boundaries_with_two_of_three_votes(self):
        result = boundary_votes(
            reference_text="甲乙丙丁戊己",
            sentence_lists={
                "rule": ["甲乙", "丙丁", "戊己"],
                "jiayan": ["甲乙", "丙丁戊己"],
                "qwen": ["甲乙丙丁", "戊己"],
            },
            threshold=2,
        )

        self.assertEqual(result.boundaries, [2, 4])
        self.assertEqual(result.boundary_vote_counts, {2: 2, 4: 2})
        self.assertEqual(set(result.valid_labels), {"rule", "jiayan", "qwen"})

    def test_sentence_agreement_vote_preserves_reference_spacing(self):
        result = sentence_agreement_vote(
            reference_text="甲乙\n丙丁 戊己",
            sentence_lists={
                "rule": ["甲乙", "丙丁 戊己"],
                "jiayan": ["甲乙", "丙丁", "戊己"],
                "qwen": ["甲乙丙丁 戊己"],
            },
            threshold=2,
        )

        self.assertEqual([segment.text for segment in result.segments], ["甲乙", "丙丁 戊己"])
        self.assertEqual(result.method, "agreement_vote")

    def test_load_sentence_run_indexes_pages_from_manifest(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir) / "rule"
            write_sentence_page(run_dir, sentences=["甲乙", "丙丁戊己"])

            run = load_sentence_run(run_dir, label="rule")

        self.assertEqual(run.label, "rule")
        self.assertEqual(list(run.pages), [("book_1", 1)])
        self.assertEqual(run.pages[("book_1", 1)].sentences, ["甲乙", "丙丁戊己"])

    def test_write_sentence_agreement_run_writes_voted_pages(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            run_dirs = []
            for label, sentences in [
                ("rule", ["甲乙", "丙丁", "戊己"]),
                ("jiayan", ["甲乙", "丙丁戊己"]),
                ("qwen", ["甲乙丙丁", "戊己"]),
            ]:
                run_dir = root / label
                write_sentence_page(run_dir, sentences=sentences, run_id=f"{label}-run")
                run_dirs.append(run_dir)

            summary = write_sentence_agreement_run(
                run_dirs=run_dirs,
                labels=RUN_LABELS,
                output_root=root / "agreement",
                run_id="sentence-agreement",
                threshold=2,
                priority_labels=["qwen", "rule", "jiayan"],
            )
            payload_path = root / "agreement" / "sentence-agreement" / "sentences_json" / "book_1" / "page_0001.json"
            payload = json.loads(payload_path.read_text(encoding="utf-8"))

        self.assertEqual(summary["written_pages"], 1)
        self.assertEqual(summary["written_sentences"], 3)
        self.assertEqual(summary["method_counts"], {"agreement_vote": 3})
        self.assertEqual([sentence["text"] for sentence in payload["sentences"]], ["甲乙", "丙丁", "戊己"])
        self.assertEqual(payload["vote_threshold"], 2)
        self.assertEqual(payload["source_run_ids"], {"rule": "rule-run", "jiayan": "jiayan-run", "qwen": "qwen-run"})


if __name__ == "__main__":
    unittest.main()
