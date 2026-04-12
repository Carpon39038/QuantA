#!/usr/bin/env python3
"""Launch the Vite dev server for the React frontend."""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.app_wiring.settings import load_settings
from backend.app.shared.telemetry.logging import configure_logging

LOGGER = logging.getLogger("quanta.frontend.dev_server")


def main() -> int:
    configure_logging()
    settings = load_settings()

    frontend_dir = ROOT / "frontend"
    if not (frontend_dir / "node_modules").exists():
        LOGGER.info("Installing frontend dependencies...")
        subprocess.run(["npm", "install"], cwd=str(frontend_dir), check=True)

    LOGGER.info("Starting Vite dev server on %s", settings.frontend_origin)
    try:
        subprocess.run(
            ["npm", "run", "dev"],
            cwd=str(frontend_dir),
        )
    except KeyboardInterrupt:
        LOGGER.info("Stopping frontend dev server")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
