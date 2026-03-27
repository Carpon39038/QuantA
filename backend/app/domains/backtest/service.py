from __future__ import annotations


def build_backtest_summary(snapshot: dict[str, object]) -> dict[str, object]:
    return dict(snapshot["backtest"])
