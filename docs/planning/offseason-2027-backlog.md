# Offseason 2027 backlog

Prepared 2026-11-11 as the single list of what to consider in the offseason. Owner decision 2026-11-14: model research starts after the 2026-12-13 final close (previously 2027-01-01), and the order of work is set in the [direction document](direction-2026-11-14.md). It is a backlog, not a commitment: nothing here starts before the final close except the start-now work below, and each item that changes model behavior, data lineage, schemas or Production still needs its own contract (`docs/plans/`) and owner approval. Live release and week state stays in [Current Status](../status.md).

## Ground rules

- The 2026 V5 model is frozen for the 2026 continuous record. The 2026 season is the clean holdout for the next model; do not select features, priors or thresholds from 2026 results.
- Diagnostics come before ideas. Start from prediction error, not from betting-result slices. Choosing features or priors from ATS win-rate buckets mixes market evaluation into model selection and breaks the guardrails in [betting policy](../modeling/betting_policy.md) and [evaluation](../modeling/evaluation.md).
- A research contract states its gates before any run: the data years used for development (2021 to 2025), the comparison model (the frozen V5), the metrics and the thresholds that decide adoption.

## Start-now work (2026-11-12)

Work that cannot wait for January, each under a Draft contract in `docs/plans/2026-11-12/`:

- [Near-kickoff line capture](../plans/2026-11-12/01-near-kickoff-line-capture.md): closing lines cannot be reconstructed later, so capture them in Weeks 12 to 15 (analysis only, outside the record). Time-sensitive.
- [Pre-registered research protocol](../plans/2026-11-12/02-offseason-research-protocol.md): approved 2026-11-12, written while 2026 is unseen.
- [Score-attribution investigation](../plans/2026-11-12/04-score-attribution-investigation.md): examine each quarantined game and specify a direct repair of the running-score defect (owner direction 2026-11-12: repair, do not keep quarantining). Report: [score-attribution investigation](../modeling/score_attribution_investigation_2026.md) (per-game data and a specified repair rule; adopting it is a separate next-model contract).
  - Status 2026-11-12: investigation implemented and documented ([report](../modeling/score_attribution_investigation_2026.md)). Owner decision: do not fix the running-score problem now; revisit on 2026-11-13. Open items for then: adopt rule R4 plus the quarter-line check as the next-model rule (and re-derive the 2025 terminal table and priors), a play-text points ledger for the four unresolved games, whether to raise the feed defect with CFBD, and why game `401858279` is quarantined without a score-exception entry.
- [Prediction-error diagnostics](../plans/2026-11-12/03-prediction-error-diagnostics.md): section A below, as a contract.

Also scheduled:

- **2026 holdout replay readiness** ([contract](../plans/2026-11-12/05-holdout-replay-readiness.md)). Verified 2026-11-18 (Task 1, read-only): all 12 revision manifests (`w7_v1` to `w12_v2`) pass pin validation and a full input load from their git-restored exceptions version (`scripts/research/verify_2026_manifest_pins.py`); the checksum mismatch only occurs against the in-place edited working file. The read-only export tool exists (`scripts/research/export_2026_holdout.py`); running it is Task 4, after the 2026-12-13 final close. Version the score-exceptions file per manifest from 2027, and after the 2026-12-13 final close export one frozen holdout table (pre-kickoff inputs per week, outcomes, captured lines) with hashes, so a candidate can be scored on 2026 once at the original information time.
- **Research bucket.** Provision the private research bucket and `CFB_R2_LAB_*` credentials (owner action in Cloudflare) so the ratings-lab CLI runs without the local-output exception, then re-baseline the closed V6 tournament (`RETAINED_AS_BENCHMARK`) as the benchmark that candidates are compared against alongside V5.

## A. Prediction-error diagnostics (read-only, first)

