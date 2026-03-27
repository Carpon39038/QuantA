#!/usr/bin/env python3

from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.app_wiring.settings import load_settings
from backend.app.domains.tasking.bootstrap import ensure_runtime_directories


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def fetch_json(url: str) -> dict[str, object]:
    with urllib.request.urlopen(url, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_text(url: str) -> str:
    with urllib.request.urlopen(url, timeout=5) as response:
        return response.read().decode("utf-8")


def wait_for(check_name: str, url: str, timeout_seconds: float = 12.0) -> None:
    deadline = time.time() + timeout_seconds
    last_error: Exception | None = None

    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1).read()
            return
        except Exception as exc:
            last_error = exc
            time.sleep(0.2)

    raise RuntimeError(f"{check_name} did not become ready: {last_error}")


def start_process(
    name: str,
    command: list[str],
    env: dict[str, str],
    log_path: Path,
) -> subprocess.Popen[bytes]:
    log_file = log_path.open("wb")
    process = subprocess.Popen(
        command,
        cwd=ROOT,
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )
    process.log_file = log_file  # type: ignore[attr-defined]
    print(f"[app-smoke] started {name}: {' '.join(command)}")
    print(f"[app-smoke] log: {log_path}")
    return process


def stop_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
    log_file = getattr(process, "log_file", None)
    if log_file is not None:
        log_file.close()


def main() -> int:
    settings = load_settings()
    ensure_runtime_directories(settings)

    backend_port = find_free_port()
    frontend_port = find_free_port()
    backend_origin = f"http://127.0.0.1:{backend_port}"
    frontend_origin = f"http://127.0.0.1:{frontend_port}"

    env = os.environ.copy()
    env.update(
        {
            "PYTHONUNBUFFERED": "1",
            "QUANTA_BACKEND_HOST": "127.0.0.1",
            "QUANTA_BACKEND_PORT": str(backend_port),
            "QUANTA_FRONTEND_HOST": "127.0.0.1",
            "QUANTA_FRONTEND_PORT": str(frontend_port),
        }
    )

    backend_log = settings.logs_dir / "app-smoke-backend.log"
    frontend_log = settings.logs_dir / "app-smoke-frontend.log"

    backend = start_process(
        "backend",
        ["pnpm", "run", "backend:dev"],
        env,
        backend_log,
    )
    frontend = None

    try:
        wait_for("backend health", f"{backend_origin}/health")

        frontend = start_process(
            "frontend",
            ["pnpm", "run", "frontend:dev"],
            env,
            frontend_log,
        )
        wait_for("frontend health", f"{frontend_origin}/health")

        backend_payload = fetch_json(f"{backend_origin}/api/v1/snapshot/latest")
        frontend_proxy_payload = fetch_json(f"{frontend_origin}/api/v1/snapshot/latest")
        frontend_html = fetch_text(f"{frontend_origin}/")
        frontend_js = fetch_text(f"{frontend_origin}/main.js")

        assert backend_payload["status"] == "READY"
        assert backend_payload["snapshot_id"] == frontend_proxy_payload["snapshot_id"]
        assert backend_payload["market_overview"]["trade_date"] == "2026-03-27"
        assert "QuantA" in frontend_html
        assert "fetchLatestSnapshot" in frontend_js
        assert "观察名单" in frontend_html

        print("[app-smoke] backend and frontend are healthy")
        print(
            "[app-smoke] proxy snapshot id:",
            frontend_proxy_payload["snapshot_id"],
        )
        print("[app-smoke] frontend shell loaded")
        return 0
    finally:
        if frontend is not None:
            stop_process(frontend)
        stop_process(backend)


if __name__ == "__main__":
    raise SystemExit(main())
