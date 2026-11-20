# Session: Rollback drill, near-kickoff enablement and status sync

## TL;DR

- **Worked On:** `docs/status.md` sync for the Monday release, the first near-kickoff capture, the Production rollback drill, and the `Read(*)` permission warning.
- **Outcome:** Drill passed in both directions. Near-kickoff capture is enabled and the first capture is stored. Monday release recorded.
- **Plan Contract:** [`docs/plans/2026-11-12/01-near-kickoff-line-capture.md`](../../docs/plans/2026-11-12/01-near-kickoff-line-capture.md)
- **Approval / Status:** Owner ran every Production and repository-variable command. Contract stays In Progress.
- **Blockers:** None for the drill. None. Holdout Phase 1 (Tasks 1 and 3) is merged to local `dev`; Task 2 and Task 4 stay deferred.
- **Next:** Push on the owner's go-ahead. Task 4 (export) runs after the 2026-12-13 final close.

**tags:** ["ops", "rollback", "near-kickoff"]

## Context and Decisions

- Production and Preview served `production-season-2026-06917363a8ab1b8b79bcb525` (run `43913658434`, `w12_v2`, commit `5fb66530`).
- Everything touching the controller, season engine, Neon schema or web query layer stays deferred until after 2026-12-13.

## Work Completed

- `~/.claude/settings.json` (a symlink into `~/.ai-agent-rules/cache/claude/`): `Read(*)` changed to `Read`; a later sync may restore it.
- Status sync committed as `ed8c5adf`.
- Near-kickoff: `CFB_NEAR_KICKOFF_CAPTURE_ENABLED=true`; workflow run `44336095011` stored capture `5637d39fda834559addd10f400072db2` (566 quotes, 63 events, ingestion run `near-kickoff-2026-w12-20261118-44336095011-1`, 2026-11-18T15:29Z). Rerunning `near_kickoff_slot.py` reported `skip` ("slot already captured"). Three unmatched board events skipped. Commit `f9be44a4`.
- Rollback drill, no weekly run active:
  1. Rollback to `5d50a63e…`: readback SHA-256 `a4f1b3fa2b7398bd7cf7c63eb27e4fa69c89a1421a97ef69ad4a4ea53d01feda`; `/api/health` showed Week 11, 67/67, data as of 2026-11-08T18:03:33Z.
  2. Roll-forward to `06917363…` (`rollback-drill-2026-11-18-restore`): readback SHA-256 `f213c19e046877c56b53a55357ff37af1f2d53db80b7e424079b484e4de684f0`; `/api/health` showed Week 12, 66/66, data as of 2026-11-16T17:07:02Z.
  3. Two first roll-forward attempts failed with the `make` usage message because the pasted command was split across lines; nothing ran. A wrapper script fixed it.
- Expected side effect: the Games page "Data published" line reads `activated_at`, so it now shows the 2026-11-18 restore time.

- Holdout replay Phase 1, see [`03-holdout-replay-readiness-impl.md`](./03-holdout-replay-readiness-impl.md): `verify_2026_manifest_pins.py` passed all 12 manifests against Preview R2 (rerun by the orchestrator after merge); `export_2026_holdout.py` and `tests/test_export_2026_holdout.py` (7 tests) added. Commits `0381a65b` (feat) and `7d837074` (docs), fast-forwarded onto `dev`; the worktree and branch are removed.
- The worktree's `make check` stopped at web lint (`eslint` missing, no `web/node_modules`); the Python steps, `mkdocs build --strict` and `git diff --check` passed.

## Files Modified

- `docs/status.md`, `docs/plans/2026-11-12/01-near-kickoff-line-capture.md`, `docs/planning/offseason-2027-backlog.md`, this log.

## Validation

- [x] `/api/health` checked after each step (values above).
- [ ] Pre-drill readback SHA-256 baseline was not recorded, so the post-restore hash (`f213c19e…`) is not compared against it. The 2026-10-25 note records matching Preview and Production hashes per release, but no baseline for this release was found in the repository or run log.
- [x] `git diff --check`; full `make check` green on `dev` (web steps included)

## Amendments and Blockers

- None.

## Handoff Notes

- **Resume at:** Owner decision on pushing `dev`; holdout contract `docs/plans/2026-11-12/05-holdout-replay-readiness.md` (Tasks 2 and 4 pending).
- **Watch out for:** Do not push during Sunday 17:00–19:30 UTC; nothing is pushed yet.
