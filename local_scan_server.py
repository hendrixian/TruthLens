from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HOST = "127.0.0.1"
PORT = 8765
PROJECT_ROOT = Path(__file__).resolve().parent
SCAN_DIR = PROJECT_ROOT / "scanned"


def sanitize_file_name(title: str) -> str:
    base = (title or "untitled_article").strip().lower()
    base = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", base)
    base = re.sub(r"\s+", "_", base)
    base = re.sub(r"_+", "_", base).strip("_")
    if not base:
        return "untitled_article"
    return base[:120]


def next_available_path(base_name: str) -> Path:
    candidate = SCAN_DIR / f"{base_name}.txt"
    if not candidate.exists():
        return candidate

    counter = 2
    while True:
        candidate = SCAN_DIR / f"{base_name}_{counter}.txt"
        if not candidate.exists():
            return candidate
        counter += 1


def build_payload(data: dict) -> str:
    lines = [
        f"title: {data.get('title', '')}",
        f"url: {data.get('url', '')}",
        f"captured_at: {datetime.now(timezone.utc).isoformat()}",
        "",
        "----- article_text -----",
        data.get("articleText", "") or "",
        "",
    ]
    return "\n".join(lines)


class ScanHandler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, payload: dict) -> None:
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.end_headers()
        self.wfile.write(encoded)

    def do_OPTIONS(self) -> None:
        self._send_json(200, {"ok": True})

    def do_POST(self) -> None:
        if self.path != "/scan":
            self._send_json(404, {"ok": False, "error": "Not found"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length)
            data = json.loads(raw.decode("utf-8") or "{}")

            title = str(data.get("title", "") or "")
            article_text = str(data.get("articleText", "") or "")
            url = str(data.get("url", "") or "")

            payload = build_payload(
                {
                    "title": title,
                    "articleText": article_text,
                    "url": url,
                }
            )

            SCAN_DIR.mkdir(parents=True, exist_ok=True)
            target = next_available_path(sanitize_file_name(title))
            target.write_text(payload, encoding="utf-8")

            self._send_json(
                200,
                {
                    "ok": True,
                    "file_path": str(target),
                },
            )
        except Exception as exc:
            self._send_json(500, {"ok": False, "error": str(exc)})

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), ScanHandler)
    print(f"TruthLens local scan server running on http://{HOST}:{PORT}")
    print(f"Saving files under: {SCAN_DIR}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

