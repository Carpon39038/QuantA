from __future__ import annotations

from backend.app.app_wiring.settings import AppSettings, load_settings


def ensure_runtime_directories(settings: AppSettings) -> dict[str, str]:
    runtime_paths = {
        "data_dir": settings.data_dir,
        "duckdb_dir": settings.duckdb_dir,
        "logs_dir": settings.logs_dir,
        "queue_dir": settings.queue_dir,
    }

    for path in runtime_paths.values():
        path.mkdir(parents=True, exist_ok=True)

    return {name: str(path) for name, path in runtime_paths.items()}


def main() -> int:
    settings = load_settings()
    runtime_paths = ensure_runtime_directories(settings)
    print("QuantA runtime directories ready:")
    for name, path in runtime_paths.items():
        print(f"- {name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
