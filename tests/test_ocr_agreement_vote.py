from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.ocr_agreement_vote import (
    PageCandidate,
    collect_eligible_pages,
    effective_min_models,
    load_ocr_run,
    parse_args,
    vote_text,
    write_agreement_run,
)


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def write_page(run_dir: Path, book_id: str, page_number: int, text: str) -> Path:
    path = run_dir / "pages_text" / book_id / f"page_{page_number:04d}.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def manifest_row(
    run_dir: Path,
    *,
    model: str = "model_a",
    run_id: str = "run-a",
    book_id: str = "book_a",
    page_number: int = 1,
    status: str = "ok",
    text_path: str | None = None,
) -> dict:
    if text_path is None:
        text_path = str(run_dir / "pages_text" / book_id / f"page_{page_number:04d}.txt")
    return {
        "model": model,
        "run_id": run_id,
        "book_id": book_id,
        "source_pdf": f"books/{book_id}.pdf",
        "page_number": page_number,
        "status": status,
        "text_path": text_path,
        "json_path": str(run_dir / "pages_json" / book_id / f"page_{page_number:04d}.json"),
        "char_count": 1,
        "wall_time_seconds": 0.1,
        "error": None,
    }


class OcrAgreementVoteTest(unittest.TestCase):
    def test_load_ocr_run_prefers_latest_non_skipped_row(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir) / "model_a" / "run-a"
            write_page(run_dir, "book_a", 1, "甲")
            write_jsonl(
                run_dir / "manifest.jsonl",
                [
                    manifest_row(run_dir, page_number=1, status="ok"),
                    manifest_row(run_dir, page_number=1, status="skipped"),
                ],
            )

            run = load_ocr_run(run_dir, Path(temp_dir))

        self.assertEqual(run.model, "model_a")
        self.assertEqual(run.run_id, "run-a")
        self.assertEqual(run.pages[("book_a", 1)].status, "ok")
        self.assertEqual(run.pages[("book_a", 1)].text, "甲")

    def test_load_ocr_run_uses_skipped_row_when_it_is_the_only_row(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir) / "model_a" / "run-a"
            write_page(run_dir, "book_a", 2, "乙")
            write_jsonl(
                run_dir / "manifest.jsonl",
                [manifest_row(run_dir, page_number=2, status="skipped")],
            )

            run = load_ocr_run(run_dir, Path(temp_dir))

        self.assertEqual(run.pages[("book_a", 2)].status, "skipped")
        self.assertEqual(run.pages[("book_a", 2)].text, "乙")

    def test_load_ocr_run_excludes_page_when_latest_non_skipped_row_is_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir) / "model_a" / "run-a"
            write_page(run_dir, "book_a", 1, "甲")
            write_jsonl(
                run_dir / "manifest.jsonl",
                [
                    manifest_row(run_dir, page_number=1, status="ok"),
                    manifest_row(run_dir, page_number=1, status="error"),
                ],
            )

            run = load_ocr_run(run_dir, Path(temp_dir))

        self.assertNotIn(("book_a", 1), run.pages)

    def test_load_ocr_run_falls_back_from_remote_manifest_path_to_run_layout(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir) / "model_a" / "run-a"
            write_page(run_dir, "book_a", 3, "丙")
            write_jsonl(
                run_dir / "manifest.jsonl",
                [
                    manifest_row(
                        run_dir,
                        page_number=3,
                        text_path="/mnt/remote/ocr_runs/model_a/run-a/pages_text/book_a/page_0003.txt",
                    )
                ],
            )

            run = load_ocr_run(run_dir, Path(temp_dir))

        self.assertEqual(run.pages[("book_a", 3)].text, "丙")

    def test_load_ocr_run_resolves_book_id_alias_after_manifest_rename(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir) / "model_a" / "run-a"
            original_book_id = "越南汉文燕行文献集成_第1册"
            renamed_book_id = "越南汉文燕行文献集成_第1册-1"
            write_page(run_dir, original_book_id, 1, "丁")
            write_jsonl(
                run_dir / "manifest.jsonl",
                [
                    manifest_row(
                        run_dir,
                        book_id=renamed_book_id,
                        page_number=1,
                        text_path="formated_output/ocr_runs/model_a/run-a/pages_text/"
                        f"{renamed_book_id}/page_0001.txt",
                    )
                ],
            )

            run = load_ocr_run(run_dir, Path(temp_dir))

        self.assertEqual(run.pages[(renamed_book_id, 1)].text, "丁")

    def test_collect_eligible_pages_requires_minimum_model_count(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            run_a = root / "model_a" / "run-a"
            run_b = root / "model_b" / "run-b"
            write_page(run_a, "book_a", 1, "甲")
            write_page(run_a, "book_a", 2, "乙")
            write_page(run_b, "book_a", 1, "甲")
            write_jsonl(run_a / "manifest.jsonl", [
                manifest_row(run_a, model="model_a", run_id="run-a", page_number=1),
                manifest_row(run_a, model="model_a", run_id="run-a", page_number=2),
            ])
            write_jsonl(run_b / "manifest.jsonl", [
                manifest_row(run_b, model="model_b", run_id="run-b", page_number=1),
            ])

            pages = collect_eligible_pages(
                [load_ocr_run(run_a, root), load_ocr_run(run_b, root)],
                min_models=2,
                book_ids=None,
            )

        self.assertEqual(list(pages), [("book_a", 1)])
        self.assertEqual([candidate.model for candidate in pages[("book_a", 1)]], ["model_a", "model_b"])

    def test_collect_eligible_pages_groups_book_id_aliases(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            run_a = root / "model_a" / "run-a"
            run_b = root / "model_b" / "run-b"
            write_page(run_a, "越南汉文燕行文献集成_第1册", 1, "甲")
            write_page(run_b, "越南汉文燕行文献集成_第1册-1", 1, "甲")
            write_jsonl(run_a / "manifest.jsonl", [
                manifest_row(
                    run_a,
                    model="model_a",
                    run_id="run-a",
                    book_id="越南汉文燕行文献集成_第1册",
                    page_number=1,
                ),
            ])
            write_jsonl(run_b / "manifest.jsonl", [
                manifest_row(
                    run_b,
                    model="model_b",
                    run_id="run-b",
                    book_id="越南汉文燕行文献集成_第1册-1",
                    page_number=1,
                ),
            ])

            pages = collect_eligible_pages(
                [load_ocr_run(run_a, root), load_ocr_run(run_b, root)],
                min_models=2,
                book_ids=None,
            )

        self.assertEqual(list(pages), [("越南汉文燕行文献集成_第1册", 1)])
        self.assertEqual([candidate.book_id for candidate in pages[("越南汉文燕行文献集成_第1册", 1)]], [
            "越南汉文燕行文献集成_第1册",
            "越南汉文燕行文献集成_第1册-1",
        ])

    def test_vote_text_uses_character_majority(self):
        result = vote_text(
            [
                PageCandidate("model_a", "run-a", "book_a", 1, "漢文", "ok", Path("a.txt")),
                PageCandidate("model_b", "run-b", "book_a", 1, "漢字", "ok", Path("b.txt")),
                PageCandidate("model_c", "run-c", "book_a", 1, "漢文", "ok", Path("c.txt")),
            ],
            model_priority=["model_a", "model_b", "model_c"],
        )

        self.assertEqual(result.text, "漢文")
        self.assertEqual(result.tie_count, 0)
        self.assertEqual(result.position_count, 2)
        self.assertEqual(result.unanimous_count, 1)

    def test_vote_text_uses_model_priority_for_ties(self):
        result = vote_text(
            [
                PageCandidate("model_a", "run-a", "book_a", 1, "甲", "ok", Path("a.txt")),
                PageCandidate("model_b", "run-b", "book_a", 1, "乙", "ok", Path("b.txt")),
            ],
            model_priority=["model_b", "model_a"],
        )

        self.assertEqual(result.text, "乙")
        self.assertEqual(result.tie_count, 1)

    def test_vote_text_drops_inserted_character_without_majority_support(self):
        result = vote_text(
            [
                PageCandidate("model_a", "run-a", "book_a", 1, "甲丙丁", "ok", Path("a.txt")),
                PageCandidate("model_b", "run-b", "book_a", 1, "甲乙丙", "ok", Path("b.txt")),
                PageCandidate("model_c", "run-c", "book_a", 1, "甲乙丙", "ok", Path("c.txt")),
            ],
            model_priority=["model_a", "model_b", "model_c"],
        )

        self.assertEqual(result.text, "甲乙丙")
        self.assertEqual(result.position_count, 3)

    def test_vote_text_drops_text_supported_by_less_than_majority(self):
        result = vote_text(
            [
                PageCandidate("churro", "run-a", "book_a", 1, "此為一頁完全空白的古籍書影像", "ok", Path("a.txt")),
                PageCandidate("qwen35", "run-b", "book_a", 1, "此頁無字", "ok", Path("b.txt")),
                PageCandidate("surya_ocr", "run-c", "book_a", 1, "", "blank", Path("c.txt")),
                PageCandidate("kandianguji", "run-d", "book_a", 1, "", "blank", Path("d.txt")),
            ],
            model_priority=["kandianguji", "churro", "qwen35", "surya_ocr"],
            min_votes=3,
        )

        self.assertEqual(result.text, "")

    def test_vote_text_keeps_majority_inserted_character(self):
        result = vote_text(
            [
                PageCandidate("model_a", "run-a", "book_a", 1, "甲丙", "ok", Path("a.txt")),
                PageCandidate("model_b", "run-b", "book_a", 1, "甲乙丙", "ok", Path("b.txt")),
                PageCandidate("model_c", "run-c", "book_a", 1, "甲乙丙", "ok", Path("c.txt")),
                PageCandidate("model_d", "run-d", "book_a", 1, "甲乙丙", "ok", Path("d.txt")),
            ],
            model_priority=["model_a", "model_b", "model_c", "model_d"],
            min_votes=3,
        )

        self.assertEqual(result.text, "甲乙丙")

    def test_write_agreement_run_uses_standard_output_layout(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_root = root / "outputs" / "ocr_agreement"
            pages = {
                ("book_a", 1): [
                    PageCandidate("model_a", "run-a", "book_a", 1, "甲", "ok", Path("a.txt")),
                    PageCandidate("model_b", "run-b", "book_a", 1, "甲", "ok", Path("b.txt")),
                ],
                ("book_a", 2): [
                    PageCandidate("model_a", "run-a", "book_a", 2, "", "blank", Path("a2.txt")),
                    PageCandidate("model_b", "run-b", "book_a", 2, "", "blank", Path("b2.txt")),
                ],
            }

            summary = write_agreement_run(
                pages,
                output_root=output_root,
                run_id="agreement-test",
                model_priority=["model_a", "model_b"],
            )

            run_root = output_root / "agreement-test"
            manifest_rows = [
                json.loads(line)
                for line in (run_root / "manifest.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            page_json = json.loads(
                (run_root / "pages_json" / "book_a" / "page_0001.json").read_text(encoding="utf-8")
            )

            self.assertEqual(summary["written_pages"], 2)
            self.assertEqual((run_root / "pages_text" / "book_a" / "page_0001.txt").read_text(encoding="utf-8"), "甲")
            self.assertEqual((run_root / "pages_text" / "book_a" / "page_0002.txt").read_text(encoding="utf-8"), "")
            self.assertEqual(
                (run_root / "books_text" / "book_a.txt").read_text(encoding="utf-8"),
                "=== page_0001 ===\n甲\n\n=== page_0002 ===\n\n",
            )
            self.assertEqual([row["status"] for row in manifest_rows], ["ok", "blank"])
            self.assertEqual(manifest_rows[0]["model"], "agreement_vote")
            self.assertEqual(manifest_rows[0]["source_models"], ["model_a", "model_b"])
            self.assertEqual(page_json["text"], "甲")
            self.assertEqual(page_json["voter_count"], 2)

    def test_parse_args_accepts_repeatable_run_dirs_and_filters(self):
        args = parse_args(
            [
                "--run-dir",
                "outputs/ocr_runs/churro/churro-full-001",
                "--run-dir",
                "outputs/ocr_runs/qwen35/qwen35-full-001",
                "--run-id",
                "agreement-dev",
                "--book-id",
                "book_a",
                "--min-models",
                "2",
                "--dry-run",
            ]
        )

        self.assertEqual(args.run_id, "agreement-dev")
        self.assertEqual(args.book_id, ["book_a"])
        self.assertEqual(args.min_models, 2)
        self.assertTrue(args.dry_run)
        self.assertEqual(len(args.run_dir), 2)

    def test_effective_min_models_defaults_to_unique_model_majority(self):
        self.assertEqual(effective_min_models(["churro", "qwen35", "surya_ocr", "kandianguji"], None), 3)
        self.assertEqual(
            effective_min_models(
                ["churro", "qwen35", "surya_ocr", "kandianguji", "kandianguji", "kandianguji"],
                None,
            ),
            3,
        )

    def test_effective_min_models_respects_explicit_override(self):
        self.assertEqual(effective_min_models(["churro", "qwen35", "surya_ocr", "kandianguji"], 4), 4)


if __name__ == "__main__":
    unittest.main()
