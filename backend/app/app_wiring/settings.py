from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


def _parse_port(name: str, default: int) -> int:
    raw_value = os.environ.get(name, str(default))
    try:
        return int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {raw_value!r}") from exc


def _parse_int(name: str, default: int) -> int:
    raw_value = os.environ.get(name, str(default))
    try:
        return int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {raw_value!r}") from exc


def _parse_optional_str(name: str) -> str | None:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return None
    normalized = raw_value.strip()
    return normalized or None


def _resolve_runtime_path(root_dir: Path, raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return root_dir / path


@dataclass(frozen=True)
class AppSettings:
    root_dir: Path
    data_dir: Path
    duckdb_dir: Path
    duckdb_path: Path
    logs_dir: Path
    queue_dir: Path
    alerts_path: Path
    fixture_path: Path
    source_fixture_dir: Path
    disclosure_fixture_dir: Path
    source_provider: str
    disclosure_provider: str
    source_symbols: tuple[str, ...]
    tushare_token: str | None
    tushare_exchange: str
    source_fail_first_n: int
    task_max_retries: int
    task_retry_backoff_seconds: int
    scheduler_poll_interval_seconds: int
    backend_host: str
    backend_port: int
    frontend_host: str
    frontend_port: int

    @property
    def backend_origin(self) -> str:
        return f"http://{self.backend_host}:{self.backend_port}"

    @property
    def frontend_origin(self) -> str:
        return f"http://{self.frontend_host}:{self.frontend_port}"


def load_settings() -> AppSettings:
    root_dir = Path(__file__).resolve().parents[3]
    data_dir = _resolve_runtime_path(
        root_dir,
        os.environ.get("QUANTA_RUNTIME_DATA_DIR", "data"),
    )
    duckdb_path = _resolve_runtime_path(
        root_dir,
        os.environ.get("QUANTA_DUCKDB_PATH", "data/duckdb/quanta.duckdb"),
    )

    source_symbols = tuple(
        symbol.strip()
        for symbol in os.environ.get(
            "QUANTA_SOURCE_SYMBOLS",
            "300750.SZ,002475.SZ,688017.SH",
        ).split(",")
        if symbol.strip()
    )

    return AppSettings(
        root_dir=root_dir,
        data_dir=data_dir,
        duckdb_dir=data_dir / "duckdb",
        duckdb_path=duckdb_path,
        logs_dir=data_dir / "logs",
        queue_dir=data_dir / "queue",
        alerts_path=_resolve_runtime_path(
            root_dir,
            os.environ.get("QUANTA_ALERTS_PATH", "data/logs/alerts.jsonl"),
        ),
        fixture_path=root_dir / "backend/app/fixtures/published_snapshot.json",
        source_fixture_dir=_resolve_runtime_path(
            root_dir,
            os.environ.get(
                "QUANTA_SOURCE_FIXTURE_DIR",
                "backend/app/fixtures/source_snapshots",
            ),
        ),
        disclosure_fixture_dir=_resolve_runtime_path(
            root_dir,
            os.environ.get(
                "QUANTA_DISCLOSURE_FIXTURE_DIR",
                "backend/app/fixtures/source_disclosures",
            ),
        ),
        source_provider=os.environ.get("QUANTA_SOURCE_PROVIDER", "fixture_json"),
        disclosure_provider=os.environ.get("QUANTA_DISCLOSURE_PROVIDER", "auto"),
        source_symbols=source_symbols,
        tushare_token=_parse_optional_str("QUANTA_TUSHARE_TOKEN"),
        tushare_exchange=os.environ.get("QUANTA_TUSHARE_EXCHANGE", "SSE"),
        source_fail_first_n=_parse_int("QUANTA_SOURCE_FAIL_FIRST_N", 0),
        task_max_retries=_parse_int("QUANTA_TASK_MAX_RETRIES", 2),
        task_retry_backoff_seconds=_parse_int(
            "QUANTA_TASK_RETRY_BACKOFF_SECONDS",
            5,
        ),
        scheduler_poll_interval_seconds=_parse_int(
            "QUANTA_SCHEDULER_POLL_INTERVAL_SECONDS",
            5,
        ),
        backend_host=os.environ.get("QUANTA_BACKEND_HOST", "127.0.0.1"),
        backend_port=_parse_port("QUANTA_BACKEND_PORT", 8765),
        frontend_host=os.environ.get("QUANTA_FRONTEND_HOST", "127.0.0.1"),
        frontend_port=_parse_port("QUANTA_FRONTEND_PORT", 4173),
    )
