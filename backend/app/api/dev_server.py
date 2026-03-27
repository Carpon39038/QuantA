from __future__ import annotations

import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from backend.app.app_wiring.container import build_container
from backend.app.app_wiring.settings import load_settings
from backend.app.domains.tasking.bootstrap import ensure_runtime_directories
from backend.app.shared.telemetry.logging import configure_logging


LOGGER = logging.getLogger("quanta.backend.dev_server")


def _make_handler() -> type[BaseHTTPRequestHandler]:
    container = build_container()

    class QuantARequestHandler(BaseHTTPRequestHandler):
        server_version = "QuantADevServer/0.1"

        def do_GET(self) -> None:
            parsed = urlparse(self.path)

            if parsed.path == "/health":
                self._send_json(
                    200,
                    {
                        "status": "ok",
                        "service": "quanta-backend",
                        "snapshot_id": container.latest_snapshot_payload()["snapshot_id"],
                    },
                )
                return

            if parsed.path == "/api/v1/snapshot/latest":
                self._send_json(200, container.latest_snapshot_payload())
                return

            if parsed.path == "/api/v1/runtime":
                self._send_json(
                    200,
                    {
                        "backend_origin": container.settings.backend_origin,
                        "frontend_origin": container.settings.frontend_origin,
                        "data_dir": str(container.settings.data_dir),
                        "fixture_path": str(container.settings.fixture_path),
                    },
                )
                return

            self._send_json(404, {"error": "not_found", "path": parsed.path})

        def log_message(self, format: str, *args: object) -> None:
            LOGGER.info("%s - %s", self.address_string(), format % args)

        def _send_json(self, status_code: int, payload: dict[str, object]) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)

    return QuantARequestHandler


def main() -> int:
    configure_logging()
    settings = load_settings()
    ensure_runtime_directories(settings)

    server = ThreadingHTTPServer(
        (settings.backend_host, settings.backend_port),
        _make_handler(),
    )

    LOGGER.info("Starting backend dev server on %s", settings.backend_origin)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        LOGGER.info("Stopping backend dev server")
    finally:
        server.server_close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
