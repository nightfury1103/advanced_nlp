from __future__ import annotations

import json
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

import modal


APP_NAME = os.environ.get("NER_APP_NAME", "advanced-nlp-ner-books-001-010")
RUN_ID = os.environ.get("NER_RUN_ID", "ner-models-books-001-010-v001")
INPUT_ROOT = Path(
    os.environ.get(
        "NER_INPUT_ROOT",
        "outputs/sentence_separation/sentence-agreement-vote-books-001-010-v001/books_sentences",
    )
)
REMOTE_INPUT_ROOT = Path("/root/ner-input")
REMOTE_OUTPUT_ROOT = Path("/mnt/ner-output")
REMOTE_MODEL_CACHE_ROOT = Path("/mnt/ner-model-cache")
OUTPUT_VOLUME_NAME = os.environ.get("NER_OUTPUT_VOLUME_NAME", "advanced-nlp-ner-output")
MODEL_CACHE_VOLUME_NAME = "advanced-nlp-ner-model-cache"
QWEN_CACHE_VOLUME_NAME = "advanced-nlp-qwen25-14b-cache"

CKIP_MODEL = "ckiplab/bert-base-chinese-ner"
HANLP_MODEL = "hanlp.pretrained.ner.MSRA_NER_ELECTRA_SMALL_ZH"
QWEN_MODEL = "Qwen/Qwen2.5-14B-Instruct-AWQ"

INPUT_BOOK_START = int(os.environ.get("NER_INPUT_BOOK_START", "1"))
INPUT_BOOK_END = int(os.environ.get("NER_INPUT_BOOK_END", "10"))
INPUT_FILE_NAMES = tuple(
    f"越南汉文燕行文献集成_第{book_number}册.jsonl"
    for book_number in range(INPUT_BOOK_START, INPUT_BOOK_END + 1)
)

CANONICAL_LABELS = (
    "PERSON",
    "LOCATION",
    "ORGANIZATION",
    "DATE",
    "TIME",
    "NUMBER",
    "MISC",
)

output_volume = modal.Volume.from_name(OUTPUT_VOLUME_NAME, create_if_missing=True)
model_cache_volume = modal.Volume.from_name(MODEL_CACHE_VOLUME_NAME, create_if_missing=True)
qwen_cache_volume = modal.Volume.from_name(QWEN_CACHE_VOLUME_NAME, create_if_missing=True)


def _input_files() -> list[Path]:
    return [INPUT_ROOT / name for name in INPUT_FILE_NAMES]


def _add_input_files(image: modal.Image) -> modal.Image:
    for path in _input_files():
        image = image.add_local_file(str(path), str(REMOTE_INPUT_ROOT / path.name))
    return image


def _base_image(*packages: str) -> modal.Image:
    image = modal.Image.debian_slim(python_version="3.11").apt_install("ca-certificates")
    return _add_input_files(image.pip_install(*packages))


ckip_image = _base_image(
    "torch",
    "transformers==4.47.1",
    "ckip-transformers==0.3.4",
)

hanlp_image = _base_image(
    "torch",
    "hanlp==2.1.2",
    "transformers==4.47.1",
)

