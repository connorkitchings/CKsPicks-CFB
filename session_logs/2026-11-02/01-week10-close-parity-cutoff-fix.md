# Session: Week 10 close-week parity failure and one-off cutoff correction flag

## TL;DR

- **Worked On:** Diagnosed the failed scheduled close-week run of 2026-11-01 (run 41350368740) and added a one-off parity flag so the Week 10 close can be rerun.
- **Outcome:** `check_release_parity.py` and `weekly_automation.py` take `--accept-cutoff-correction WEEK` (close-week only); the workflow exposes it as the `accept_cutoff_correction` dispatch input. Nothing was released.
- **Plan Contract:** N/A (fast path, owner-chosen 2026-11-02)
- **Approval / Status:** Owner chose fast path, a one-off flag, and work on `dev`.
- **Blockers:** Full parity report not inspected (artifact host blocked in this session); only 40 of about 128 failure lines were visible, all `cutoff_utc` on Week 8 pregame snapshots.
- **Next:** Owner checks the run's parity report for any non-`cutoff_utc` difference, then dispatches `close-week` on `dev` with `accept_cutoff_correction=8` (optionally first with `skip_production=true`) before the first Week 10 kickoff.

**tags:** ["automation", "github-actions", "parity", "season", "incident"]

## Context and Decisions

- The run passed detection, capture, the Week 10 build, score exceptions, the commit and push of `revision_manifest_w10_v1.json` to `dev` (`c3ee43e`) and prepare, then failed parity with `v5_rating_snapshots <run>:pregame:<Team>:week-8: changed columns ['cutoff_utc']`.
- Cause: the active Preview release was built from the Week 9 manifests (Week 8 cutoff 18:00:00Z, stale); `w10_v1` restores the certified 14:39:00Z, as planned in `docs/status.md`. Close-week parity compares completed-week pregame snapshots strictly, including `cutoff_utc`.
- The owner chose a one-off flag over a permanent rule. Its scope is narrow: only `cutoff_utc`, only pregame `v5_rating_snapshots`, only the named week, which must be before the completed week; value columns stay strict; refused in market-refresh. The controller drops it when parity falls back to market-refresh, and records it in the run summary and parity report.

## Work Completed

- Parity flag, report field `accepted_cutoff_corrections`, controller passthrough, workflow input (validated as digits, passed through env), runbook and status notes, tests.

## Files Modified

- `scripts/pipeline/check_release_parity.py`: `--accept-cutoff-correction` and `accept_cutoff_corrections` in `compare_releases`.
- `scripts/ops/weekly_automation.py`: `Controller.accept_cutoff_corrections` and the CLI flag.
- `.github/workflows/weekly-season-update.yml`: `accept_cutoff_correction` dispatch input.
- `tests/test_check_release_parity.py`, `tests/test_weekly_automation.py`: new cases.
- `docs/ops/weekly_runbook.md`, `docs/status.md`: input documented; incident noted.

## Validation

- [x] `uv run pytest tests/test_check_release_parity.py tests/test_weekly_automation.py` (57 passed)
- [x] `ruff check` and `ruff format --check` on the changed Python files
- [x] Workflow YAML parses; the input snippet tested for blank, `8` and a rejected non-numeric value
- [x] `git diff --check`

## Amendments and Blockers

- Rerun: owner-approved full close-week run 41390458854 from `dev` (`50a78c6`, `accept_cutoff_correction=8`) resumed at prepare; prepare, parity, Preview release and then Production release all passed (2026-11-02 04:48Z to 04:57Z).
- CI on `50a78c6` failed one test, `test_committed_week_9_manifest_passes_the_repo_loaders`. It came from the automation commit `c3ee43e` (pushes by `GITHUB_TOKEN` do not run CI): that commit added five score exceptions, so the hard-coded `w9_v1` manifest no longer matches the mutable exceptions file. The test now loads the newest committed manifest by week and version (`test_latest_committed_manifest_passes_the_repo_loaders`). CI's general suite passes locally (2205 passed, 5 skipped).

## Handoff Notes

- **Resume at:** Rerun of the Week 10 close from `dev`.
- **Watch out for:** Commit nothing to `dev` between the rerun's prepare and its last release. Dispatch with `--ref dev` so the new input exists; the scheduled path from `main` does not need it. Release `dev` to `main` later as usual.
