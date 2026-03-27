from __future__ import annotations

import json
from pathlib import Path


def load_json_fixture(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))
