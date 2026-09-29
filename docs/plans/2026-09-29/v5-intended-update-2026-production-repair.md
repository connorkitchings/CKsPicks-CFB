# 2026 V5 intended-update production repair

- **Status:** In Progress
- **Created:** 2026-09-29
- **Planner:** Sol
- **Approval source:** User explicitly authorized implementation of this exact path in the 2026-09-29 handoff message; approved before code changes
- **Implementation log:** `session_logs/2026-09-29/02-v5-intended-update-production-implementation.md` (Task 1 baseline); `session_logs/2026-09-29/03-v5-intended-update-task2-preflight.md` (Task 2 preflight, R2 publication deferred); `session_logs/2026-09-29/04-v5-intended-update-task3-preflight.md` (Task 3 preflight, R2/Neon deferred); `session_logs/2026-09-29/05-v5-intended-update-task4-preflight.md` (Task 4 preflight, MAE reconciled, R2/Neon/freeze deferred); `session_logs/2026-09-29/06-v5-intended-update-task5-preflight.md` (Task 5 preflight); `session_logs/2026-09-29/07-migration-target-incident-and-preview-recovery.md` (Preview 0018); `session_logs/2026-09-29/08-v5-intended-update-preview-rating-and-package-preflight.md` (Task 6 rating projection and packaging preflight); `session_logs/2026-09-29/09-v5-intended-update-preview-runs-and-live-preflight.md` (Preview W0–4 publication and Week 5 live preflight)
- **Commit policy:** Separate user-executed plan commit before implementation; separate implementation and release commits

## Goal

Make the public 2026 team ratings reflect V5's intended one-game-one-observation update. Generate a newly fitted forecast from those ratings, replace the selected predictions for completed Weeks 0–4, and publish newly computed grades and season statistics for those predictions. Prepare a prospective forecast for the next slate whose first kickoff has not passed. Preserve every original rating, prediction, grade, selection, and release record for audit and rollback.

Success means that each selected week has one verified repaired rating lineage, a matching verified forecast bundle, the correct prediction artifact, and, for completed weeks, grades computed from certified finals. The ratings page, game cards, grades, and season statistics must all resolve to the same selected lineage. Completed-week replacements are labeled **retrospective replay**, never prospective picks. Activation requires a separate exact release decision on the finished packets.

## Current State

- The [three-way review](../2026-09-28/v5-estimator-three-way-review.md) and [2026 counterfactual](../../research/2026-09-28-v5-2026-counterfactual.md) establish the intended update and a local, retrospective result: 215 completed Week 0–4 games; margin MAE 15.909 for accepted V5, 15.376 with repaired 2026 ratings and the old bridge, and 14.512 with repaired historical ratings and a refitted bridge. Total gains were small. This research is not a production artifact or release authorization.
- The accepted 2026 priors are derived from each team's 2025 terminal adjusted PPP and usable possessions, not 2025 final rating states. Their 276 offense/defense rows were reproduced exactly. Repairing 2025 historical rating updates is needed for bridge refitting, but does not itself alter those 2026 priors.
- The accepted V5 estimator, live forecast, replay scripts, rating projector, and exact release policy pin the old candidate and bundle. `v5_release_policy` currently permits one model/bundle pair. The ratings UI lists current snapshots across sources; an equal cutoff from two lineages can be ambiguous. The prepare-week rating-currency check also compares against a global latest snapshot rather than the forecast's required manifest.
- Original Weeks 0–4 are selected, frozen, and scored. Week 5 run `2026w5-5d436e58c072` was selected as of 2026-09-27. The implementation must re-read production selection, schedule, quote coverage, and kickoff state before choosing the next prospective slate. A 2026-09-28 counterfactual is retrospective for Weeks 0–4 and is not a frozen prospective Week 5 release.
- R2 is the immutable artifact source, Neon is the derived serving database, and publication requires the restricted pipeline role plus exact admin authorization. Migration `0017_require_rating_manifest.sql` is the current schema endpoint. The independent V6 research bucket is not required for this versioned production candidate.

## Proposed Approach

Create a **versioned V5 intended-update successor**, provisionally `v5-intended-update-2026-v1`, alongside accepted V5. Promote the already reviewed repair mathematics into a production module and build certified historical and 2026 artifacts. Refit the same alpha-10 Ridge bridge on the repaired historical pregame ratings. Keep the existing V5 code path and its old bundle intact as rollback.

