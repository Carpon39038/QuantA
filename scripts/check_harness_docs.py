#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = [
    "AGENTS.md",
    "ARCHITECTURE.md",
    "pyproject.toml",
    "package.json",
    ".env.example",
    "docs/index.md",
    "docs/HARNESS.md",
    "docs/PLANS.md",
    "docs/QUALITY_SCORE.md",
    "docs/RELIABILITY.md",
    "docs/SECURITY.md",
    "docs/product-specs/index.md",
    "docs/exec-plans/active/2026-03-27-m0-harness-bootstrap.md",
    "docs/exec-plans/active/2026-03-27-m0-execution-harness-bootstrap.md",
    "docs/exec-plans/active/2026-03-27-m0-execution-harness-bootstrap.acceptance.json",
    "docs/exec-plans/active/2026-03-27-m0-execution-harness-bootstrap.progress.md",
    "docs/exec-plans/tech-debt-tracker.md",
    "docs/generated/db-schema.md",
    "scripts/check_execution_harness.py",
    "scripts/init_dev.sh",
    "scripts/smoke.sh",
    "scripts/app_smoke.py",
    "scripts/run_frontend.py",
    "backend/app/api/dev_server.py",
    "frontend/src/app/index.html",
]


def check_required_files() -> list[str]:
    errors: list[str] = []
    for relative_path in REQUIRED_FILES:
        path = ROOT / relative_path
        if not path.exists():
            errors.append(f"missing required file: {relative_path}")
    return errors


def check_product_spec_links() -> list[str]:
    errors: list[str] = []
    content = (ROOT / "docs/product-specs/index.md").read_text(encoding="utf-8")
    expected_mentions = [
        "A股分析系统需求路线图",
        "A股分析系统架构设计",
        "A股分析系统实施文档",
    ]
    for mention in expected_mentions:
        if mention not in content:
            errors.append(f"product spec index is missing: {mention}")
    return errors


def check_active_plan_task_lists() -> list[str]:
    errors: list[str] = []
    active_plan_dir = ROOT / "docs/exec-plans/active"

    for path in sorted(active_plan_dir.glob("*.md")):
        if path.name.endswith(".progress.md"):
            continue

        content = path.read_text(encoding="utf-8")
        if "- [ ]" not in content and "- [x]" not in content:
            errors.append(f"active plan should contain a checklist: {path.relative_to(ROOT)}")

    return errors


def main() -> int:
    errors = []
    errors.extend(check_required_files())
    errors.extend(check_product_spec_links())
    errors.extend(check_active_plan_task_lists())

    if errors:
        print("Harness docs check failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Harness docs check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
