from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from scripts.parallel_alignment import (
    AlignmentStep,
    align_embeddings,
    confidence_for,
    load_pairs,
    load_sentences,
    write_alignment_run,
)


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


class ParallelAlignmentTest(unittest.TestCase):
    def test_align_embeddings_keeps_order_and_detects_many_to_one(self):
        steps = align_embeddings(
            np.asarray([[1, 0], [1, 0], [0, 1]], dtype=np.float32),
            np.asarray([[1, 0], [0, 1]], dtype=np.float32),
        )

        self.assertEqual([(step.relation, step.source_indices, step.target_indices) for step in steps], [
            ("2-1", (0, 1), (0,)),
            ("1-1", (2,), (1,)),
        ])

    def test_align_embeddings_leaves_low_similarity_sentences_unmatched(self):
        steps = align_embeddings(
            np.asarray([[1, 0]], dtype=np.float32),
            np.asarray([[0, 1]], dtype=np.float32),
        )

        self.assertEqual([step.relation for step in steps], ["0-1", "1-0"])
        self.assertEqual(confidence_for(steps[0]), ("unmatched", True))

    def test_loaders_validate_and_resolve_relative_pair_paths(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.jsonl"
            target = root / "target.jsonl"
            manifest = root / "pairs.jsonl"
            write_jsonl(source, [{"sentence_id": "han-1", "text": "甲"}])
            write_jsonl(target, [{"sentence_id": "vi-1", "text": "A"}])
            write_jsonl(manifest, [{"pair_id": "book-1", "source_path": "source.jsonl", "target_path": "target.jsonl"}])

            pair = load_pairs(manifest)[0]
            sentences = load_sentences(pair.source_path)

        self.assertEqual(pair.source_path, source)
        self.assertEqual(sentences[0].sentence_id, "han-1")

    def test_write_alignment_run_preserves_both_sides_and_review_flag(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.jsonl"
            target = root / "target.jsonl"
            manifest = root / "pairs.jsonl"
            write_jsonl(source, [
                {"sentence_id": "han-1", "text": "甲"},
                {"sentence_id": "han-2", "text": "乙"},
            ])
            write_jsonl(target, [{"sentence_id": "vi-1", "text": "A B"}])
            write_jsonl(manifest, [{"pair_id": "book-1", "source_path": "source.jsonl", "target_path": "target.jsonl"}])

            with patch(
                "scripts.parallel_alignment.embed_sentences",
                side_effect=[
                    np.asarray([[1, 0], [1, 0]], dtype=np.float32),
                    np.asarray([[1, 0]], dtype=np.float32),
                ],
            ):
                summary = write_alignment_run(
                    pairs=load_pairs(manifest),
                    output_root=root / "out",
                    run_id="test-run",
                    embedding_model="test-embedding",
                    batch_size=2,
                    device=None,
                    min_match_score=0.35,
                    expansion_penalty=0.02,
                    skip_penalty=0.35,
                )
            rows = [
                json.loads(line)
                for line in (root / "out" / "test-run" / "alignments" / "book-1.jsonl").read_text(encoding="utf-8").splitlines()
            ]

        self.assertEqual(summary["written_pairs"], 1)
        self.assertEqual(rows[0]["relation"], "2-1")
        self.assertEqual(rows[0]["source_sentence_ids"], ["han-1", "han-2"])
        self.assertEqual(rows[0]["target_sentence_ids"], ["vi-1"])
        self.assertTrue(rows[0]["review_required"])


if __name__ == "__main__":
    unittest.main()
