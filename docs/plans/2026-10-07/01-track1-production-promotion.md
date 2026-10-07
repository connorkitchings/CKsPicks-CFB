# Track 1: Production Venues and Full `dev` Promotion

- **Status:** In Progress
- **Created:** 2026-10-07
- **Planner:** Sol
- **Approval source:** User explicitly requested implementation of this exact Track 1 plan on 2026-10-07. Repository workflow requires the separate plan commit and a fresh implementation task before implementation work.
- **Implementation log:** `session_logs/2026-10-07/02-track1-production-promotion-implementation.md`
- **Commit policy:** Separate user-run plan commit on `dev`; all later Git operations are user-run. Production venue publication and production branch promotion require separate user authorization after their release packet is reviewable.
- **Authority:** Contract 04, its Window 1 release gates, Stage 7A/7B web read-path contracts, and this approved Track 1 decision.

## Goal

Publish complete pinned 2026 venue facts to Production and promote the reviewed `dev` code to `main`, where Vercel deploys the application. Confirm that the public site serves the reviewed commit and that the Performance and matchup read paths operate safely with Production evidence.

Window 1 fixes are already ancestors of `main`. The full `dev` promotion therefore includes later Stage 7A/7B web read-path changes. This plan explicitly includes that broader deployment while keeping Window 2 serving cutover inactive.

## Current State

- Work is on `dev`; at planning capture, the worktree was clean, `dev` was `8f3c9b62098ccb6fedf43ac24b45a3efe06377fb`, and local `main` was `562319aaf0510d840d60806e11c4802ea0c80049`. `dev` was 49 commits ahead. Recheck all refs before packet approval and again before the user's fast-forward.
- The Window 1 venue publisher supports `--venues-version` but selects the newest validated Silver `games` version dynamically. Add a matching games-version pin so dry-run and apply can use reviewed immutable inputs.
- Venue capture `b569d242e8c4c53b416bfe14` previously covered all 271 then-current Production games, but Week 6 has since started. The game count, source version, hashes, and city coverage must be recaptured; the historical count is not a current acceptance value.
- Preview and Production Week 5 prospective attestations and migrations 0023/0024 were reported applied and read back in Stage 7B logs. Recapture the Production ledger, actual `cks_prod_web` read privileges, designation, and serving baseline for this release.
- This host lacks the `ckspicks-cfb/production/pipeline-url` Keychain item for `cks_prod_pipeline`, so the Production venue dry-run could not run here. Production database and R2 operations must use an authorized operator host and the restricted wrapper.
- Repository `.vercelignore` limits uploaded deployment files to `web/`. Vercel's configured Production branch must be verified before relying on automatic deployment from a push to `main`.

## Proposed Approach

