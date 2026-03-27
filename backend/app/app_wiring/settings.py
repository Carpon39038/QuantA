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
    fixture_path: Path
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

    return AppSettings(
        root_dir=root_dir,
        data_dir=data_dir,
        duckdb_dir=data_dir / "duckdb",
        duckdb_path=duckdb_path,
        logs_dir=data_dir / "logs",
        queue_dir=data_dir / "queue",
        fixture_path=root_dir / "backend/app/fixtures/published_snapshot.json",
        backend_host=os.environ.get("QUANTA_BACKEND_HOST", "127.0.0.1"),
        backend_port=_parse_port("QUANTA_BACKEND_PORT", 8765),
        frontend_host=os.environ.get("QUANTA_FRONTEND_HOST", "127.0.0.1"),
        frontend_port=_parse_port("QUANTA_FRONTEND_PORT", 4173),
    )
