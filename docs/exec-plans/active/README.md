# Active Plans

`active/` only contains execution plans that still have current delivery work.
Completed milestones are archived under `../completed/` with their acceptance and
progress handoff files.

## Current

1. [M24 Auto History Backfill Recommendation Loop](2026-04-09-m24-auto-history-backfill-recommendation-loop.md)

## Operating Rule

Keep a plan in `active/` only while its next step is part of the current work
loop. Once its acceptance is passing and any remaining follow-up has moved into a
later plan or `../tech-debt-tracker.md`, move the plan, acceptance, and progress
files to `../completed/`.
