# Session: V5 replay and Preview rehearsal planning

## TL;DR

- **Worked On:** The next dependency under the V5 product transformation.
- **Outcome:** Approved, bounded implementation contract documented at `docs/plans/2026-09-24/01-v5-replay-preview-rehearsal.md`.
- **Plan Contract:** `docs/plans/2026-09-24/01-v5-replay-preview-rehearsal.md` (Approved; implementation not started).
- **Approval / Status:** User chose the full Preview rehearsal and replay-first scope, then asked to document the plan. User subsequently authorized committing this session's reviewed changes.
- **Blockers:** Replay apply needs a clean committed SHA. Preview site currently filters selected V4 fallback runs; historical selection is absent from `/api/health`.
- **Next:** Implement Task 1, commit a clean code checkpoint, then apply the replay and continue through Preview scoring, serving, and rollback.

## Context and Decisions

- Preview has migration 0013 and 452 V5 rating snapshots, but no V5 selection or durable replay manifest.
- Week 0 is the bounded rehearsal slate. Preview V4 run `2026w0-a0edb9e72cb1` is frozen, has eight stored predictions, and belongs to the correct week. `current_week` points to a 2025 replay, so historical Week 0 selection requires its own health evidence.
- The first checkpoint commits rollback-capable code. The replay apply uses that clean SHA and saves reviewed preflight evidence under `/tmp`. A second checkpoint commits the exact replay manifest pin before publication.
- Current-slate Contract 07/08 refresh, live forecast, prospective freeze, production activation, scheduler, and V4 retirement remain outside this milestone.

## Work Completed

- Read the replay builder, serving adapter, selection policy, scoring path, site queries, health route, and active contracts.
- Queried Preview read-only for run eligibility and selection state. No Preview mutation occurred during planning.
- Wrote the implementation contract and linked it from the plans index.

## Files Modified

- `docs/plans/2026-09-24/01-v5-replay-preview-rehearsal.md` — approved execution contract.
- `docs/plans/index.md` — current contract link.
- `session_logs/2026-09-24/02-v5-replay-preview-planning.md` — planning record.

## Validation

- [x] `git diff --check` after documentation persistence.
- [x] Strict MkDocs build after documentation persistence.

## Amendments and Blockers

None. The separate V5 product transformation implementation remains In Progress; this contract is its replay-first Preview milestone.

## Handoff Notes

- **Resume at:** Repair selected V4 rendering and selected-week health, then use the two clean-code checkpoints in the contract.
- **Watch out for:** Never treat retrospective replay as prospective evidence or update production while rehearsing Preview.

**Copy-ready implementation prompt:**

```text
Use the repository-local implement-plan skill and implement the approved contract at:

docs/plans/2026-09-24/01-v5-replay-preview-rehearsal.md

Treat it as authoritative. Preserve its architectural decisions, run its validation,
and stop for any material conflict. This request explicitly authorizes implementation.
```

**Suggested plan commit message:** `Document V5 replay and Preview rehearsal contract`

**tags:** ["v5", "planning", "replay", "preview"]
