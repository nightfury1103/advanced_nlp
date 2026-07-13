from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from scripts.sentence_separation import (
    DEFAULT_OUTPUT_ROOT,
    PageText,
    SentenceSegment,
    load_manifest_pages,
    segment_text,
    write_sentence_run,
)


MODEL_SENTENCE_MODEL = "model_sentence_separation"
DEFAULT_BASE_URL = "https://api.openai.com/v1"


class ModelResponseError(ValueError):
    pass


def load_dotenv(path: Path = Path(".env")) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass
class OpenAICompatibleClient:
    api_key: str
    model: str
    base_url: str = DEFAULT_BASE_URL
    timeout_seconds: float = 120.0
    use_response_format: bool = True

    def complete(self, prompt: str) -> str:
        url = self.base_url.rstrip("/") + "/chat/completions"
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You separate historical Chinese/Han text into sentence units. "
                        "Return strict JSON only."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
        }
        if self.use_response_format:
            payload["response_format"] = {"type": "json_object"}
        request = urllib.request.Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise ModelResponseError(f"model API HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise ModelResponseError(f"model API request failed: {exc}") from exc
        return data["choices"][0]["message"]["content"]


def strip_fenced_json(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    if len(lines) >= 3 and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1]).strip()
    return stripped


def parse_model_sentences(text: str) -> list[str]:
    raw = strip_fenced_json(text)
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ModelResponseError("model did not return valid JSON") from exc

    if isinstance(payload, list):
        values = payload
    elif isinstance(payload, dict) and isinstance(payload.get("sentences"), list):
        values = payload["sentences"]
    else:
        raise ModelResponseError("model JSON must be a list or contain a sentences list")

    sentences = []
    for value in values:
        if isinstance(value, str):
            sentence = value.strip()
        elif isinstance(value, dict) and isinstance(value.get("text"), str):
            sentence = value["text"].strip()
        else:
            raise ModelResponseError("each sentence must be a string or an object with text")
        if sentence:
            sentences.append(sentence)
    return sentences


def normalize_for_validation(text: str) -> str:
    return "".join(text.split())


def build_prompt(text: str) -> str:
    return (
        "Midterm guideline context: for the HVH image-input track, the required "
        "post-OCR task is sentence separation. The guideline allows LLM-based "
        "methods.\n\n"
        "Task: split the following voted OCR text into sentence units.\n"
        "Rules:\n"
        "1. Do not translate.\n"
        "2. Do not correct OCR.\n"
        "3. Do not add, remove, or reorder characters.\n"
        "4. Preserve punctuation if it already exists.\n"
        "5. Return JSON exactly as {\"sentences\":[\"...\"]}.\n\n"
        f"OCR text:\n{text}"
    )


class ModelSentenceSegmenter:
    def __init__(self, *, client: object, model_name: str):
        self.client = client
        self.model_name = model_name

    def segment_text(self, text: str) -> list[SentenceSegment]:
        if not text.strip():
            return []
        try:
            response = self.client.complete(build_prompt(text))
            sentences = parse_model_sentences(response)
            if normalize_for_validation("".join(sentences)) != normalize_for_validation(text):
                raise ModelResponseError("model changed the input text")
            return [SentenceSegment(sentence, "model") for sentence in sentences]
        except Exception:
            return [
                SentenceSegment(segment.text, "model_fallback")
                for segment in segment_text(text)
            ]


def write_model_sentence_run(
    pages: list[PageText],
    *,
    output_root: Path,
    run_id: str,
    segmenter: ModelSentenceSegmenter,
    max_workers: int = 1,
) -> dict:
    return write_sentence_run(
        pages,
        output_root=output_root,
        run_id=run_id,
        segmenter=segmenter.segment_text,
        output_model=MODEL_SENTENCE_MODEL,
        page_metadata={"segment_model": segmenter.model_name},
        sentence_metadata={"segment_model": segmenter.model_name},
        max_workers=max_workers,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Use an LLM to separate voted OCR output into sentence units.")
    parser.add_argument("--input-run-dir", action="append", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument(
        "--run-id",
        default="model-sentence-separation-" + dt.datetime.now().strftime("%Y%m%d-%H%M%S"),
    )
    parser.add_argument("--model", required=True, help="Model name accepted by the configured chat-completions API.")
    parser.add_argument("--base-url", default=os.getenv("MODEL_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--api-key-env", default="MODEL_API_KEY")
    parser.add_argument("--timeout-seconds", type=float, default=120.0)
    parser.add_argument("--limit-pages", type=int, help="Optional smoke-test limit before a full run.")
    parser.add_argument("--workers", type=int, default=1, help="Concurrent page-level model requests.")
    parser.add_argument(
        "--no-response-format",
        action="store_true",
        help="Do not send OpenAI JSON response_format; useful for vLLM servers with broken guided JSON decoding.",
    )
    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    load_dotenv()
    return build_parser().parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    api_key = os.getenv(args.api_key_env) or os.getenv("OPENAI_API_KEY")
    if not api_key:
        print(
            f"error: set {args.api_key_env} or OPENAI_API_KEY before running model sentence separation",
            file=sys.stderr,
        )
        return 2

    try:
        pages = load_manifest_pages(args.input_run_dir, repo_root=Path.cwd())
        if args.limit_pages is not None:
            pages = pages[: args.limit_pages]
        client = OpenAICompatibleClient(
            api_key=api_key,
            model=args.model,
            base_url=args.base_url,
            timeout_seconds=args.timeout_seconds,
            use_response_format=not args.no_response_format,
        )
        segmenter = ModelSentenceSegmenter(client=client, model_name=args.model)
        summary = write_model_sentence_run(
            pages,
            output_root=args.output_root,
            run_id=args.run_id,
            segmenter=segmenter,
            max_workers=args.workers,
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
