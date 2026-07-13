"""Create auditable Hán--Việt sentence alignments from pre-segmented text.

The runner deliberately keeps sentence segmentation outside the alignment step.
Each document pair is supplied in a JSONL manifest and each source/target document
is a JSONL file containing at least ``sentence_id`` and ``text``.  LaBSE is loaded
only when the command is run, so the dynamic-programming core remains testable
without downloading a model.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np


ALIGNMENT_MODEL = "labse_monotonic_sentence_alignment"
DEFAULT_OUTPUT_ROOT = Path("outputs/parallel_alignment")
DEFAULT_EMBEDDING_MODEL = "sentence-transformers/LaBSE"
RELATIONS = ((1, 1), (1, 2), (2, 1), (2, 2))


@dataclass(frozen=True)
class Sentence:
    sentence_id: str
    text: str


@dataclass(frozen=True)
class DocumentPair:
    pair_id: str
    source_path: Path
    target_path: Path


@dataclass(frozen=True)
class AlignmentStep:
    source_indices: tuple[int, ...]
    target_indices: tuple[int, ...]
    score: float | None

    @property
    def relation(self) -> str:
        return f"{len(self.source_indices)}-{len(self.target_indices)}"


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as input_file:
        for line_number, line in enumerate(input_file, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSONL row") from exc
            if not isinstance(row, dict):
                raise ValueError(f"{path}:{line_number}: expected a JSON object")
            rows.append(row)
    return rows


def load_sentences(path: Path) -> list[Sentence]:
    sentences = []
    seen_ids = set()
    for line_number, row in enumerate(read_jsonl(path), start=1):
        sentence_id = row.get("sentence_id")
        text = row.get("text")
        if not isinstance(sentence_id, str) or not sentence_id:
            raise ValueError(f"{path}:{line_number}: missing sentence_id")
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"{path}:{line_number}: missing sentence text")
        if sentence_id in seen_ids:
            raise ValueError(f"{path}:{line_number}: duplicate sentence_id {sentence_id}")
        seen_ids.add(sentence_id)
        sentences.append(Sentence(sentence_id=sentence_id, text=text))
    return sentences


def load_pairs(path: Path) -> list[DocumentPair]:
    pairs = []
    seen_ids = set()
    for line_number, row in enumerate(read_jsonl(path), start=1):
        pair_id = row.get("pair_id")
        source_path = row.get("source_path")
        target_path = row.get("target_path")
        if not all(isinstance(value, str) and value for value in (pair_id, source_path, target_path)):
            raise ValueError(f"{path}:{line_number}: pair_id, source_path, and target_path are required")
        if pair_id in seen_ids:
            raise ValueError(f"{path}:{line_number}: duplicate pair_id {pair_id}")
        seen_ids.add(pair_id)
        base = path.parent
        source = Path(source_path)
        target = Path(target_path)
        pairs.append(
            DocumentPair(
                pair_id=pair_id,
                source_path=source if source.is_absolute() else base / source,
                target_path=target if target.is_absolute() else base / target,
            )
        )
    if not pairs:
        raise ValueError(f"{path}: no document pairs")
    return pairs


def _normalise_embeddings(embeddings: np.ndarray) -> np.ndarray:
    embeddings = np.asarray(embeddings, dtype=np.float32)
    if embeddings.ndim != 2:
        raise ValueError("embeddings must be a 2D array")
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    if np.any(norms == 0):
        raise ValueError("embeddings must not contain zero vectors")
    return embeddings / norms


def _group_vector(embeddings: np.ndarray, indices: tuple[int, ...]) -> np.ndarray:
    vector = embeddings[list(indices)].mean(axis=0)
    norm = float(np.linalg.norm(vector))
    if norm == 0:
        raise ValueError("group embedding has zero norm")
    return vector / norm


def align_embeddings(
    source_embeddings: np.ndarray,
    target_embeddings: np.ndarray,
    *,
    min_match_score: float = 0.35,
    expansion_penalty: float = 0.02,
    skip_penalty: float = 0.35,
) -> list[AlignmentStep]:
    """Align ordered sentence vectors, retaining unmatched sentences explicitly.

    The path is monotonic and permits 1-1, 1-2, 2-1, and 2-2 matches.  Candidate
    matches below ``min_match_score`` are rejected, allowing source or target
    omissions to remain reviewable instead of forcing a spurious pair.
    """

    source = _normalise_embeddings(source_embeddings)
    target = _normalise_embeddings(target_embeddings)
    if source.shape[1] != target.shape[1]:
        raise ValueError("source and target embeddings must have the same dimension")

    source_count, target_count = len(source), len(target)
    scores = np.full((source_count + 1, target_count + 1), -np.inf, dtype=np.float64)
    back: list[list[AlignmentStep | None]] = [
        [None for _ in range(target_count + 1)] for _ in range(source_count + 1)
    ]
    scores[0, 0] = 0.0

    for source_end in range(source_count + 1):
        for target_end in range(target_count + 1):
            if not np.isfinite(scores[source_end, target_end]):
                continue
            current = float(scores[source_end, target_end])

            for source_size, target_size in RELATIONS:
                next_source = source_end + source_size
                next_target = target_end + target_size
                if next_source > source_count or next_target > target_count:
                    continue
                source_indices = tuple(range(source_end, next_source))
                target_indices = tuple(range(target_end, next_target))
                similarity = float(_group_vector(source, source_indices) @ _group_vector(target, target_indices))
                match_score = similarity - expansion_penalty * (source_size + target_size - 2)
                if match_score < min_match_score:
                    continue
                candidate = current + match_score
                if candidate > scores[next_source, next_target]:
                    scores[next_source, next_target] = candidate
                    back[next_source][next_target] = AlignmentStep(source_indices, target_indices, similarity)

            if source_end < source_count:
                candidate = current - skip_penalty
                if candidate > scores[source_end + 1, target_end]:
                    scores[source_end + 1, target_end] = candidate
                    back[source_end + 1][target_end] = AlignmentStep((source_end,), (), None)
            if target_end < target_count:
                candidate = current - skip_penalty
                if candidate > scores[source_end, target_end + 1]:
                    scores[source_end, target_end + 1] = candidate
                    back[source_end][target_end + 1] = AlignmentStep((), (target_end,), None)

    steps = []
    source_end, target_end = source_count, target_count
    while source_end or target_end:
        step = back[source_end][target_end]
        if step is None:
            raise RuntimeError("no alignment path found")
        steps.append(step)
        source_end -= len(step.source_indices)
        target_end -= len(step.target_indices)
    return list(reversed(steps))


def confidence_for(step: AlignmentStep) -> tuple[str, bool]:
    if step.score is None:
        return "unmatched", True
    if step.relation == "1-1" and step.score >= 0.82:
        return "high", False
    if step.score >= 0.65:
        return "medium", True
    return "low", True


def embed_sentences(
    sentences: Iterable[Sentence],
    *,
    model_name: str,
    batch_size: int,
    device: str | None,
) -> np.ndarray:
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError("install sentence-transformers to run LaBSE alignment") from exc
    model = SentenceTransformer(model_name, device=device)
    texts = [sentence.text for sentence in sentences]
    return np.asarray(model.encode(texts, batch_size=batch_size, show_progress_bar=False), dtype=np.float32)


def safe_filename(value: str) -> str:
    name = re.sub(r"[^\w.-]+", "_", value, flags=re.UNICODE).strip("._")
    return name or "pair"


def write_alignment_run(
    *,
    pairs: list[DocumentPair],
    output_root: Path,
    run_id: str,
    embedding_model: str,
    batch_size: int,
    device: str | None,
    min_match_score: float,
    expansion_penalty: float,
    skip_penalty: float,
) -> dict:
    run_root = output_root / run_id
    manifest_path = run_root / "manifest.jsonl"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    if manifest_path.exists():
        manifest_path.unlink()

    written_alignments = 0
    review_count = 0
    used_output_names = set()
    for pair in pairs:
        source_sentences = load_sentences(pair.source_path)
        target_sentences = load_sentences(pair.target_path)
        source_embeddings = embed_sentences(
            source_sentences, model_name=embedding_model, batch_size=batch_size, device=device
        )
        target_embeddings = embed_sentences(
            target_sentences, model_name=embedding_model, batch_size=batch_size, device=device
        )
        steps = align_embeddings(
            source_embeddings,
            target_embeddings,
            min_match_score=min_match_score,
            expansion_penalty=expansion_penalty,
            skip_penalty=skip_penalty,
        )

        output_name = safe_filename(pair.pair_id)
        if output_name in used_output_names:
            raise ValueError(f"pair_id {pair.pair_id!r} conflicts with another output filename")
        used_output_names.add(output_name)
        output_path = run_root / "alignments" / f"{output_name}.jsonl"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as output_file:
            for index, step in enumerate(steps, start=1):
                confidence, review_required = confidence_for(step)
                row = {
                    "alignment_id": f"{pair.pair_id}-a{index:05d}",
                    "pair_id": pair.pair_id,
                    "source_sentence_ids": [source_sentences[i].sentence_id for i in step.source_indices],
                    "target_sentence_ids": [target_sentences[i].sentence_id for i in step.target_indices],
                    "source_text": "\n".join(source_sentences[i].text for i in step.source_indices),
                    "target_text": "\n".join(target_sentences[i].text for i in step.target_indices),
                    "relation": step.relation,
                    "similarity": None if step.score is None else round(step.score, 6),
                    "confidence": confidence,
                    "review_required": review_required,
                    "alignment_model": ALIGNMENT_MODEL,
                    "embedding_model": embedding_model,
                }
                output_file.write(json.dumps(row, ensure_ascii=False) + "\n")
                written_alignments += 1
                review_count += review_required

        manifest_row = {
            "model": ALIGNMENT_MODEL,
            "run_id": run_id,
            "pair_id": pair.pair_id,
            "status": "ok" if steps else "blank",
            "source_path": str(pair.source_path),
            "target_path": str(pair.target_path),
            "alignment_path": str(output_path),
            "source_sentence_count": len(source_sentences),
            "target_sentence_count": len(target_sentences),
            "alignment_count": len(steps),
            "embedding_model": embedding_model,
            "min_match_score": min_match_score,
            "expansion_penalty": expansion_penalty,
            "skip_penalty": skip_penalty,
        }
        with manifest_path.open("a", encoding="utf-8") as manifest_file:
            manifest_file.write(json.dumps(manifest_row, ensure_ascii=False) + "\n")

    return {
        "run_root": str(run_root),
        "written_pairs": len(pairs),
        "written_alignments": written_alignments,
        "review_required": review_count,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Align pre-segmented Hán--Việt document pairs with LaBSE.")
    parser.add_argument("--pair-manifest", type=Path, required=True, help="JSONL document-pair manifest.")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--run-id", default="labse-alignment-" + dt.datetime.now().strftime("%Y%m%d-%H%M%S"))
    parser.add_argument("--embedding-model", default=DEFAULT_EMBEDDING_MODEL)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--device", default=None, help="Sentence Transformers device, e.g. mps, cuda, or cpu.")
    parser.add_argument("--min-match-score", type=float, default=0.35)
    parser.add_argument("--expansion-penalty", type=float, default=0.02)
    parser.add_argument("--skip-penalty", type=float, default=0.35)
    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    return build_parser().parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        summary = write_alignment_run(
            pairs=load_pairs(args.pair_manifest),
            output_root=args.output_root,
            run_id=args.run_id,
            embedding_model=args.embedding_model,
            batch_size=args.batch_size,
            device=args.device,
            min_match_score=args.min_match_score,
            expansion_penalty=args.expansion_penalty,
            skip_penalty=args.skip_penalty,
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