At every 2026 forecast cutoff, the repaired updater uses only earlier-week games whose six-hour post-kickoff availability boundary has passed. It recalculates V5's four-pass opponent adjustment on that admissible graph, excluding the forecast game; each source game contributes its own adjusted PPP and its own usable possessions exactly once. Missing opponent context falls back to raw PPP with an explicit flag. Preserve the accepted possession rules, 2025-derived scales and preseason priors, `rho=0.60`, exposure constant `k=8`, game population, offsets, bridge features, and interval calibration protocol. The bridge refit may change coefficients and calibrated uncertainty, but must not train on 2026 outcomes.

Use a self-contained, signed **2026 season rating manifest** for the successor. It contains the certified preseason priors and each immutable pregame/current generation through the manifest cutoff, with source-game IDs, availability times, parent hashes, and logical hashes per generation. A later manifest must reproduce earlier generation hashes unless a separately versioned correction is expressly reviewed. Prediction runs bind the exact rating manifest SHA and successor bundle SHA. For completed-week replay, a manifest may physically include later data, but its verifier must independently reconstruct each earlier pregame state using only that earlier cutoff; the resulting forecast remains labeled replay.

Add an append-only approval registry for multiple exact model/bundle pairs and transactionally select the verified replacement runs as a set. The old pair remains authorized for rollback. Public rating periods are scoped to the selected source and use source-qualified IDs; old direct links remain resolvable to their original lineage. The new `system_stats` are recomputed from the newly selected, scored runs. No old object or row is overwritten.

## Scope

### Included

- Certified repaired historical rating frame and through-2025 forecast bundle, plus independently verified 2026 rating generations.
- New 2026 Weeks 0–4 predictions at the original admissible game cutoffs, their new grades from certified finals, and selected-run statistics.
- One prospective successor forecast for the first still-unstarted slate, only if its timestamped source and freeze gates can be met.
- Versioned publication, policy, selection, UI, rollback, and operator documentation needed to serve the new lineage consistently.

### Excluded

- Changing possession measurement rules, 2025 terminal measurements, 2026 preseason prior formula, training population, rating parameters, or betting thresholds.
- Treating reconstructed Weeks 0–4 as prospective performance or making a V6 model selection from this release.
- Mutating accepted V5 or V4 artifacts, original grades, frozen runs, or original selection-history records.
- A production activation by implementation alone. Exact run-specific release authorization remains a separate final decision after reviewable packets exist.

## Affected Components and Contracts

- Rating mathematics and artifact builders: `src/cks_picks_cfb/ratings/`, `src/cks_picks_cfb/ratings_lab/` as the parity reference, `scripts/pipeline/publish_v5_ratings.py` or a successor projector, and relevant R2 verifier code.
- Forecast application and replay: `src/cks_picks_cfb/data/data_first_live_forecast_v1.py`, `src/cks_picks_cfb/forecast/live_sources.py`, `scripts/pipeline/build_v5_replay.py`, live runner, and signed bridge/bundle manifests. Freeze old constants; introduce explicit versioned routing for the successor.
- Storage and release: a new append-only `contracts/migrations/0018_*.sql` (confirm numbering before creation), `contracts/schema.sql`, `contracts/schema.ts`, `scripts/pipeline/publish_to_db.py`, `scripts/pipeline/check_prepared_week.py`, `scripts/pipeline/validate_v5_release_packet.py`, `src/cks_picks_cfb/ops/public_selection.py`, and associated restricted/admin grants.
- Serving: `web/src/lib/v5.ts`, `web/src/lib/rating-periods.ts`, ratings/game/stat views, and their contracts. `prediction_runs.rating_manifest_sha256` remains mandatory for the successor.
- Operations and evidence: `docs/ops/v5_weekly_operator.md`, production runbook, current status guide, exact release packets, and implementation session logs.

## Implementation Tasks

### Task 1 — Pin the baseline and source lineage

**Changes:** Record the selected runs, frozen/score state, certified finals, exact historical and weekly measurement/rating manifest SHAs, market quote selections and capture times, first kickoff for the target slate, 2025 prior source, and old bundle hash. Resolve current dirty research files before implementing; do not discard them. Confirm R2 Preview and production credentials by presence only and any local data root if used; never write repository `./data/`.

