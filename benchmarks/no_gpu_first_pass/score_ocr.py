import argparse
import json
import string
from pathlib import Path


PAGES = [5, 20, 44, 52, 80, 160, 240, 320]


def normalize_text(value: str) -> str:
    remove = set(string.whitespace + string.punctuation + "，。！？、；：「」『』（）《》〈〉—…")
    return "".join(char for char in value if char not in remove)


def edit_distance(reference: str, candidate: str) -> int:
    previous = list(range(len(candidate) + 1))
    for ref_index, ref_char in enumerate(reference, start=1):
        current = [ref_index]
        for cand_index, cand_char in enumerate(candidate, start=1):
            insert = current[cand_index - 1] + 1
            delete = previous[cand_index] + 1
            substitute = previous[cand_index - 1] + (ref_char != cand_char)
            current.append(min(insert, delete, substitute))
        previous = current
    return previous[-1]


def character_error_rate(reference: str, candidate: str) -> float:
    reference = normalize_text(reference)
    candidate = normalize_text(candidate)
    if not reference:
        return 0.0 if not candidate else 1.0
    return edit_distance(reference, candidate) / len(reference)


def substring_edit_distance(reference: str, candidate: str) -> int:
    """Distance from reference to the best contiguous span inside candidate."""
    previous = [0] * (len(candidate) + 1)
    for ref_index, ref_char in enumerate(reference, start=1):
        current = [ref_index]
        for cand_index, cand_char in enumerate(candidate, start=1):
            insert = current[cand_index - 1] + 1
            delete = previous[cand_index] + 1
            substitute = previous[cand_index - 1] + (ref_char != cand_char)
            current.append(min(insert, delete, substitute))
        previous = current
    return min(previous)


def aligned_character_error_rate(reference: str, candidate: str) -> float:
    reference = normalize_text(reference)
    candidate = normalize_text(candidate)
    if not reference:
        return 0.0 if not candidate else 1.0
    return substring_edit_distance(reference, candidate) / len(reference)


def load_runtime_summary(model_dir: Path) -> dict[int, dict]:
    summary_path = model_dir / "summary.json"
    if not summary_path.exists():
        return {}
    rows = json.loads(summary_path.read_text(encoding="utf-8"))
    return {int(row["page"]): row for row in rows}


def aggregate_scores(rows: list[dict]) -> dict:
    scored = [row for row in rows if row["status"] == "scored"]
    missing_ground_truth = sum(row["status"] == "missing_ground_truth" for row in rows)
    missing_prediction = sum(row["status"] == "missing_prediction" for row in rows)
    reference_chars = sum(row["reference_chars"] for row in scored)
    prediction_chars = sum(row["prediction_chars"] for row in scored)
    total_distance = sum(row["edit_distance"] for row in scored)
    total_aligned_distance = sum(row.get("aligned_edit_distance", row["edit_distance"]) for row in scored)
    timed = [row for row in scored if row.get("wall_time_seconds") is not None]
    total_time = sum(row["wall_time_seconds"] for row in timed)

    return {
        "scored_pages": len(scored),
        "missing_ground_truth_pages": missing_ground_truth,
        "missing_prediction_pages": missing_prediction,
        "reference_chars": reference_chars,
        "prediction_chars": prediction_chars,
        "edit_distance": total_distance,
        "weighted_cer": round(total_distance / reference_chars, 4) if reference_chars else None,
        "aligned_edit_distance": total_aligned_distance,
        "weighted_aligned_cer": round(total_aligned_distance / reference_chars, 4)
        if reference_chars
        else None,
        "total_wall_time_seconds": round(total_time, 3) if timed else None,
        "avg_wall_time_seconds": round(total_time / len(timed), 3) if timed else None,
        "reference_chars_per_second": round(reference_chars / total_time, 2) if total_time else None,
        "prediction_chars_per_second": round(prediction_chars / total_time, 2) if total_time else None,
        "prediction_reference_char_ratio": round(prediction_chars / reference_chars, 4)
        if reference_chars
        else None,
    }


def score_model(model_dir: Path, ground_truth_dir: Path) -> list[dict]:
    rows = []
    runtime_by_page = load_runtime_summary(model_dir)
    for page in PAGES:
        gt_path = ground_truth_dir / f"page_{page:03d}.txt"
        pred_path = model_dir / f"page_{page:03d}.txt"
        if not gt_path.exists() or not gt_path.read_text(encoding="utf-8").strip():
            rows.append({"page": page, "status": "missing_ground_truth"})
            continue
        if not pred_path.exists():
            rows.append({"page": page, "status": "missing_prediction"})
            continue
        reference = gt_path.read_text(encoding="utf-8")
        candidate = pred_path.read_text(encoding="utf-8")
        reference_norm = normalize_text(reference)
        candidate_norm = normalize_text(candidate)
        distance = edit_distance(reference_norm, candidate_norm)
        aligned_distance = substring_edit_distance(reference_norm, candidate_norm)
        runtime = runtime_by_page.get(page, {})
        wall_time = runtime.get("wall_time_seconds")
        rows.append(
            {
                "page": page,
                "status": "scored",
                "reference_chars": len(reference_norm),
                "prediction_chars": len(candidate_norm),
                "edit_distance": distance,
                "cer": round(distance / len(reference_norm), 4) if reference_norm else None,
                "aligned_edit_distance": aligned_distance,
                "aligned_cer": round(aligned_distance / len(reference_norm), 4)
                if reference_norm
                else None,
                "wall_time_seconds": wall_time,
                "ocr_items": runtime.get("item_count"),
                "prediction_reference_char_ratio": round(len(candidate_norm) / len(reference_norm), 4)
                if reference_norm
                else None,
                "reference_chars_per_second": round(len(reference_norm) / wall_time, 2)
                if wall_time
                else None,
                "prediction_chars_per_second": round(len(candidate_norm) / wall_time, 2)
                if wall_time
                else None,
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--ground-truth-dir", default="benchmarks/no_gpu_first_pass/ground_truth")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    rows = score_model(Path(args.model_dir), Path(args.ground_truth_dir))
    payload = {"summary": aggregate_scores(rows), "pages": rows}
    Path(args.out).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
