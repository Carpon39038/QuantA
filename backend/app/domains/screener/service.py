from __future__ import annotations


def build_screener_summary(snapshot: dict[str, object]) -> dict[str, object]:
    return dict(snapshot["screener"])
