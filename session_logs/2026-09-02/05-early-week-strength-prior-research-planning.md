# Session: Early-Week Strength-Prior Research Planning

## TL;DR

- **Worked On:** Diagnosed the Alabama–East Carolina Game 1 prediction and prepared the approved dual-track early-week research contract.
- **Outcome:** Confirmed a genuine V4 modeling limitation, not a UI/sign bug. The approved contract adds audited offseason context to independent rating and direct early-game research tracks while preserving production V4.
- **Plan Contract:** `docs/plans/2026-09-02/early-week-strength-prior-research.md`
- **Approval / Status:** User approved the plan and said “Proceed” on 2026-09-02; contract status is `Approved`.
- **Blockers:** R2 execution remains blocked on an R1 certificate with `tournaments_permitted: true`. Historic offseason context is presently reconstructed only.
- **Next:** Run the approved contract in a fresh Terra task.

## Context and Decisions

- Production run `2026w1-b2c739321e5d` stores Alabama `+0.165649` against East Carolina with a `-28.25` home line. The run is `published`, routes to `game_1`, and used the immutable V4 bundle.
- Reconstructing the exact R2 feature row and saved model reproduced the `+0.165649` prediction. At zero completed games all current-evidence weights are zero, leaving prior season rate statistics and basic game context only.
- The bundle includes no admitted roster/talent/recruiting/coaching or conference-strength input. Alabama and ECU's retained 2025 performance-rate features are similar enough to yield an implausible near-pick'em forecast.
- The selected Game 1 spread CatBoost improved 2022–2024 OOF MAE by 1.43 but had worse locked-2025 MAE than its baseline (15.16 vs. 14.55); the existing anti-regression guard still retained it.
- User chose a research-successor scope, structured offseason inputs, and both rating-prior and direct early-game experiments. Markets remain evaluation only and V4 remains untouched.

## Work Completed

- Completed start-session and plan-session investigation: repository context, recent logs, clean worktree, R2 configuration, production prediction row, R2 catalog metadata, immutable feature snapshot, V4 manifest, and locked report.
- Verified R2 storage credentials/configuration without exposing secrets.
- Created the approved implementation contract and added it to the planning index.

## Files Modified

- `docs/plans/2026-09-02/early-week-strength-prior-research.md` — approved Sol-to-Terra implementation contract.
- `docs/plans/index.md` — active-contract entry.
- `session_logs/2026-09-02/05-early-week-strength-prior-research-planning.md` — this planning handoff.

## Validation

- [ ] `git diff --check`
- [ ] `uv run mkdocs build --quiet`

## Amendments and Blockers

- None. The existing R1 certificate dependency is explicitly retained.

## Handoff Notes

- **Resume at:** Implement the approved contract in a fresh Terra task.
- **Watch out for:** Existing historic preseason inputs are reconstructed; neither direct nor rating research may present them as strict or activate them. Never alter V4 or the active production run.

**tags:** ["modeling", "early-season", "ratings", "planning"]

