#!/usr/bin/env python3
"""Serve the midterm report locally and persist on-page review feedback.

Run from the repository root:
    python3 reports/review_server.py
Then open http://127.0.0.1:8765
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


REPORTS_DIR = Path(__file__).resolve().parent
FEEDBACK_PATH = REPORTS_DIR / "feedback.jsonl"
MAX_MESSAGE_LENGTH = 4000


class ReviewHandler(SimpleHTTPRequestHandler):
    """Serve report assets and accept deliberately small local review messages."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(REPORTS_DIR), **kwargs)

    def do_GET(self) -> None:  # noqa: N802
        if self.path in {"/", "/index.html"}:
            self.path = "/midterm_review.html"
        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/api/feedback":
            self.send_error(HTTPStatus.NOT_FOUND, "Unknown endpoint")
            return
        content_length = self.headers.get("Content-Length")
        try:
            size = int(content_length or "0")
        except ValueError:
            size = 0
        if not 2 <= size <= MAX_MESSAGE_LENGTH + 300:
            self._json_response(HTTPStatus.BAD_REQUEST, {"error": "Invalid request size"})
            return
        try:
            payload = json.loads(self.rfile.read(size).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._json_response(HTTPStatus.BAD_REQUEST, {"error": "Expected JSON"})
            return
        section = payload.get("section")
        message = payload.get("message")
        if not isinstance(section, str) or not isinstance(message, str):
            self._json_response(HTTPStatus.BAD_REQUEST, {"error": "Invalid feedback fields"})
            return
        section, message = section.strip(), message.strip()
        if not section or not message or len(section) > 120 or len(message) > MAX_MESSAGE_LENGTH:
            self._json_response(HTTPStatus.BAD_REQUEST, {"error": "Feedback is empty or too long"})
            return
        record = {
            "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "section": section,
            "message": message,
        }
        with FEEDBACK_PATH.open("a", encoding="utf-8") as output:
            output.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._json_response(HTTPStatus.CREATED, {"ok": True})

    def _json_response(self, status: HTTPStatus, payload: dict[str, object]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the locally reviewable midterm report.")
    parser.add_argument("--host", default="127.0.0.1", help="Local bind address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8765, help="TCP port (default: 8765)")
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), ReviewHandler)
    print(f"Report: http://{args.host}:{args.port}")
    print(f"Feedback file: {FEEDBACK_PATH}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
