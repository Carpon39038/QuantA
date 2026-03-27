from __future__ import annotations


def build_market_overview(snapshot: dict[str, object]) -> dict[str, object]:
    return dict(snapshot["market_overview"])
