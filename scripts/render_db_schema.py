#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.domains.market_data.schema import render_schema_markdown


def main() -> int:
    output_path = ROOT / "docs/generated/db-schema.md"
    output_path.write_text(render_schema_markdown(), encoding="utf-8")
    print(f"Rendered schema snapshot: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
