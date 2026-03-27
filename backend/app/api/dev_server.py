from __future__ import annotations

import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from backend.app.app_wiring.dev_bootstrap import bootstrap_dev_runtime
from backend.app.app_wiring.container import build_container
from backend.app.app_wiring.settings import load_settings
from backend.app.domains.backtest.queue import enqueue_backtest_request
from backend.app.domains.tasking.bootstrap import ensure_runtime_directories
from backend.app.domains.tasking.queue import enqueue_service_task
from backend.app.shared.telemetry.logging import configure_logging


LOGGER = logging.getLogger("quanta.backend.dev_server")


def _make_handler() -> type[BaseHTTPRequestHandler]:
    container = build_container()

    class QuantARequestHandler(BaseHTTPRequestHandler):
        server_version = "QuantADevServer/0.1"

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)

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

            path_parts = parsed.path.strip("/").split("/")
            if len(path_parts) == 5 and path_parts[:3] == ["api", "v1", "stocks"]:
                symbol = path_parts[3]

                try:
                    if path_parts[4] == "snapshot":
                        self._send_json(
                            200,
                            container.stock_snapshot_payload(
                                symbol=symbol,
                                snapshot_id=_query_value(query, "snapshot_id"),
                                raw_snapshot_id=_query_value(query, "raw_snapshot_id"),
                                price_basis=_query_value(query, "price_basis"),
                            ),
                        )
                        return

                    if path_parts[4] == "kline":
                        self._send_json(
                            200,
                            container.stock_kline_payload(
                                symbol=symbol,
                                dataset=_query_value(query, "dataset", "price_series"),
                                snapshot_id=_query_value(query, "snapshot_id"),
                                raw_snapshot_id=_query_value(query, "raw_snapshot_id"),
                                price_basis=_query_value(query, "price_basis"),
                                date_from=_query_value(query, "date_from"),
                                date_to=_query_value(query, "date_to"),
                            ),
                        )
                        return

                    if path_parts[4] == "indicators":
                        self._send_json(
                            200,
                            container.stock_indicators_payload(
                                symbol=symbol,
                                snapshot_id=_query_value(query, "snapshot_id"),
                                price_basis=_query_value(query, "price_basis"),
                                date_from=_query_value(query, "date_from"),
                                date_to=_query_value(query, "date_to"),
                            ),
                        )
                        return

                    if path_parts[4] == "capital-flow":
                        self._send_json(
                            200,
                            container.stock_capital_flow_payload(
                                symbol=symbol,
                                snapshot_id=_query_value(query, "snapshot_id"),
                                date_from=_query_value(query, "date_from"),
                                date_to=_query_value(query, "date_to"),
                            ),
                        )
                        return
                except LookupError as exc:
                    self._send_json(
                        404,
                        {"error": "not_found", "message": str(exc)},
                    )
                    return
                except ValueError as exc:
                    self._send_json(
                        400,
                        {"error": "bad_request", "message": str(exc)},
                    )
                    return

            if len(path_parts) == 5 and path_parts[:4] == ["api", "v1", "screener", "runs"]:
                run_key = path_parts[4]

                try:
                    if run_key == "latest":
                        self._send_json(
                            200,
                            container.screener_run_payload(
                                snapshot_id=_query_value(query, "snapshot_id"),
                            ),
                        )
                        return

                    self._send_json(
                        200,
                        container.screener_run_payload(run_id=run_key),
                    )
                    return
                except LookupError as exc:
                    self._send_json(
                        404,
                        {"error": "not_found", "message": str(exc)},
                    )
                    return

            if len(path_parts) == 6 and path_parts[:4] == ["api", "v1", "screener", "runs"]:
                run_key = path_parts[4]
                if path_parts[5] == "results":
                    try:
                        payload = container.screener_run_payload(run_id=run_key)
                        self._send_json(
                            200,
                            {
                                "api_contract_version": payload["api_contract_version"],
                                "run_id": payload["run_id"],
                                "snapshot_id": payload["snapshot_id"],
                                "results": payload["results"],
                            },
                        )
                        return
                    except LookupError as exc:
                        self._send_json(
                            404,
                            {"error": "not_found", "message": str(exc)},
                        )
                        return

            if len(path_parts) == 5 and path_parts[:4] == ["api", "v1", "backtests", "runs"]:
                backtest_key = path_parts[4]

                try:
                    if backtest_key == "latest":
                        self._send_json(
                            200,
                            container.backtest_run_payload(
                                snapshot_id=_query_value(query, "snapshot_id"),
                            ),
                        )
                        return

                    self._send_json(
                        200,
                        container.backtest_run_payload(backtest_id=backtest_key),
                    )
                    return
                except LookupError as exc:
                    self._send_json(
                        404,
                        {"error": "not_found", "message": str(exc)},
                    )
                    return

            if len(path_parts) == 6 and path_parts[:4] == ["api", "v1", "backtests", "runs"]:
                backtest_key = path_parts[4]

                try:
                    payload = container.backtest_run_payload(backtest_id=backtest_key)
                    if path_parts[5] == "trades":
                        self._send_json(
                            200,
                            {
                                "api_contract_version": payload["api_contract_version"],
                                "backtest_id": payload["backtest_id"],
                                "trades": payload["trades"],
                            },
                        )
                        return
                    if path_parts[5] == "equity-curve":
                        self._send_json(
                            200,
                            {
                                "api_contract_version": payload["api_contract_version"],
                                "backtest_id": payload["backtest_id"],
                                "equity_curve": payload["equity_curve"],
                            },
                        )
                        return
                except LookupError as exc:
                    self._send_json(
                        404,
                        {"error": "not_found", "message": str(exc)},
                    )
                    return

            if parsed.path == "/api/v1/runtime":
                self._send_json(
                    200,
                    {
                        "backend_origin": container.settings.backend_origin,
                        "frontend_origin": container.settings.frontend_origin,
                        "data_dir": str(container.settings.data_dir),
                        "duckdb_path": str(container.settings.duckdb_path),
                        "seed_fixture_path": str(container.settings.fixture_path),
                    },
                )
                return

            if parsed.path == "/api/v1/tasks/runs":
                self._send_json(
                    200,
                    container.task_runs_payload(
                        snapshot_id=_query_value(query, "snapshot_id"),
                    ),
                )
                return

            if parsed.path == "/api/v1/system/health":
                self._send_json(200, container.system_health_payload())
                return

            self._send_json(404, {"error": "not_found", "path": parsed.path})

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            body = self._read_json_body()

            if parsed.path == "/api/v1/tasks/daily-sync/run":
                try:
                    queued_task = enqueue_service_task(
                        container.settings,
                        task_name="daily_sync",
                        snapshot_id=_query_value(query, "snapshot_id")
                        or _body_value(body, "snapshot_id"),
                    )
                    self._send_json(
                        202,
                        {
                            "status": "accepted",
                            "task": queued_task,
                        },
                    )
                    return
                except LookupError as exc:
                    self._send_json(
                        404,
                        {"error": "not_found", "message": str(exc)},
                    )
                    return
                except ValueError as exc:
                    self._send_json(
                        400,
                        {"error": "bad_request", "message": str(exc)},
                    )
                    return

            if parsed.path == "/api/v1/tasks/daily-screener/run":
                try:
                    queued_task = enqueue_service_task(
                        container.settings,
                        task_name="daily_screener",
                        snapshot_id=_query_value(query, "snapshot_id")
                        or _body_value(body, "snapshot_id"),
                    )
                    self._send_json(
                        202,
                        {
                            "status": "accepted",
                            "task": queued_task,
                        },
                    )
                    return
                except LookupError as exc:
                    self._send_json(
                        404,
                        {"error": "not_found", "message": str(exc)},
                    )
                    return
                except ValueError as exc:
                    self._send_json(
                        400,
                        {"error": "bad_request", "message": str(exc)},
                    )
                    return

            if parsed.path == "/api/v1/backtests/runs":
                try:
                    queued_request = enqueue_backtest_request(
                        container.settings,
                        snapshot_id=_query_value(query, "snapshot_id")
                        or _body_value(body, "snapshot_id"),
                        top_n=_body_int_value(body, "top_n"),
                    )
                    self._send_json(
                        202,
                        {
                            "status": "accepted",
                            "backtest": queued_request,
                        },
                    )
                    return
                except LookupError as exc:
                    self._send_json(
                        404,
                        {"error": "not_found", "message": str(exc)},
                    )
                    return
                except ValueError as exc:
                    self._send_json(
                        400,
                        {"error": "bad_request", "message": str(exc)},
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

        def _read_json_body(self) -> dict[str, object]:
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length <= 0:
                return {}

            raw_body = self.rfile.read(content_length)
            if not raw_body:
                return {}

            try:
                payload = json.loads(raw_body.decode("utf-8"))
            except json.JSONDecodeError:
                return {}
            return payload if isinstance(payload, dict) else {}

    return QuantARequestHandler


def _query_value(
    query: dict[str, list[str]],
    name: str,
    default: str | None = None,
) -> str | None:
    values = query.get(name)
    if not values:
        return default
    value = values[-1]
    return value if value != "" else default


def _body_value(body: dict[str, object], name: str) -> str | None:
    value = body.get(name)
    return value if isinstance(value, str) and value != "" else None


def _body_int_value(body: dict[str, object], name: str) -> int | None:
    value = body.get(name)
    if value is None:
        return None
    return int(value)


def main() -> int:
    configure_logging()
    settings = load_settings()
    ensure_runtime_directories(settings)
    bootstrap_dev_runtime(settings)

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
