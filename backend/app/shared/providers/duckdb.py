from __future__ import annotations

from pathlib import Path

import duckdb


def connect_duckdb(path: Path) -> duckdb.DuckDBPyConnection:
    path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(path))
