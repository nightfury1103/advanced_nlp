import argparse
import itertools
import json
from pathlib import Path
from typing import Optional

from score_ocr import edit_distance, normalize_text, substring_edit_distance


CLEAN_PAGES = [44, 80, 160, 240, 320]
SHARED_WITH_OLMOCR_PAGES = [80, 160, 240, 320]

DEFAULT_MODELS = {
    "KanDianGuJi": "kandianguji",
    "olmOCR L4 FP8": "olmocr_l4_smoke",
    "Umi/RapidOCR CPU": "umi_cpu",
    "GJ.cool": "gjcool",
}


def strict_pair_agreement(left: str, right: str) -> dict:
    left_norm = normalize_text(left)
    right_norm = normalize_text(right)
    denominator = max(len(left_norm), len(right_norm))
    distance = edit_distance(left_norm, right_norm)
    agreement = 1.0 if denominator == 0 else 1 - distance / denominator
    return {
        "edit_distance": distance,
        "denominator": denominator,
        "agreement": round(max(0.0, agreement), 4),
    }


def aligned_pair_agreement(left: str, right: str) -> dict:
    left_norm = normalize_text(left)
    right_norm = normalize_text(right)
    if len(left_norm) <= len(right_norm):
        shorter, longer = left_norm, right_norm
    else:
        shorter, longer = right_norm, left_norm
    denominator = len(shorter)
    distance = substring_edit_distance(shorter, longer)
    agreement = 1.0 if denominator == 0 else 1 - distance / denominator
    return {
        "edit_distance": distance,
        "denominator": denominator,
        "agreement": round(max(0.0, agreement), 4),
    }


def read_page(model_dir: Path, page: int) -> Optional[str]:
    path = model_dir / f"page_{page:03d}.txt"
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def score_pair(
    model_a: str,
    model_a_dir: Path,
    model_b: str,
    model_b_dir: Path,
    pages: list[int],
) -> dict:
    used_pages = []
    strict_distance = 0
    strict_denominator = 0
    aligned_distance = 0
    aligned_denominator = 0

    for page in pages:
        left = read_page(model_a_dir, page)
        right = read_page(model_b_dir, page)
        if left is None or right is None:
            continue

        strict = strict_pair_agreement(left, right)
        aligned = aligned_pair_agreement(left, right)
        used_pages.append(page)
        strict_distance += strict["edit_distance"]
        strict_denominator += strict["denominator"]
        aligned_distance += aligned["edit_distance"]
        aligned_denominator += aligned["denominator"]

    strict_agreement = (
        None
        if strict_denominator == 0
        else round(max(0.0, 1 - strict_distance / strict_denominator), 4)
    )
    aligned_agreement = (
        None
        if aligned_denominator == 0
        else round(max(0.0, 1 - aligned_distance / aligned_denominator), 4)
    )

    return {
        "model_a": model_a,
        "model_b": model_b,
        "pages": used_pages,
        "page_count": len(used_pages),
        "strict_edit_distance": strict_distance,
        "strict_denominator": strict_denominator,
        "strict_agreement": strict_agreement,
        "aligned_edit_distance": aligned_distance,
        "aligned_denominator": aligned_denominator,
        "aligned_agreement": aligned_agreement,
    }


def score_section(
    name: str,
    output_root: Path,
    models: dict[str, str],
    pages: list[int],
) -> dict:
    rows = []
    for model_a, model_b in itertools.combinations(models, 2):
        rows.append(
            score_pair(
                model_a,
                output_root / models[model_a],
                model_b,
                output_root / models[model_b],
                pages,
            )
        )
    return {
        "name": name,
        "models": list(models),
        "requested_pages": pages,
        "pairs": rows,
    }


def build_report(output_root: Path) -> dict:
    all_models = DEFAULT_MODELS
    complete_models = {
        "KanDianGuJi": "kandianguji",
        "Umi/RapidOCR CPU": "umi_cpu",
        "GJ.cool": "gjcool",
    }
    return {
        "summary": {
            "metric": "OCR output agreement",
            "strict_agreement": "1 - pairwise edit distance / max normalized output length",
            "aligned_agreement": "1 - shorter output edit distance to best contiguous span in longer output / shorter length",
            "normalization": "same normalization as score_ocr.py",
        },
        "sections": [
            score_section(
                "all_models_shared_pages",
                output_root,
                all_models,
                SHARED_WITH_OLMOCR_PAGES,
            ),
            score_section(
                "complete_models_clean_pages",
                output_root,
                complete_models,
                CLEAN_PAGES,
            ),
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-root",
        default="benchmarks/no_gpu_first_pass/output",
        help="Directory containing one subdirectory per OCR system.",
    )
    parser.add_argument(
        "--out",
        default="benchmarks/no_gpu_first_pass/output/agreement_scores.json",
        help="Path to write agreement JSON.",
    )
    args = parser.parse_args()

    payload = build_report(Path(args.output_root))
    Path(args.out).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