**Baseline captured 2026-09-29:** [Source lockfile](v5-repair-2026-source-lock.json) contains the read-only production selection, game/final/quote keys, row hashes, prior research parents, and exact post-Week 0–4 certified measurement/rating SHAs. Refresh its time-sensitive selection and next-kickoff fields before release; its historical source identities remain pinned.

**Acceptance criteria:** A machine-readable, deterministic source lockfile and read-only baseline report identify all game keys, parents, temporal boundaries, and old rollback IDs. No missing game, line, or outcome is silently imputed. If Week 5's kickoff or freeze boundary has passed, use the next unstarted slate for live release and handle Week 5 only as replay after results are certified.

### Task 2 — Package and independently verify the repaired rating and bridge lineage

**Changes:** Promote the reviewed one-game-one-observation algorithm into a versioned production path. Generate signed repaired historical pregame states for 2015–2019 and 2021–2025, excluding 2020, and refit the common alpha-10 Ridge bridge and earlier-only interval calibration. Independently verify source checksums, exact V5-control fidelity, update math, no future game influence, feature/offset parity, bridge coefficients and bundle application. Use no 2026 targets in fit or selection.

**Acceptance criteria:** The accepted V5 control reproduces certified means/variances and bridge predictions within documented numerical tolerance. Repaired history and the final bundle have immutable R2 manifests and independent verification records. Retrospective metrics are compared with the research report; unexplained population or material prediction differences stop promotion.

### Task 3 — Build complete 2026 rating generations

**Changes:** From the pinned 2025 terminal measurements, generate the certified 2026 priors and each pregame/current cutoff through the selected live slate. Give every state its admissible source-game IDs, exposure, context flags, and lineage. Sign a self-contained season manifest with logical generation hashes. Build a source-specific rating projector that appends these rows to Neon without changing old rows.

**Acceptance criteria:** All 276 prior rows equal the accepted priors; every scheduled eligible game has offense/defense states for both teams at its own cutoff; all 138 FBS teams have a current row at each displayed period, using prior-only states when needed. Earlier generation hashes cannot change when a later week is added. Projecting twice is idempotent; any conflicting same-ID row fails. The prepare-week gate compares the exact required manifest SHA and verified cutoff, not a global maximum.

### Task 4 — Generate versioned forecasts and replacement scores

**Changes:** Add explicit successor routing to live/replay forecast builders without changing the old V5 path. Bind each forecast to the repaired rating and refitted bundle SHAs. Replay Weeks 0–4 against the same eligible 215 game keys and timestamped original market-quote policy; calculate new prediction and interval fields. Using certified final scores, build new run-specific spread/total grades with the existing threshold policy. Produce a prospective run for the next eligible slate from fresh pre-kickoff sources.

**Acceptance criteria:** Every completed-week target has one matching new prediction; quote IDs and line availability are accounted for; no result enters a prediction input. New grades link only to the new prediction run and certified outcome reference. Missing finals or needed quotes block that week. The new prospective run is generated and frozen before its first kickoff or is explicitly deferred to the next slate. Forecast and score artifacts are deterministic under pinned inputs.

### Task 5 — Make release and serving lineage-aware

**Changes:** Migrate the singleton model/bundle policy to an append-only, admin-approved registry while preserving the old pair and exact per-run live/replay authorizations. Validate each run against its approved model, bundle, rating source, evidence class, and week. Implement transactionally validated multiweek selection with selection-history rows and one `system_stats` recompute. Scope current ratings and period navigation to the selected lineage; use source-qualified period IDs and preserve legacy deep links to their original source. Ensure scores, game cards, and ratings read the same selected set.

**Acceptance criteria:** Preview can select all replacement Weeks 0–4 and the eligible live week atomically, with no visible mixed lineage. A failed validation leaves the old selection intact. Old V5 remains selectable as a tested rollback. The restricted pipeline role cannot add approved model pairs or release authorizations. A legacy rating link is stable, while the default ratings page follows the active selection. A mismatch between selected forecast and rating SHA is surfaced as a release failure.

### Task 6 — Rehearse, assemble packets, and make the exact release decision

