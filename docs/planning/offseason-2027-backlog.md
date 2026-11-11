# Offseason 2027 backlog

Prepared 2026-11-11 as the single list of what to consider from 2027-01-01. It is a backlog, not a commitment: nothing here starts before the offseason, and each item that changes model behavior, data lineage, schemas or Production still needs its own contract (`docs/plans/`) and owner approval. Live release and week state stays in [Current Status](../status.md).

## Ground rules

- The 2026 V5 model is frozen for the 2026 continuous record. The 2026 season is the clean holdout for the next model; do not select features, priors or thresholds from 2026 results.
- Diagnostics come before ideas. Start from prediction error, not from betting-result slices. Choosing features or priors from ATS win-rate buckets mixes market evaluation into model selection and breaks the guardrails in [betting policy](../modeling/betting_policy.md) and [evaluation](../modeling/evaluation.md).
- A research contract states its gates before any run: the data years used for development (2021 to 2025), the comparison model (the frozen V5), the metrics and the thresholds that decide adoption.

## A. Prediction-error diagnostics (read-only, first)

Output: a report under `docs/modeling/`, no model change.

- Margin and total residuals for 2021 to 2025 as the development view and 2026 as a separate monitoring view.
- Mean absolute error and bias by week of season, rating-gap size, totals regime (low, mid, high), conference group and home or neutral site.
- Interval calibration: do stated variances cover outcomes at the stated rate, by the same splits.
- Early-season behavior: how fast preseason priors are replaced by in-season evidence, and the error cost of Weeks 0 to 4.
- Totals model separately from the spread model.
- Sensitivity of narrow matchups to the partial-quarantine policy (finding of the [V5 ratings audit](../modeling/v5_offense_defense_ratings_audit_2026.md)).

## B. Model research candidates (each needs a pre-registered contract)

Chosen only after section A shows where the error is; the likely areas are:

- Preseason priors and the early-season blend.
- The totals model.
- Measurement refinements: the garbage-time rule for the Net success rate (the analysis in `session_logs/2026-11-09/06-nsr-keep-garbage-time-impl.md` points to a flat margin cut of about 24 points; the owner kept the current rule for 2026, so this is a candidate for the next model version, which needs a stored column and a release), turnover margin, and the historical EPA replacement.
- Rating-system structure questions raised by the audit, once its original-artifact verification can be completed.

## C. 2027 rollover readiness

- Preseason priors and the new 2027 manifests and request inventory.
- A Week 0 rehearsal on Preview, with the weekly automation disabled for Production until it passes (as in 2026).
- Re-check `FINAL_REGULAR_WEEK` and the season calendar for 2027 (and the end-of-season state from the [2026 contract](../plans/2026-11-11/regular-season-end-state.md)).
- Restore or re-capture the original prepared artifacts the ratings audit could not verify, and keep them retained.
- Confirm provider credentials, quotas and the Odds API budget for the season.

## D. Postseason

Full postseason support, if wanted: the provider files bowls and the College Football Playoff under a separate season type with restarting week numbers and staged matchups, so it needs multi-stage cutoffs, week mapping and week selectors on the site. Decide first whether the official record should include postseason games at all.

## E. Deferred data backlog

From [Current Status](../status.md#deferred-backlog): historical EPA replacement, the six quality follow-ups, scoring and descendant recertification, the 2025 matchup backfill, the turnover-margin factor for the matchup card, and non-monotonic play-by-play score repair ([known issues](../data/known_issues.md)).

Recovery backup from the 2026-10-28 worktree cleanup (owner decision 2026-11-11: keep it all for now). It lives outside the repository at `.worktrees/cleanup-backups/2026-10-28/data-architecture-roadmap/` in the owner's checkout:

- `branches.bundle` (restore a branch with `git fetch <bundle> refs/heads/<branch>:refs/heads/<branch>`; tips are listed in its `manifest.json`). Two preserved branches are not on `dev`: `worktree-connorkitchings-data-architecture-blueprint-review` and `codex/graph-correctness-fixes` (its helper `optionalChartWeeks` is absent from `dev`; the Graphs repairs shipped through #14 and #15, so it is probably superseded, but that was not verified).
- The blueprint review (`docs/planning/data_architecture_blueprint_review.md` on that branch, dated 2026-10-24, non-authoritative) lists blueprint claims the code does not support, missing storage and performance design, existing assets the blueprint ignores, and unsequenced data defects. Restore it as a non-authoritative document with the first offseason data contract, after reading it against the 2026-10-29 blueprint revision.
- `incremental-close-week-private.tar.gz` holds old Preview rollover artifacts and the 2026-10-02/03 investigation backups (6 MB, 74 files). Its `.env` entry is empty and a text scan found no credentials, though the scan cannot see inside parquet files. Keep it until the EPA replacement and 2025 matchup backfill are scoped; do not commit or publish it.

## F. Operations and resilience

- Production rollback drill (never run; the readback fix is merged). Run it mid-week, outside a weekly run, and record the evidence.
- Review how many Sunday and Monday slots the scheduler missed in 2026 and whether the backup slots are enough.
- Automation commits made with `GITHUB_TOKEN` do not trigger CI; decide whether to add a post-commit check.
- Unused market-quotes catalog version and other small cleanups listed under Open items in the status page.

## G. Site and product

- Small fixes from the final site review: console warning on 404 pages, long team names wrapping in the matchup forecast card, a "Bye" row.
- Web read performance ([contract](../plans/2026-10-29/01-web-read-performance.md)).
- Content and explainability. Owner decision 2026-11-11: the site is primarily an analytics site, and market comparison and bet finding are a central spoke of that analytics wheel, so betting views are part of the analytics product rather than a separate tool. Weigh model research against explainability and market-comparison content on that basis.