Output: a report under `docs/modeling/`, no model change. Contract: [2026-11-12/03](../plans/2026-11-12/03-prediction-error-diagnostics.md). Report (development view only): [prediction-error diagnostics, 2021 to 2025](../modeling/prediction_error_diagnostics_2021_2025.md). It includes site class, conference and a totals over-prediction diagnostic; only a true partial-quarantine re-estimation remains open (it needs the V5 control replay).

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
- Venue as a model input: the forecast hard-codes every game as home (`home_host=1.0`, `venue_unknown=True`), while the diagnostics show neutral-site margin bias of -4.32 points; the venue data is already stored (`fbs_involved_games`, `game_venues`). Not market-derived, so allowed.
- Measurement refinements: the garbage-time rule for the Net success rate (the analysis in `session_logs/2026-11-09/06-nsr-keep-garbage-time-impl.md` points to a flat margin cut of about 24 points; the owner kept the current rule for 2026, so this is a candidate for the next model version, which needs a stored column and a release), turnover margin, and the historical EPA replacement.
- Offense-evidence input: whether adjusted yards per play (or EPA per play) predicts future scoring better than adjusted points per possession, per the [adjusted YPP predictive diagnostic](../plans/2026-11-19/adjusted-ypp-predictive-diagnostic.md) (Draft); the display side is [specified here](../plans/2026-11-19/yards-per-play-display.md).
- Rating-system structure questions raised by the audit, once its original-artifact verification can be completed.
- Background reading, no commitment: the [V6 methodology survey](../research/v6-methodology-survey-2026-11.md) (rating systems, totals structure, evaluation decisions, input feasibility).

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

- ~~Production rollback drill~~ Done 2026-11-18 (rolled back to the Week 11 release and forward again; evidence in `session_logs/2026-11-18/02-rollback-drill-and-near-kickoff-enable.md`).
- **Neon release retention and provenance slimming** ([2026-11-18 repository review](../plans/2026-11-18/repo-review-and-offseason-engineering.md)): build a supported `scripts/ops/prune_season_releases.py` (`make season-prune`) codifying the two-phase trigger-safe delete (`SET CONSTRAINTS ALL IMMEDIATE`, scoped trigger disable/delete/enable with 25/25 trigger assertions, mandatory JSON export receipt, Production rollback-target protection) and smallest-first headroom-checked `VACUUM (FULL, ANALYZE)` cascade from `session_logs/2026-11-15/04-preview-release-prune.md`. In the next offseason projection set, drop or empty per-row `source_versions` JSONB repetition on `team_season_stats` (~420 bytes repeated across ~36,432 rows per release, ~15.3 MB raw JSONB per release), `team_game_measurements` and `team_possession_stats` (~35–45% storage reduction per release).
- **Season `prepare` runtime optimization** ([2026-11-18 repository review](../plans/2026-11-18/repo-review-and-offseason-engineering.md)): pre-index `teams_by_game` and `usable_by_game` in `src/cks_picks_cfb/forecast/offsets.py` to remove ~460,000 inner-loop pandas DataFrame boolean scans per `prepare` run, and key `measurement-cache` in `src/cks_picks_cfb/season/inputs.py` and `scripts/pipeline/refresh_score_exceptions.py` on the five pinned input dataset hashes plus a SHA-256 of the measurement source files (instead of git `HEAD` `code_sha`) so the manifest commit in `weekly_automation.py` does not force `build_measurements` to execute twice. Gate on 100% byte-identical `serving-projections.json` SHA-256 against a certified 2026 manifest.
- **Per-manifest score-reconciliation exceptions and Stage 1a safeguards** ([Stage 1a](../plans/2026-10-28/01-data-architecture-operational-safeguards.md), [holdout replay readiness](../plans/2026-11-12/05-holdout-replay-readiness.md)): deferred until after the 2026-12-13 final regular-season close so `weekly_automation.py` and `refresh_score_exceptions.py` stay untouched during Weeks 13–15.
- Review how many Sunday and Monday slots the scheduler missed in 2026 and whether the backup slots are enough.
- Automation commits made with `GITHUB_TOKEN` do not trigger CI; add an in-workflow post-commit verification step (`contracts/validation.py` + focused season/manifest pytest checks) in `weekly-season-update.yml`, and add refusal guards to legacy `Makefile` targets (`team-stats`, `matchup-data`, `prepare-week`, `promote-silver`).
- Unused market-quotes catalog version and other small cleanups listed under Open items in the status page.

## G. Site and product

- Small fixes from the final site review: all closed in PR #39 (`a7d03f2d`, site v2.0.0), including the 404 theme application fix (`66ce7294`), short team names in the forecast card, and the Bye row on team schedules.
- Web read performance ([contract](../plans/2026-10-29/01-web-read-performance.md), expanded 2026-11-18 with PostgreSQL double-referenced CTE materialization fixes in `tie-sql.ts`, `getCurrentRatings` and `prediction_grades` joins, plus lazy `/stats` chart loading).
- [JP+ site review adoptions](../plans/2026-11-17/jpplus-review-adoptions.md): approved 2026-11-17 and deferred until after the offseason model and methods work.
- Content and explainability. Owner decision 2026-11-11: the site is primarily an analytics site, and market comparison and bet finding are a central spoke of that analytics wheel, so betting views are part of the analytics product rather than a separate tool. Weigh model research against explainability and market-comparison content on that basis.
