# Session: Week 6 display-only run planning on served successor lineage

## TL;DR
- **Worked On:** Investigated successor pipeline scripts, evidence class semantics, and data dependencies for publishing a display-only Week 6 slate with evidence class `pending`. Created approved Sol-to-Terra implementation contract `docs/plans/2026-10-07/03-week6-display-run.md`.
- **Outcome:** Contract completed and marked `Approved`. Evidence class resolved to `pending` (truthful to the forecast timing, prevents illegal retrospective claims, grades cleanly unconstrained, and will never be frozen). Added Task 1 for building a deterministic Week 6 source lock generator and parameterizing Week-5-specific pipeline scripts with byte-for-byte p2 parity verification.
- **Plan Contract:** `docs/plans/2026-10-07/03-week6-display-run.md`
- **Approval / Status:** User authorized planning and confirmed `pending` evidence class and the lock-builder task.
- **Blockers:** Implementation requires executing Task 1 (lock builder & script parameterization) before running Preview Silver refresh and downstream tasks.
- **Next:** Launch Terra implementation task using `.agent/skills/implement-plan/` targeting `docs/plans/2026-10-07/03-week6-display-run.md`.

## Context and Decisions
- Southern Miss @ Troy kicked off Oct 7 00:00Z. The remaining 57 FBS games have not yet kicked off (earliest at 23:00Z). CFBD currently provides full spread and total lines for all 58 games.
- The user confirmed that the objective is to display Week 6 predictions and post-Week-5 ratings on the public site based strictly on through-Week-5 data (zero data leakage from Week 6), without claiming a pre-kickoff prospective record.
- **Evidence Class Decision:** `pending`.
  - An unplayed slate cannot be produced by the `replay` path (which requires completed games and is reserved for Stage 7B historical reconstruction).
  - The `pending` evidence class reflects the actual operational timing of the forecast.
  - Crucial governance guard: `freeze_week.py` and `close_week.py` must NEVER be run on this slate, because the 1-hour pre-kickoff boundary has passed for Troy and running freeze would mark the run `missed` (which breaks public selection).
  - Unconstrained grading post-finals will proceed via `backfill_v5_unconstrained_grades.py --week 6 --grades-only`.

## Work Completed
1. Inspected all scripts in the successor lineage (`build_v5_intended_update_live_serving.py`, `build_v5_intended_update_forecasts.py`, `build_v5_intended_update_2026.py`, `verify_v5_intended_update_live_serving.py`, `package_v5_intended_update_live_run.py`, `authorize_v5_intended_update_preview.py`) and identified all hardcoded Week 5 paths, week ranges, and checks.
2. Verified that `v5-repair-2026-source-lock.json` was a static artifact created in a prior session without an existing builder script. Added a task to create `scripts/pipeline/build_v5_intended_update_source_lock.py`.
3. Created decision-complete implementation contract `docs/plans/2026-10-07/03-week6-display-run.md` covering all 8 phases from script generalization and Preview Silver refresh through ratings extension, forecasting, Preview rehearsal, and user-executed Production release.

## Validation
- `git diff --check` passes cleanly.
- `uv run mkdocs build --quiet` passes.

## Handoff Notes
- **Resume at:** Terra implementation of Task 1 in `docs/plans/2026-10-07/03-week6-display-run.md`.
- **First actions:**
  1. Write `scripts/pipeline/build_v5_intended_update_source_lock.py`.
  2. Parameterize successor scripts for `--week`.
  3. Add parity regression test asserting exact match on Week 5 p2 outputs.

## Update (later the same session): contract superseded, Week 6 held
- Reconciling the contract with the repository (implement-plan step 1) found it unbuildable as written: three kickoff guards in the successor chain (serving builder apply, packager apply, independent verifier) refuse a post-kickoff `pending` run, plus a missing foundation-refresh stage and no Production rollback path. Two mechanical amendments were recorded (commands and the 07/08 refresh), the web banner was removed at the user's direction, and a third amendment (an explicit `--display-only` mode) was proposed.
- **User decision: hold Week 6 until the Week 7 cutover.** The contract was closed as **Superseded** with its findings retained; no implementation, ingest or write was started. The earlier "Approved / Next: launch Terra" lines above are historical.
- `docs/status.md` Week 6 row updated to the final decision. Nothing external changed.
- **Resume at:** nothing pending for Week 6 now. After Week 6 finals plus 24 hours (about Oct 12-13), follow the Stage 7B Cutover Execution Plan; use this contract's Amendments 1-2 as input.