qwen_image = _base_image(
    "vllm==0.6.6.post1",
    "transformers==4.47.1",
    "accelerate>=1.2.0",
    "huggingface_hub[hf_transfer]>=0.26.0",
)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as input_file:
        for line_number, line in enumerate(input_file, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON") from exc
            if not isinstance(row, dict):
                raise ValueError(f"{path}:{line_number}: row must be an object")
            rows.append(row)
    return rows


def _load_input_rows(*, book_filter: str = "", limit_sentences: int = 0) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    remaining = limit_sentences if limit_sentences > 0 else None
    for path in sorted(REMOTE_INPUT_ROOT.glob("*.jsonl")):
        rows = _read_jsonl(path)
        for row in rows:
            book_id = row.get("book_id")
            sentence_id = row.get("sentence_id")
            text = row.get("text")
            if not all(isinstance(value, str) and value for value in (book_id, sentence_id, text)):
                raise ValueError(f"invalid sentence row in {path}: {row!r}")
            if book_filter and book_filter not in book_id:
                continue
            grouped.setdefault(book_id, []).append(row)
            if remaining is not None:
                remaining -= 1
                if remaining == 0:
                    return grouped
    return grouped


def _strip_bio(label: str) -> str:
    label = label.strip().upper()
    if label.startswith(("B-", "I-", "E-", "S-")):
        return label[2:]
    return label


def canonical_label(raw_label: str, model_key: str) -> str:
    raw = _strip_bio(raw_label)
    if raw in {"PERSON", "PER", "P", "NR", "NH", "NAME"}:
        return "PERSON"
    if raw in {"LOCATION", "LOC", "L", "NS", "GPE", "ADDRESS", "FAC", "SCENE"}:
        return "LOCATION"
    if raw in {"ORGANIZATION", "ORG", "O", "NT", "COMPANY", "GOVERNMENT", "ORGANISATION"}:
        return "ORGANIZATION"
    if raw in {"DATE", "DATEX", "DATERANGE"}:
        return "DATE"
    if raw in {"TIME", "TIMEX", "DURATION"}:
        return "TIME"
    if raw in {
        "CARDINAL",
        "INTEGER",
        "ORDINAL",
        "NUMBER",
        "NUMEX",
        "MONEY",
        "PERCENT",
        "QUANTITY",
        "RATE",
    }:
        return "NUMBER"
    if raw in CANONICAL_LABELS:
        return raw
    if model_key == "qwen25" and raw in {"WORK", "BOOK", "TITLE", "EVENT", "DYNASTY", "ERA"}:
        return "MISC"
    return "MISC"


def _find_entity_text(text: str, value: str) -> tuple[int, int] | None:
    if not value:
        return None
    start = text.find(value)
    if start < 0:
        return None
    return start, start + len(value)


def normalize_entity(
    *,
    sentence_text: str,
    model_key: str,
    value: Any,
    default_label: str | None = None,
) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    raw_label = value.get("raw_label") or value.get("label") or value.get("entity_group") or default_label
    if not isinstance(raw_label, str) or not raw_label.strip():
        return None

    raw_text = value.get("text") or value.get("word")
    start = value.get("start")
    end = value.get("end")
    if isinstance(start, bool) or not isinstance(start, int):
        start = None
    if isinstance(end, bool) or not isinstance(end, int):
        end = None

    if start is not None and end is not None and 0 <= start < end <= len(sentence_text):
        entity_text = sentence_text[start:end]
        if isinstance(raw_text, str) and raw_text and raw_text != entity_text:
            located = _find_entity_text(sentence_text, raw_text)
            if located is None:
                return None
            start, end = located
            entity_text = sentence_text[start:end]
    elif isinstance(raw_text, str):
        located = _find_entity_text(sentence_text, raw_text)
        if located is None:
            return None
        start, end = located
        entity_text = sentence_text[start:end]
    else:
        return None

    result: dict[str, Any] = {
        "text": entity_text,
        "start": start,
        "end": end,
        "label": canonical_label(raw_label, model_key),
        "raw_label": raw_label,
    }
    score = value.get("score")
    if isinstance(score, (int, float)) and not isinstance(score, bool):
        result["score"] = round(float(score), 6)
    return result


def normalize_entities(
    *,
    sentence_text: str,
    model_key: str,
    values: list[Any],
) -> list[dict[str, Any]]:
    entities = []
    seen = set()
    for value in values:
        entity = normalize_entity(sentence_text=sentence_text, model_key=model_key, value=value)
        if entity is None:
            continue
        key = (entity["start"], entity["end"], entity["label"])
        if key in seen:
            continue
        seen.add(key)
        entities.append(entity)
    return sorted(entities, key=lambda item: (item["start"], item["end"], item["label"]))


class CkipPredictor:
    def __init__(self) -> None:
        from ckip_transformers.nlp import CkipNerChunker

        self.driver = CkipNerChunker(model="bert-base", device=0)

    def predict(self, texts: list[str]) -> list[list[dict[str, Any]]]:
        # CKIP reserves two BERT special tokens and asserts a strict upper bound.
        # All agreed sentences are shorter than 500 characters.
        outputs = self.driver(texts, batch_size=64, max_length=500, use_delim=False)
        result = []
        for text, output in zip(texts, outputs):
            values = []
            for token in output:
                start, end = token.idx
                values.append(
                    {
                        "text": token.word,
                        "start": start,
                        "end": end,
                        "raw_label": token.ner,
                    }
                )
            result.append(normalize_entities(sentence_text=text, model_key="ckip", values=values))
        return result


class HanlpPredictor:
    def __init__(self) -> None:
        import hanlp

        model_url = getattr(hanlp.pretrained.ner, "MSRA_NER_ELECTRA_SMALL_ZH")
        self.recognizer = hanlp.load(model_url, devices=0)

    def predict(self, texts: list[str]) -> list[list[dict[str, Any]]]:
        tokenized = [list(text) for text in texts]
        outputs = self.recognizer(tokenized)
        result = []
        for text, output in zip(texts, outputs):
            values = []
            for entity in output:
                if not isinstance(entity, (list, tuple)) or len(entity) < 4:
                    continue
                entity_text, label, start, end = entity[:4]
                values.append(
                    {
                        "text": entity_text,
                        "raw_label": label,
                        "start": start,
                        "end": end,
                    }
                )
            result.append(normalize_entities(sentence_text=text, model_key="hanlp", values=values))
        return result


def qwen_prompt(text: str) -> str:
    return (
        "You perform named entity recognition on noisy historical Chinese/Han text.\n"
        "Return JSON only, exactly in the form {\"entities\":[...]}.\n"
        "Each entity must have text, start, end, and label. start is a Python character "
        "offset and end is exclusive. The text must be an exact substring of the input.\n"
        "Allowed labels: PERSON, LOCATION, ORGANIZATION, DATE, TIME, NUMBER, MISC.\n"
        "Use MISC for historical works, titles, offices, dynasties, eras, and events when "
        "they do not fit another allowed label. Do not translate, correct, add, remove, or "
        "reorder input characters. Do not include explanations.\n\n"
        f"INPUT:\n{text}"
    )


def extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 3 and lines[-1].strip() == "```":
            stripped = "\n".join(lines[1:-1]).strip()
    decoder = json.JSONDecoder()
    for index, char in enumerate(stripped):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(stripped[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise ValueError("model did not return a JSON object")


class QwenPredictor:
    def __init__(self) -> None:
        from vllm import LLM, SamplingParams

        self.llm = LLM(
            model=QWEN_MODEL,
            quantization="awq",
            dtype="half",
            trust_remote_code=True,
            max_model_len=8192,
            gpu_memory_utilization=0.92,
        )
        self.sampling_params = SamplingParams(
            temperature=0,
            max_tokens=256,
            stop=["<|im_end|>"],
        )

    def predict(self, texts: list[str]) -> list[list[dict[str, Any]]]:
        prompts = [qwen_prompt(text) for text in texts]
        outputs = self.llm.generate(prompts, self.sampling_params, use_tqdm=False)
        result = []
        for text, output in zip(texts, outputs):
            generated = output.outputs[0].text if output.outputs else ""
            try:
                payload = extract_json_object(generated)
                values = payload.get("entities", [])
                if not isinstance(values, list):
                    values = []
            except ValueError:
                values = []
            result.append(normalize_entities(sentence_text=text, model_key="qwen25", values=values))
        return result


def _predictor(model_key: str) -> Any:
    if model_key == "ckip":
        return CkipPredictor()
    if model_key == "hanlp":
        return HanlpPredictor()
    if model_key == "qwen25":
        return QwenPredictor()
    raise ValueError(f"unknown model key: {model_key}")


def _output_dir(model_key: str, run_id: str) -> Path:
    return REMOTE_OUTPUT_ROOT / "ner_runs" / run_id / model_key


def _load_done_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {
        row["sentence_id"]
        for row in _read_jsonl(path)
        if row.get("status") == "ok" and isinstance(row.get("sentence_id"), str)
    }


def _write_metadata(
    model_key: str,
    *,
    run_id: str,
    input_run_id: str,
    requested_sentences: int,
    book_filter: str,
) -> None:
    output_dir = _output_dir(model_key, run_id)
    output_dir.mkdir(parents=True, exist_ok=True)
    metadata_path = output_dir / "run_metadata.json"
    if metadata_path.exists():
        return
    metadata = {
        "model_key": model_key,
        "model": {"ckip": CKIP_MODEL, "hanlp": HANLP_MODEL, "qwen25": QWEN_MODEL}[model_key],
        "run_id": run_id,
        "input_run_id": input_run_id,
        "canonical_labels": list(CANONICAL_LABELS),
        "requested_sentences": requested_sentences,
        "book_filter": book_filter,
        "created_at_epoch": time.time(),
    }
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_summary(model_key: str, run_id: str, summary: dict[str, Any]) -> None:
    output_dir = _output_dir(model_key, run_id)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def run_model(
    model_key: str,
    *,
    run_id: str,
    input_run_id: str,
    limit_sentences: int = 0,
    book_filter: str = "",
) -> dict[str, Any]:
    grouped = _load_input_rows(book_filter=book_filter, limit_sentences=limit_sentences)
    _write_metadata(
        model_key,
        run_id=run_id,
        input_run_id=input_run_id,
        requested_sentences=limit_sentences,
        book_filter=book_filter,
    )
    predictor = _predictor(model_key)
    output_dir = _output_dir(model_key, run_id)
    output_dir.mkdir(parents=True, exist_ok=True)

    summary: dict[str, Any] = {
        "model_key": model_key,
        "run_id": run_id,
        "input_sentences": sum(len(rows) for rows in grouped.values()),
        "processed_sentences": 0,
        "skipped_sentences": 0,
        "error_sentences": 0,
        "entity_count": 0,
        "label_counts": Counter(),
        "books": {},
    }

    for book_id, rows in grouped.items():
        output_path = output_dir / "sentences" / f"{book_id}.jsonl"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        done_ids = _load_done_ids(output_path)
        pending = [row for row in rows if row["sentence_id"] not in done_ids]
        summary["skipped_sentences"] += len(rows) - len(pending)
        book_counts = Counter()
        started = time.perf_counter()

        with output_path.open("a", encoding="utf-8") as output_file:
            for offset in range(0, len(pending), 64 if model_key != "qwen25" else 32):
                batch = pending[offset : offset + (64 if model_key != "qwen25" else 32)]
                try:
                    predictions = predictor.predict([row["text"] for row in batch])
                    if len(predictions) != len(batch):
                        raise RuntimeError("predictor returned a different number of rows")
                    batch_errors = [None] * len(batch)
                except Exception as exc:
                    predictions = [[] for _ in batch]
                    batch_errors = [repr(exc)] * len(batch)

                for row, entities, error in zip(batch, predictions, batch_errors):
                    result = {
                        "model_key": model_key,
                        "model": {"ckip": CKIP_MODEL, "hanlp": HANLP_MODEL, "qwen25": QWEN_MODEL}[model_key],
                        "run_id": run_id,
                        "sentence_id": row["sentence_id"],
                        "book_id": row["book_id"],
                        "page_number": row.get("page_number"),
                        "sentence_number": row.get("sentence_number"),
                        "text": row["text"],
                        "entities": entities,
                        "status": "error" if error else "ok",
                        "error": error,
                        "source_run_id": row.get("source_run_id"),
                        "source_agreement_ratio": row.get("source_agreement_ratio"),
                    }
                    output_file.write(json.dumps(result, ensure_ascii=False) + "\n")
                    summary["processed_sentences"] += 1
                    if error:
                        summary["error_sentences"] += 1
                    summary["entity_count"] += len(entities)
                    book_counts.update(entity["label"] for entity in entities)
                    summary["label_counts"].update(entity["label"] for entity in entities)
                output_file.flush()
                output_volume.commit()
                print(
                    f"{model_key} {book_id}: {min(offset + len(batch), len(pending))}/{len(pending)} "
                    f"pending, {time.perf_counter() - started:.1f}s",
                    flush=True,
                )

        summary["books"][book_id] = {
            "input_sentences": len(rows),
            "skipped_sentences": len(rows) - len(pending),
            "processed_sentences": len(pending),
            "entity_count": sum(book_counts.values()),
            "label_counts": dict(book_counts),
        }
        _write_summary(model_key, run_id, {**summary, "label_counts": dict(summary["label_counts"])})
        output_volume.commit()

    summary["label_counts"] = dict(summary["label_counts"])
    _write_summary(model_key, run_id, summary)
    output_volume.commit()
    return summary


app = modal.App(APP_NAME)


@app.function(
    image=ckip_image,
    gpu="A100-40GB",
    volumes={"/mnt/ner-output": output_volume, "/mnt/ner-model-cache": model_cache_volume},
    timeout=60 * 60 * 12,
)
def run_ckip(
    run_id: str,
    input_run_id: str,
    limit_sentences: int = 0,
    book_filter: str = "",
) -> dict[str, Any]:
    os.environ.setdefault("HF_HOME", str(REMOTE_MODEL_CACHE_ROOT / "huggingface"))
    return run_model(
        "ckip",
        run_id=run_id,
        input_run_id=input_run_id,
        limit_sentences=limit_sentences,
        book_filter=book_filter,
    )


@app.function(
    image=hanlp_image,
    gpu="A100-40GB",
    volumes={"/mnt/ner-output": output_volume, "/mnt/ner-model-cache": model_cache_volume},
    timeout=60 * 60 * 12,
)
def run_hanlp(
    run_id: str,
    input_run_id: str,
    limit_sentences: int = 0,
    book_filter: str = "",
) -> dict[str, Any]:
    os.environ.setdefault("HANLP_HOME", str(REMOTE_MODEL_CACHE_ROOT / "hanlp"))
    return run_model(
        "hanlp",
        run_id=run_id,
        input_run_id=input_run_id,
        limit_sentences=limit_sentences,
        book_filter=book_filter,
    )


@app.function(
    image=qwen_image,
    gpu="A100-40GB",
    volumes={"/mnt/ner-output": output_volume, "/root/.cache/huggingface": qwen_cache_volume},
    timeout=60 * 60 * 12,
)
def run_qwen25(
    run_id: str,
    input_run_id: str,
    limit_sentences: int = 0,
    book_filter: str = "",
) -> dict[str, Any]:
    os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "1")
    return run_model(
        "qwen25",
        run_id=run_id,
        input_run_id=input_run_id,
        limit_sentences=limit_sentences,
        book_filter=book_filter,
    )


@app.local_entrypoint()
def main(
    limit_sentences: int = 0,
    book_filter: str = "",
    wait: bool = True,
    model_key: str = "all",
) -> None:
    functions = {
        "ckip": run_ckip,
        "hanlp": run_hanlp,
        "qwen25": run_qwen25,
    }
    if model_key != "all" and model_key not in functions:
        raise ValueError(f"model_key must be one of all, {', '.join(functions)}")
    selected = functions.values() if model_key == "all" else [functions[model_key]]
    calls = [
        function.spawn(
            run_id=RUN_ID,
            input_run_id=INPUT_ROOT.parent.name,
            limit_sentences=limit_sentences,
            book_filter=book_filter,
        )
        for function in selected
    ]
    for call in calls:
        print(f"started Modal call {call.object_id}", flush=True)
    if wait:
        for call in calls:
            print(call.get(), flush=True)