Pin both Silver input versions, prepare and review a single release packet for Production venue data and the full `dev` deployment, then execute the two authorized actions separately. Use a Vercel Preview deployment and read-only Preview/Production checks to validate the new web reads before production promotion. Vercel Git deployments create Preview deployments for pull requests and Production deployments when changes reach the configured Production branch; capture the current Production deployment first for rollback ([Git deployment behavior](https://vercel.com/docs/git), [rollback procedure](https://vercel.com/docs/deployments/rollback-production-deployment)).

## Scope

### Included

- A backward-compatible `--games-version` argument for the game venue publisher and tests for exact version lookup and fail-closed coverage.
- Fresh Preview and Production evidence collection, pinned Production venue dry-run, review of all `main..dev` web changes, CI and Vercel Preview verification, and a release packet.
- Separately approved Production venue publication and user-run fast-forward/push of the reviewed `dev` SHA to `main`.
- Post-publication database readback, post-deployment Vercel and public-route verification, and release/status documentation.

### Excluded

- Window 2 serving selection, current-week movement, production authorization, release cutover, freeze, or rollback operations.
- Production schema migrations or prospective-record registration; Stage 7B reports these as complete, and this plan only re-verifies their state.
- Any publication from an unpinned or changed Silver input, and any Git commit, merge, push, or deployment action performed by the implementation agent.

## Affected Components and Contracts

- `scripts/pipeline/publish_game_venues.py` and `tests/test_game_venues.py` for exact Silver games-version selection.
- Window 1 contract 04 release receipt; Stage 7A/7B Performance and matchup read paths; `.vercelignore` and the configured Vercel Git deployment.
- `docs/status.md`, `docs/plans/index.md`, and the implementation session log after evidence is captured.

## Implementation Tasks

### Task 1 — Pin the complete venue input identity

**Changes**

- Add optional `--games-version` and pass it to the existing validated Silver catalog lookup. Keep current default selection for existing callers.
- The Track 1 command must provide both `--games-version` and `--venues-version b569d242e8c4c53b416bfe14`; record version IDs and content hashes in the release packet.
- Do not broaden the city requirement. Every current Production game must resolve to one unique venue row with a nonempty city; state may be empty for valid international venues.

**Acceptance criteria**

- Exact pinned source versions are reflected in the publisher's coverage report and quality identity.
- Missing pinned versions, games missing from Silver, unresolved venue IDs, missing cities, or any duplicate/coverage mismatch fail before writes.

### Task 2 — Capture live release evidence and dry-run Production venues

**Changes**

- On the authorized operator host, verify restricted Preview and Production identities without printing credentials; capture Vercel's current Production deployment and configured Production branch.
- Capture current Git refs, Production migrations and effective `cks_prod_web` privileges, Week 5 designation, current-week pointer, active selections, serving-stat fingerprints, and all 2026 Production games/venue rows.
- Choose the newest validated Silver `games` version for 2026 only after reconciling its complete game-ID set with Production. Pin that exact version and content hash.
- Run the dry-run command through `zsh scripts/ops/with_production_pipeline_env.sh` with `--environment production`, both source pins, `--require-city`, and `--dry-run`. Save the exact proposed insert/update diff and pre-publication row payload.

**Acceptance criteria**

- All current Production games have exactly one matching Silver game and one publishable venue row with city; zero games are absent from Silver and zero venue IDs are unresolved.
- The Week 5 prospective row, schema, role grants, and serving state match the release packet baseline.
- No database, R2, selection, current-week, grade, authorization, or freeze write occurs during preparation.

### Task 3 — Validate the complete `dev` deployment

**Changes**

- Review every changed web file between `main` and the exact candidate `dev` SHA. Verify `.vercelignore` continues to ship only `web/` and that no new code activates a Window 2 serving cutover.
- Run the full Python suite, Ruff, `make contracts-check`, web lint, typecheck, publication tests, production build, Performance/matchup Playwright scenarios, MkDocs, and `git diff --check`.
- Have the user open a `dev` to `main` PR. Require green CI and a Vercel Preview deployment for the exact SHA. Verify its database identity is the restricted Preview web role, not fixture mode.
- Check Picks, Results, Performance, and representative matchup pages against real Preview data. Confirm replay and Week 5 retrospectively attested prospective records are separate; expected lineage mismatches must show the guarded unavailable/updating state and disable incompatible sharing.

**Acceptance criteria**

- All required checks pass on the candidate SHA and the Preview deployment reports that exact SHA.
- Real Preview reads show accurate retrospective/prospective labels and no latest-run fallback. Any unexpected page failure, role mismatch, or newly hidden matchup data stops promotion for investigation.

### Task 4 — Assemble the packet and gate Production actions

The packet records the exact candidate `dev` SHA; current `main` SHA and prior Vercel Production deployment URL; CI and Preview evidence; pinned games/venues version IDs and hashes; proposed venue row diff and before payload; Production schema, role, prospective-row, and serving-state readbacks; and exact rollback procedure.

After review, request and record **separate** user authorizations for (a) the Production venue publication and (b) the `main` fast-forward/push. Do not combine one authorization as authority for the other.

### Task 5 — User-run Production venue publish and verification

After the venue-specific authorization, the user runs the same pinned publisher through `with_production_pipeline_env.sh`, removing `--dry-run` and retaining `--require-city`. Independently read back every affected `game_venues` row and compare it with the pinned payload. Recompute the serving fingerprints and confirm selections, current week, grades, and statistics remain at the packet baseline.

If the source hash, selected game set, or proposed diff changes after approval, stop and rebuild the packet. If a venue write is wrong, preserve the before payload and obtain a separately reviewed repair decision; do not roll back serving state.

### Task 6 — User-run full `dev` promotion and production smoke checks

After deployment-specific authorization, the user fast-forwards `main` to the reviewed `dev` SHA and pushes it. Verify Vercel's Production deployment reports the approved SHA. Check `/api/health`, Picks, Results, Performance, and representative matchup routes against live Production reads. Recheck venue coverage, Week 5 attestation labeling, `cks_prod_web` read access, and the serving fingerprints. If deployment health fails, restore the captured prior Vercel deployment using the documented Vercel rollback flow, verify service, and prepare a user-run Git correction so branch and deployed state can be reconciled.

## Testing Strategy

- Focused tests for games version pinning, missing catalog versions, complete game key coverage, city requirements, and international city-only venues.
- Full repository checks listed in Task 3, including database-backed migration/query tests where available.
- Real Preview web-page verification and read-only Production identity/schema/designation/serving checks on the authorized operator host.
- Production venue dry-run, then independent row readback and serving-state comparison after the separately authorized apply.
- Post-deployment route and Vercel commit verification; retain the previous deployment URL for rollback.

## Risks and Edge Cases

- Silver games and venues captures may not cover the Week 6 additions. Stop and obtain a reviewed current source capture rather than relaxing coverage or using an unpinned version.
- Preview web behavior is not evidence of Production permissions; verify `cks_prod_web` effective access and the Production Week 5 designation before promotion.
- The full `dev` merge includes Stage 7A/7B read paths. Their fail-closed behavior can hide model-derived matchup sections when production provenance does not match; identify and review those cases before release.
- A Vercel rollback restores application code only. It does not restore database venue rows; retain the exact before payload for a separately reviewed data correction.
- If either branch moves or the deployed Production commit differs from the captured baseline, stop and recapture the packet.

## Definition of Done

- [ ] Both venue source versions are pinned and the Production dry-run covers every current Production game with a city.
- [ ] Production schema, effective web grants, Week 5 designation, and serving baseline are freshly verified.
- [ ] Full validation, CI, and real-data Vercel Preview checks pass on the exact candidate SHA.
- [ ] The release packet is reviewed and separate user authorizations are recorded for Production venue publication and `main` promotion.
- [ ] User-run venue publication is independently read back; serving fingerprints remain unchanged.
- [ ] User-run `main` fast-forward produces a healthy Vercel deployment at the reviewed SHA; public route checks pass and rollback target is retained.
- [ ] Contract 04 Window 1 receipt, `docs/status.md`, plan index, and implementation log reflect observed results; plan status is updated only to match completed gates.

## Amendments

Material changes to the candidate SHA, source identities, Production write scope, web behavior, or rollback approach require a reviewed amendment before release. The separate user authorization gates remain in force.

### Implementation checkpoint — 2026-10-07

Tasks 1–2 are delivered locally: backward-compatible games pin, exact source hashes in quality identity, source-duplicate rejection, focused no-write failure tests, fresh restricted-role Preview/Production capture and pinned Production dry run. Current database venue coverage is 271/271 cities with zero business-column changes; applying the existing upsert would still change timestamps. Both existing Week 5 designations were independently verified against live sources and immutable bytes. All serving fingerprints stayed unchanged.

Task 3 local validation passed: full Python 2,039/12 skipped, disposable PostgreSQL 32, venue 19, publication 134, Performance/matchup Playwright 24, Ruff, contracts, lint/typecheck, fixture build and documentation. The reviewed web diff revealed a reproducible PostgreSQL 42P10 query defect. The user's follow-up explicitly authorized a localized SQL-shape repair; adding the ordering column to DISTINCT preserves selection semantics, and actual repaired Drizzle SQL passes in both environments. This is a mechanical repair within release preparation, not a serving selector redesign.

The [release preparation packet](track1-release-packet.md) remains **HOLD**, not approval-ready. Multiple manifest sources share rating cutoffs; the provenance query can choose a source different from the rendered ratings. Resolving that selector meaning requires a reviewed decision. A final committed candidate, `dev`→`main` PR, green CI, restricted-role exact-SHA real Preview page verification, and the two separate Production authorizations are also outstanding. No Production venue apply, deployment, Git mutation, or Stage 7B serving write occurred. Plan remains In Progress; Tasks 5–6 and the release definition of done remain unchecked.


### Reopened source-binding verification — 2026-10-07

The user's explicit follow-up authorized resolving ambiguity when the source is derivable from Stage 7A. Inspection confirms the rendered `getRatingsAsOf` rows retain their owning manifest SHA, including source-pinned preseason backfills. Provenance is now filtered by the single source of the exact two rendered teams; missing/mixed/ambiguous sources remain fail closed. Forecast and published-stat source comparisons are unchanged. This is implementation of the approved lineage guard, not a new selector or serving decision.

Three focused query regressions pass with disposable PostgreSQL, including competing manifests at the same cutoff executing actual Drizzle SQL. Re-derived rendered-source queries pass against both real environments (two competing cutoff sources; only the rendered source returned). Final lint/typecheck, fixture build, 135 publication tests (one separately passed DB test skipped without its URL), 24 browser tests, Ruff and serving fingerprint readback pass. The semantic hold is lifted; final candidate commit/PR, green CI and real restricted-web exact-SHA Preview verification still hold promotion. No live writes or Git mutations occurred.
