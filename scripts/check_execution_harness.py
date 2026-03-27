#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = (
    ROOT / "docs/exec-plans/active/2026-03-27-m0-execution-harness-bootstrap.md"
)
ACCEPTANCE_PATH = (
    ROOT
    / "docs/exec-plans/active/2026-03-27-m0-execution-harness-bootstrap.acceptance.json"
)
PROGRESS_PATH = (
    ROOT
    / "docs/exec-plans/active/2026-03-27-m0-execution-harness-bootstrap.progress.md"
)

REQUIRED_PROGRESS_HEADINGS = [
    "## Current State",
    "## Last Completed",
    "## Verification",
    "## Next Step",
]

DOC_EXPECTATIONS = {
    "docs/HARNESS.md": [
        "Minimal Execution Harness",
        "scripts/init_dev.sh",
        "scripts/smoke.sh",
        "app-level smoke",
        "acceptance",
        "progress",
    ],
    "docs/PLANS.md": [
        "Long-Running Rule",
        "Done When",
        "Verify By",
        "acceptance",
        "progress",
    ],
    "docs/QUALITY_SCORE.md": [
        "执行 harness",
        "后端代码骨架",
        "前端代码骨架",
    ],
    "docs/exec-plans/tech-debt-tracker.md": [
        "Execution Harness",
        "app-level smoke",
    ],
}


def check_required_paths() -> list[str]:
    errors: list[str] = []
    for path in [PLAN_PATH, ACCEPTANCE_PATH, PROGRESS_PATH]:
        if not path.exists():
            errors.append(f"missing execution harness artifact: {path.relative_to(ROOT)}")
    return errors


def check_plan_structure() -> list[str]:
    errors: list[str] = []
    content = PLAN_PATH.read_text(encoding="utf-8")

    required_sections = [
        "## Goal",
        "## Scope",
        "## Non-Goals",
        "## Done When",
        "## Verify By",
        "## Tasks",
        "## Decisions",
        "## Status",
    ]

    for section in required_sections:
        if section not in content:
            errors.append(f"execution harness plan is missing section: {section}")

    return errors


def check_progress_structure() -> list[str]:
    errors: list[str] = []
    content = PROGRESS_PATH.read_text(encoding="utf-8")

    for heading in REQUIRED_PROGRESS_HEADINGS:
        if heading not in content:
            errors.append(f"progress handoff is missing heading: {heading}")

    return errors


def check_doc_expectations() -> list[str]:
    errors: list[str] = []
    for relative_path, expected_mentions in DOC_EXPECTATIONS.items():
        content = (ROOT / relative_path).read_text(encoding="utf-8")
        for mention in expected_mentions:
            if mention not in content:
                errors.append(f"{relative_path} is missing expected mention: {mention}")
    return errors


def load_acceptance() -> tuple[dict[str, object] | None, list[str]]:
    try:
        data = json.loads(ACCEPTANCE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, [f"acceptance file is not valid JSON: {exc}"]

    if not isinstance(data, dict):
        return None, ["acceptance file must be a JSON object"]

    return data, []


def check_acceptance_items(
    acceptance: dict[str, object],
    require_all_passing: bool,
) -> tuple[list[str], dict[str, object]]:
    errors: list[str] = []
    summary: dict[str, object] = {
        "total": 0,
        "passing": 0,
        "pending_ids": [],
    }

    required_top_level_keys = ["plan_id", "title", "status", "updated_at", "items"]
    for key in required_top_level_keys:
        if key not in acceptance:
            errors.append(f"acceptance file is missing key: {key}")

    items = acceptance.get("items")
    if not isinstance(items, list) or not items:
        errors.append("acceptance file must contain a non-empty items list")
        return errors, summary

    seen_ids: set[str] = set()
    pending_ids: list[str] = []
    passing = 0

    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            errors.append(f"acceptance item #{index} must be an object")
            continue

        required_item_keys = [
            "id",
            "title",
            "priority",
            "description",
            "artifacts",
            "verify_steps",
            "passes",
        ]
        for key in required_item_keys:
            if key not in item:
                errors.append(f"acceptance item #{index} is missing key: {key}")

        item_id = item.get("id")
        if not isinstance(item_id, str) or not item_id:
            errors.append(f"acceptance item #{index} has invalid id")
        elif item_id in seen_ids:
            errors.append(f"duplicate acceptance item id: {item_id}")
        else:
            seen_ids.add(item_id)

        priority = item.get("priority")
        if not isinstance(priority, int) or priority < 1 or priority > 3:
            errors.append(
                f"acceptance item {item_id or f'#{index}'} has invalid priority: {priority}"
            )

        artifacts = item.get("artifacts")
        if not isinstance(artifacts, list) or not artifacts:
            errors.append(f"acceptance item {item_id or f'#{index}'} must list artifacts")
        else:
            for artifact in artifacts:
                if not isinstance(artifact, str) or not artifact:
                    errors.append(
                        f"acceptance item {item_id or f'#{index}'} has invalid artifact path"
                    )
                    continue
                artifact_path = ROOT / artifact
                if not artifact_path.exists():
                    errors.append(
                        f"acceptance item {item_id or f'#{index}'} references missing artifact: {artifact}"
                    )

        verify_steps = item.get("verify_steps")
        if not isinstance(verify_steps, list) or not verify_steps:
            errors.append(
                f"acceptance item {item_id or f'#{index}'} must define verify_steps"
            )
        else:
            for step in verify_steps:
                if not isinstance(step, str) or not step:
                    errors.append(
                        f"acceptance item {item_id or f'#{index}'} has invalid verify step"
                    )

        passes = item.get("passes")
        if not isinstance(passes, bool):
            errors.append(
                f"acceptance item {item_id or f'#{index}'} must use a boolean passes flag"
            )
            continue

        if passes:
            passing += 1
        elif isinstance(item_id, str):
            pending_ids.append(item_id)

    summary["total"] = len(items)
    summary["passing"] = passing
    summary["pending_ids"] = pending_ids

    if require_all_passing and pending_ids:
        errors.append(
            "not all acceptance items are passing: " + ", ".join(pending_ids)
        )

    return errors, summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate QuantA's minimal execution harness artifacts."
    )
    parser.add_argument(
        "--require-all-passing",
        action="store_true",
        help="Fail if any acceptance item still has passes=false.",
    )
    parser.add_argument(
        "--print-summary",
        action="store_true",
        help="Print a short summary of the acceptance state.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    errors: list[str] = []
    errors.extend(check_required_paths())

    if errors:
        print("Execution harness check failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    errors.extend(check_plan_structure())
    errors.extend(check_progress_structure())
    errors.extend(check_doc_expectations())

    acceptance, acceptance_errors = load_acceptance()
    errors.extend(acceptance_errors)
    summary: dict[str, object] = {"total": 0, "passing": 0, "pending_ids": []}

    if acceptance is not None:
        item_errors, summary = check_acceptance_items(
            acceptance=acceptance,
            require_all_passing=args.require_all_passing,
        )
        errors.extend(item_errors)

    if errors:
        print("Execution harness check failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Execution harness check passed.")
    if args.print_summary:
        pending_ids = summary["pending_ids"]
        pending_text = ", ".join(pending_ids) if pending_ids else "none"
        print(
            "Acceptance summary: "
            f"{summary['passing']}/{summary['total']} passing; pending: {pending_text}"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
