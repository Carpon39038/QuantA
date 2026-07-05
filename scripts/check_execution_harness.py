#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
ACTIVE_PLAN_DIR = ROOT / "docs/exec-plans/active"
COMPLETED_PLAN_DIR = ROOT / "docs/exec-plans/completed"

REQUIRED_PROGRESS_HEADINGS = [
    ("## Current State", "## Current Status"),
    ("## Next Step", "## Next"),
    "## Completed",
    "## Verification",
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


def acceptance_paths() -> list[Path]:
    paths: list[Path] = []
    for plan_dir in [ACTIVE_PLAN_DIR, COMPLETED_PLAN_DIR]:
        paths.extend(sorted(plan_dir.glob("*.acceptance.json")))
    return paths


def artifact_stem(path: Path) -> str:
    return path.name[: -len(".acceptance.json")]


def plan_path_for_acceptance(path: Path) -> Path:
    return path.with_name(f"{artifact_stem(path)}.md")


def progress_path_for_acceptance(path: Path) -> Path:
    return path.with_name(f"{artifact_stem(path)}.progress.md")


def check_required_paths(paths: list[Path]) -> list[str]:
    errors: list[str] = []
    for path in [ACTIVE_PLAN_DIR, COMPLETED_PLAN_DIR]:
        if not path.exists():
            errors.append(f"missing execution plan directory: {path.relative_to(ROOT)}")
    if not paths:
        errors.append("missing execution harness acceptance artifacts")
    for path in paths:
        for related_path in [
            plan_path_for_acceptance(path),
            path,
            progress_path_for_acceptance(path),
        ]:
            if not related_path.exists():
                errors.append(
                    "missing execution harness artifact: "
                    f"{related_path.relative_to(ROOT)}"
                )
    return errors


def check_active_plan_structure(plan_path: Path) -> list[str]:
    errors: list[str] = []
    content = plan_path.read_text(encoding="utf-8")

    required_sections = [
        "## Goal",
        "## Scope",
        "## Non-Goals",
        "## Acceptance",
        "## Done When",
        "## Verify By",
        "## Tasks",
        "## Status",
    ]

    for section in required_sections:
        if section not in content:
            errors.append(
                f"active execution plan {plan_path.relative_to(ROOT)} "
                f"is missing section: {section}"
            )

    return errors


def check_active_progress_structure(progress_path: Path) -> list[str]:
    errors: list[str] = []
    content = progress_path.read_text(encoding="utf-8")

    for expectation in REQUIRED_PROGRESS_HEADINGS:
        if isinstance(expectation, tuple):
            if not any(heading in content for heading in expectation):
                expected = " or ".join(expectation)
                errors.append(
                    f"active progress handoff {progress_path.relative_to(ROOT)} "
                    f"is missing heading: {expected}"
                )
            continue

        if expectation not in content:
            errors.append(
                f"active progress handoff {progress_path.relative_to(ROOT)} "
                f"is missing heading: {expectation}"
            )

    return errors


def check_doc_expectations() -> list[str]:
    errors: list[str] = []
    for relative_path, expected_mentions in DOC_EXPECTATIONS.items():
        content = (ROOT / relative_path).read_text(encoding="utf-8")
        for mention in expected_mentions:
            if mention not in content:
                errors.append(f"{relative_path} is missing expected mention: {mention}")
    return errors


def load_acceptance(path: Path) -> tuple[dict[str, object] | None, list[str]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, [f"{path.relative_to(ROOT)} is not valid JSON: {exc}"]

    if not isinstance(data, dict):
        return None, [f"{path.relative_to(ROOT)} must be a JSON object"]

    return data, []


def check_acceptance_items(
    path: Path,
    acceptance: dict[str, object],
    require_all_passing: bool,
) -> tuple[list[str], dict[str, object]]:
    errors: list[str] = []
    summary: dict[str, object] = {
        "total": 0,
        "passing": 0,
        "pending_ids": [],
    }

    relative_path = path.relative_to(ROOT)
    required_top_level_keys = ["plan_id", "title", "items"]
    for key in required_top_level_keys:
        if key not in acceptance:
            errors.append(f"{relative_path} is missing key: {key}")

    items = acceptance.get("items")
    if not isinstance(items, list) or not items:
        errors.append(f"{relative_path} must contain a non-empty items list")
        return errors, summary

    seen_ids: set[str] = set()
    pending_ids: list[str] = []
    passing = 0

    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            errors.append(f"{relative_path} item #{index} must be an object")
            continue

        required_item_keys = [
            "id",
            "title",
            "description",
            "passes",
        ]
        for key in required_item_keys:
            if key not in item:
                errors.append(f"{relative_path} item #{index} is missing key: {key}")

        item_id = item.get("id")
        if not isinstance(item_id, str) or not item_id:
            errors.append(f"{relative_path} item #{index} has invalid id")
        elif item_id in seen_ids:
            errors.append(f"{relative_path} has duplicate acceptance item id: {item_id}")
        else:
            seen_ids.add(item_id)

        priority = item.get("priority")
        if priority is not None and (
            not isinstance(priority, int) or priority < 1 or priority > 3
        ):
            errors.append(
                f"{relative_path} item {item_id or f'#{index}'} "
                f"has invalid priority: {priority}"
            )

        artifacts = item.get("artifacts")
        if artifacts is not None:
            if not isinstance(artifacts, list) or not artifacts:
                errors.append(
                    f"{relative_path} item {item_id or f'#{index}'} "
                    "must list artifacts when artifacts is present"
                )
                continue
            for artifact in artifacts:
                if not isinstance(artifact, str) or not artifact:
                    errors.append(
                        f"{relative_path} item {item_id or f'#{index}'} "
                        "has invalid artifact path"
                    )
                    continue
                artifact_path = ROOT / artifact
                if not artifact_path.exists():
                    errors.append(
                        f"{relative_path} item {item_id or f'#{index}'} "
                        f"references missing artifact: {artifact}"
                    )

        verify_steps = item.get("verify_steps", item.get("verification"))
        if not isinstance(verify_steps, list) or not verify_steps:
            errors.append(
                f"{relative_path} item {item_id or f'#{index}'} "
                "must define verify_steps or verification"
            )
        else:
            for step in verify_steps:
                if not isinstance(step, str) or not step:
                    errors.append(
                        f"{relative_path} item {item_id or f'#{index}'} "
                        "has invalid verify step"
                    )

        passes = item.get("passes")
        if not isinstance(passes, bool):
            errors.append(
                f"{relative_path} item {item_id or f'#{index}'} "
                "must use a boolean passes flag"
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
            f"{relative_path} has non-passing acceptance items: "
            + ", ".join(pending_ids)
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

    paths = acceptance_paths()
    errors: list[str] = []
    errors.extend(check_required_paths(paths))

    if errors:
        print("Execution harness check failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    errors.extend(check_doc_expectations())

    total = 0
    passing = 0
    pending_by_plan: dict[str, list[str]] = {}

    for path in paths:
        if path.parent == ACTIVE_PLAN_DIR:
            errors.extend(check_active_plan_structure(plan_path_for_acceptance(path)))
            errors.extend(
                check_active_progress_structure(progress_path_for_acceptance(path))
            )

        acceptance, acceptance_errors = load_acceptance(path)
        errors.extend(acceptance_errors)

        if acceptance is None:
            continue

        item_errors, summary = check_acceptance_items(
            path=path,
            acceptance=acceptance,
            require_all_passing=args.require_all_passing,
        )
        errors.extend(item_errors)

        total += int(summary["total"])
        passing += int(summary["passing"])
        pending_ids = summary["pending_ids"]
        if isinstance(pending_ids, list) and pending_ids:
            pending_by_plan[artifact_stem(path)] = [str(item) for item in pending_ids]

    if errors:
        print("Execution harness check failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Execution harness check passed.")
    if args.print_summary:
        if pending_by_plan:
            pending_text = "; ".join(
                f"{plan}: {', '.join(ids)}"
                for plan, ids in sorted(pending_by_plan.items())
            )
        else:
            pending_text = "none"
        print(
            "Acceptance summary: "
            f"{passing}/{total} passing across {len(paths)} plans; "
            f"pending: {pending_text}"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