**Changes:** Run the full sequence in Preview using production-equivalent migration/grants and R2 manifests. Compare each old/new week, game, rating, prediction, grade, interval, and resulting season statistic. Test rollback and reactivation. Prepare exact production packets with source/bundle hashes, run IDs, quote/outcome refs, game counts, freeze timestamps, known retrospective status, score deltas, UI readback, and rollback IDs. Record the new model family in public copy and operating docs.

**Acceptance criteria:** Preview readback proves that W0–4 public predictions and scores change together, every completed game can be traced to a grade and rating, and the active week remains prospective only if frozen before kickoff. There is no unreviewed partial rollout. Stop before production authorization or selection and present the exact packets for the user's release decision.

### Task 7 — Execute an authorized production release and verify

**Changes:** Only after explicit approval of the exact packets, apply the reviewed migration/grants, register the successor pair, insert run-specific release authorizations, project verified ratings, publish replacement runs and grades, and atomically select the completed and eligible live runs. Recompute selected-run statistics in the selection transaction. Check Neon and the public site against exact run IDs and manifest SHAs. Preserve an immediate batch rollback to the old selected runs.

**Acceptance criteria:** Production readback shows complete ratings, new predictions, new grades, and correct season statistics for Weeks 0–4, with replay labels; the prospective week has no grade until certified finals. All original artifacts remain retrievable. If any invariant fails, restore the original selected-run set and verify public consistency. Archive the exact release evidence and update the weekly operator to continue the successor lineage.

## Testing Strategy

- Focused estimator tests: three-game weighting, each source game once, sparse/missing opponent context, same-week exclusion, six-hour boundary, byes, postponed games, FCS, missing possessions, 2019→2021 gap, 2020 exclusion, and future-result invariance.
- Artifact and forecast tests: accepted V5 replica equality, historical and 2026 manifest checksum/parent verification, deterministic rerun, no training leakage, exact game-key and feature parity, interval calibration and coverage diagnostics, 215-game counterfactual reconciliation, and current-slate key/quote coverage.
- Database and site tests: migration/grants, old-pair rollback, exact release authorization, source-specific rating currency, idempotent append-only projection, atomic batch-selection failure injection, score/stat recomputation, active source navigation and old deep links.
- Full Preview rehearsal through public readback, then scoped existing V5/storage/boundary regressions, `make contracts-check`, Ruff format and lint, relevant TypeScript checks/build, documentation build, and `git diff --check`. Do not run production mutation as a test.

## Risks and Edge Cases

- Repaired Week 0–4 results are retrospective and may look like historical published picks; label them conspicuously and keep the original prospective record accessible in audit history.
- Bridge refitting changes the forecast as well as ratings; publish exact old/new attribution and interval behavior, even if some weeks or totals worsen. No Alabama–South Carolina ordering threshold determines release.
- Earlier weekly measurement captures may differ from a later Week 4 capture. Use certified per-cutoff parents or prove value equality and availability; stop if the 215-game population or state lineage cannot be reconciled.
- An active week can cross kickoff while the packet is being prepared. Never recast a post-kickoff run as live; roll the prospective target forward and amend the exact packet.
- Simultaneous old/new rows at equal cutoffs can contaminate UI or preparation gates unless every query uses the selected source SHA. Selection, ratings, scores, and stats must switch together.
- The release policy migration must preserve exact old authorization semantics and least privilege. A faulty migration could remove rollback even though old artifacts remain.
- Published score counts can legitimately differ from old counts when new edges cross the unchanged grade threshold. Validate policy and game coverage, not an assumed fixed grade count.

## Definition of Done

- [ ] All implementation tasks and acceptance criteria are complete.
- [ ] Required validation and independent verification pass.
- [ ] Exact production release is separately approved and either completed with readback or recorded as prepared and awaiting that decision; the latter is **not** an implemented production fix.
- [ ] Original runs and a tested batch rollback remain available.
- [ ] Documentation, release evidence, and implementation session log are updated.
- [ ] Contract status reflects the actual outcome: `Implemented` only after production readback, otherwise `In Progress`.

## Amendments

Material changes to estimator math, training population, selection semantics, production schema, or release scope require a documented amendment and renewed review before implementation continues. Minor implementation details may be recorded in the implementation log if they preserve this contract's interfaces and acceptance criteria.
