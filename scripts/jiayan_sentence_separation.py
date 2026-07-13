from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

from scripts.sentence_separation import (
    DEFAULT_OUTPUT_ROOT,
    PageText,
    SentenceSegment,
    load_manifest_pages,
    segment_text,
    write_sentence_run,
)


JIAYAN_SENTENCE_MODEL = "jiayan_sentence_separation"
JIAYAN_SEGMENT_MODEL = "jiayan_crf_sentencizer"
DEFAULT_JIAYAN_MODEL_DIR = Path("models/jiayan/jiayan_models")


def normalize_for_validation(text: str) -> str:
    return "".join(text.split())


class JiayanSentenceSegmenter:
    def __init__(self, *, sentencizer: object):
        self.sentencizer = sentencizer

    def segment_text(self, text: str) -> list[SentenceSegment]:
        if not text.strip():
            return []
        try:
            model_segments = [
                str(segment).strip()
                for segment in self.sentencizer.sentencize(text)
                if str(segment).strip()
            ]
            if normalize_for_validation("".join(model_segments)) != normalize_for_validation(text):
                raise ValueError("Jiayan changed input text")
            return [
                SentenceSegment(segment, "jiayan_sentencizer")
                for segment in model_segments
            ]
        except Exception:
            return [
                SentenceSegment(segment.text, "jiayan_fallback")
                for segment in segment_text(text)
            ]


def create_jiayan_segmenter(model_dir: Path) -> JiayanSentenceSegmenter:
    from jiayan import CRFSentencizer, load_lm

    lm_path = model_dir / "jiayan.klm"
    cut_model_path = model_dir / "cut_model"
    if not lm_path.exists():
        raise FileNotFoundError(f"missing Jiayan language model: {lm_path}")
    if not cut_model_path.exists():
        raise FileNotFoundError(f"missing Jiayan sentence model: {cut_model_path}")
    lm = load_lm(str(lm_path))
    sentencizer = CRFSentencizer(lm)
    sentencizer.load(str(cut_model_path))
    return JiayanSentenceSegmenter(sentencizer=sentencizer)


def write_jiayan_sentence_run(
    pages: list[PageText],
    *,
    output_root: Path,
    run_id: str,
    segmenter: JiayanSentenceSegmenter,
) -> dict:
    return write_sentence_run(
        pages,
        output_root=output_root,
        run_id=run_id,
        segmenter=segmenter.segment_text,
        output_model=JIAYAN_SENTENCE_MODEL,
        page_metadata={"segment_model": JIAYAN_SEGMENT_MODEL},
        sentence_metadata={"segment_model": JIAYAN_SEGMENT_MODEL},
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Use Jiayan CRF to separate voted OCR output into sentence units.")
    parser.add_argument("--input-run-dir", action="append", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_JIAYAN_MODEL_DIR)
    parser.add_argument(
        "--run-id",
        default="jiayan-sentence-separation-" + dt.datetime.now().strftime("%Y%m%d-%H%M%S"),
    )
    parser.add_argument("--limit-pages", type=int, help="Optional smoke-test limit before a full run.")
    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    return build_parser().parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        pages = load_manifest_pages(args.input_run_dir, repo_root=Path.cwd())
        if args.limit_pages is not None:
            pages = pages[: args.limit_pages]
        segmenter = create_jiayan_segmenter(args.model_dir)
        summary = write_jiayan_sentence_run(
            pages,
            output_root=args.output_root,
            run_id=args.run_id,
            segmenter=segmenter,
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
