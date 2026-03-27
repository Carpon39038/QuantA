#!/usr/bin/env python3

from __future__ import annotations

import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import logging
from pathlib import Path
import sys
import urllib.request
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.app_wiring.settings import load_settings
from backend.app.domains.tasking.bootstrap import ensure_runtime_directories
from backend.app.shared.telemetry.logging import configure_logging


LOGGER = logging.getLogger("quanta.frontend.dev_server")


def _make_handler(backend_origin: str) -> type[SimpleHTTPRequestHandler]:
    app_dir = str((load_settings().root_dir / "frontend/src/app").resolve())

    class FrontendRequestHandler(SimpleHTTPRequestHandler):
        def __init__(self, *args: object, **kwargs: object) -> None:
            super().__init__(*args, directory=app_dir, **kwargs)

        def do_GET(self) -> None:
            parsed = urlparse(self.path)

            if parsed.path == "/health":
                self._send_json(
                    200,
                    {
                        "status": "ok",
                        "service": "quanta-frontend",
                        "proxy_backend": backend_origin,
                    },
                )
                return

            if parsed.path.startswith("/api/"):
                self._proxy_to_backend(parsed.path)
                return

            if parsed.path == "/":
                self.path = "/index.html"

            super().do_GET()

        def end_headers(self) -> None:
            self.send_header("Cache-Control", "no-store")
            super().end_headers()

        def log_message(self, format: str, *args: object) -> None:
            LOGGER.info("%s - %s", self.address_string(), format % args)

        def _proxy_to_backend(self, path: str) -> None:
            with urllib.request.urlopen(f"{backend_origin}{path}", timeout=5) as response:
                body = response.read()
                self.send_response(response.status)
                self.send_header(
                    "Content-Type",
                    response.headers.get_content_type() + "; charset=utf-8",
                )
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        def _send_json(self, status_code: int, payload: dict[str, object]) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return FrontendRequestHandler


def main() -> int:
    configure_logging()
    settings = load_settings()
    ensure_runtime_directories(settings)

    server = ThreadingHTTPServer(
        (settings.frontend_host, settings.frontend_port),
        _make_handler(settings.backend_origin),
    )

    LOGGER.info("Starting frontend dev server on %s", settings.frontend_origin)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        LOGGER.info("Stopping frontend dev server")
    finally:
        server.server_close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
