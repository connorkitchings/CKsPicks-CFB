# Week 6 Display-Only Run on Served (Successor) Lineage

- **Status:** Superseded (2026-10-07; no implementation was started; see Closure)
- **Created:** 2026-10-07
- **Planner:** Sol
- **Approval source:** User authorization in session (2026-10-07); evidence class `pending` and "no label" confirmed by the user 2026-10-07 (see Amendment 1)
- **Implementation log:** none (no implementation work was done); planning log `session_logs/2026-10-07/05-week6-display-run-planning.md`
- **Commit policy:** Commit with implementation

## Goal

Ingest complete 2026 Week 5 data (plays, drives, game stats) into Silver, extend the verified V5 intended-update rating and forecast lineage through Week 5, and publish a live display-only Week 6 prediction run with evidence class `pending` to Preview and Production.

This unblocks Week 6 on the public web app, replacing the current hold screen ("Picks dropping soon") with all 58 FBS Week 6 game leans and post-Week-5 ratings, without creating invalid prospective evidence for games that have already kicked off.

## Current State

- **Serving Lineage:** V5 intended-update successor (`v5-intended-update-2026-v1`), rating source `e80ae347…`, refitted inference bundle `30c4f1eb…`.
- **Data Boundary:**
  - Silver `game_outcomes` contains Week 5 certified finals (56 games).
  - Silver `games` contains all 58 scheduled Week 6 FBS games.
  - Silver `plays` (`443019a9…`) contains Weeks 0–4 only; zero Week 5 plays currently exist in Silver.
  - `v5_rating_snapshots` stops at week 5 ("Post-Week 4"), so no ratings exist to forecast Week 6.
- **Schedule & Clock:**
  - Week 6 has 58 FBS games. Southern Miss @ Troy kicked off on Tuesday Oct 6 (`2026-10-07T00:00Z`) and has completed.
  - Earliest remaining kickoffs are Wednesday Oct 7 at `23:00Z` and `23:30Z`, followed by Thursday and Saturday slates.
  - CFBD currently provides spread and total lines for all 58 games from multiple sportsbooks.
- **Governance Constraints:**
  - Contract 04 Appendix B & Stage 7B: A run cannot be certified as prospective evidence once kickoff has passed.
  - Database migration 0023 & `freeze_week.py`: Freezing is rejected within 1 hour of the earliest kickoff. Running `freeze_week.py` on a run past kickoff would mutate `evidence_class` to `missed`, rendering the run unselectable by `public_selection.py`.
  - Therefore, **this Week 6 run must NEVER be frozen or closed via `freeze_week.py` / `close_week.py`**. It remains in `state = 'published'` with `evidence_class = 'pending'`.

## Proposed Approach

1. **Evidence Class:** Use `evidence_class = 'pending'`.
   - The forecast is built during Week 6 before 57 of the 58 games kick off.
   - It cannot enter the official `prospective_week_records` table because no pre-kickoff freeze attestation will exist.
   - It can still be graded after finals via `backfill_v5_unconstrained_grades.py --week 6 --grades-only` (identical to the unconstrained grading path).
2. **Source Lock Generator:** Implement a small utility `scripts/pipeline/build_v5_intended_update_source_lock.py` to deterministically capture Week 6 schedule, market keys, cutoffs, and parent digests into `v5-repair-2026-w6-source-lock.json`.
3. **Parameterize Successor Scripts:** Generalize Week-5-specific scripts to accept `--week`, ensuring backwards parity so Week 5 `p2` hashes reproduce byte-for-byte.
4. **Silver Refresh:** Execute `prepare-week` in Preview with strict stop conditions (Weeks 0–4 plays must not change).
5. **Rating Extension:** Run `build_v5_intended_update_2026.py` with `--previous-manifest` to guarantee byte-for-byte invariance of earlier generations (`pregame_w0..w5` and `current_post_w0..w4`) while appending `pregame_w6` and `current_post_w5`.
6. **No web notice:** the user decided (2026-10-07) that no label or banner is added. The standard "Published" pill and each game's kickoff time stand; there is no web change in this contract.
7. **Preview Rehearsal → Production Promotion:** Rehearse in Preview first; upon user approval, promote Silver to Production catalog, insert serving authorization, publish, and select.

## Scope

### Included
- Building `scripts/pipeline/build_v5_intended_update_source_lock.py`.
- Parameterizing `build_v5_intended_update_2026.py`, `build_v5_intended_update_forecasts.py`, `build_v5_intended_update_live_serving.py`, `package_v5_intended_update_live_run.py`, `verify_v5_intended_update_live_serving.py`, and `authorize_v5_intended_update_preview.py`.
- Automated regression test validating Week 5 `p2` bit-for-bit parity.
- Preview Week 5 Silver ingest and verification.
- Production catalog promotion of refreshed Silver (user-run).
- Generating and projecting Week 6 ratings and matchup data.
- Building, verifying, packaging, and publishing the Week 6 serving run to Preview and Production.
- Publishing `team_season_stats` as-of-week 6 and matchup data for Week 6.

### Excluded
- Running `freeze_week.py` or creating a prospective freeze attestation.
- Model re-training, hyperparameter adjustments, or refitting inference bundle `30c4f1eb…`.
- Reconstructing Weeks 0–5 historical completed games (reserved for Stage 7B).
- Modifying Docker CI parity plan (`docs/plans/2026-10-07/02-docker-python-ci-parity.md`).

## Affected Components and Contracts

- `scripts/pipeline/build_v5_intended_update_source_lock.py` (new)
- `scripts/pipeline/build_v5_intended_update_2026.py`
- `scripts/pipeline/build_v5_intended_update_forecasts.py`
- `scripts/pipeline/build_v5_intended_update_live_serving.py`
- `scripts/pipeline/verify_v5_intended_update_live_serving.py`
- `scripts/pipeline/package_v5_intended_update_live_run.py`
- `scripts/pipeline/authorize_v5_intended_update_preview.py`
- `tests/test_v5_intended_update_week_parameterization.py` (new)
- Neon tables: `prediction_runs`, `predictions`, `v5_rating_snapshots`, `team_season_stats`, `v5_serving_authorizations`, `site_week_selections`, `current_week`.

---

## Implementation Tasks

### Task 1 — Source Lock Generator & Script Parameterization

**Files:**
- `scripts/pipeline/build_v5_intended_update_source_lock.py` (new)
- `scripts/pipeline/build_v5_intended_update_2026.py`
- `scripts/pipeline/build_v5_intended_update_forecasts.py`
- `scripts/pipeline/build_v5_intended_update_live_serving.py`
- `scripts/pipeline/verify_v5_intended_update_live_serving.py`
- `scripts/pipeline/package_v5_intended_update_live_run.py`
- `scripts/pipeline/authorize_v5_intended_update_preview.py`
- `tests/test_v5_intended_update_week_parameterization.py` (new)

**Changes:**
- Create `build_v5_intended_update_source_lock.py` to extract schedule games and market keys for a specified target week while carrying forward locked historical parents.
- Update `build_v5_intended_update_2026.py` to dynamically hash pregame team states for `range(target_week + 1)` and support `--previous-manifest`.
- Add `--week` parameter across the intended-update live serving, forecast, verification, packaging, and authorization scripts, defaulting to 5 if omitted.
- Add test verifying that when `--week 5` and release tag `20260929-p2` are passed, generated hashes match the published Week 5 p2 outputs.

**Acceptance criteria:**
- `p2` parity test passes with identical SHA-256 digests.
- `--week 6` CLI arguments run without errors or hardcoded week 5 path collisions.

---

### Task 2 — Ingest Week 5 Data into Preview Silver

**Files:**
- Operational execution in Preview via `prepare-week`.

**Commands:**
```bash
PYTHONPATH=src:. zsh scripts/ops/with_preview_env.sh uv run python -m cks_picks_cfb.ops prepare-week \
  --year 2026 --week 6 --as-of 2026-10-07T18:00:00Z --environment preview
```

**Acceptance criteria & Stop conditions:**
- Week 5 plays and game stats exist in Preview Silver.
- **STOP CONDITION:** Verify that existing Weeks 0–4 Silver play rows did not change (byte hash / content check against pre-apply Silver). If any past week row changed, pause immediately for review before proceeding.

---

### Task 3 — Promote Refreshed Silver to Production Catalog

**Files:**
- Production catalog registration via `promote_silver_versions.py`.

**Commands:**
```bash
# Dry run verification
PYTHONPATH=src:. zsh scripts/ops/with_preview_env.sh zsh scripts/ops/with_production_pipeline_env.sh \
  uv run python scripts/pipeline/promote_silver_versions.py --season 2026 --dry-run

# User execution (live catalog registration)
PYTHONPATH=src:. zsh scripts/ops/with_preview_env.sh zsh scripts/ops/with_production_pipeline_env.sh \
  uv run python scripts/pipeline/promote_silver_versions.py --season 2026
```

**Acceptance criteria:**
- Production catalog registers new Silver versions for `plays`, `games`, `game_outcomes`, and `team_game_stats`. Zero file re-uploads needed (R2 bucket is shared).

---

### Task 4 — Build Week 6 Source Lock & Ratings Replay

**Files:**
- `v5-repair-2026-w6-source-lock.json`
- `scripts/pipeline/build_v5_intended_update_2026.py`

**Commands:**
```bash
# 1. Generate Week 6 source lock
PYTHONPATH=src:. uv run python scripts/pipeline/build_v5_intended_update_source_lock.py \
  --season 2026 --week 6 --output artifacts/locks/v5-repair-2026-w6-source-lock.json

# 2. Build rating manifest with invariance check on previous manifest
PYTHONPATH=src:. uv run python scripts/pipeline/build_v5_intended_update_2026.py \
  --run-id v5-intended-update-2026-w6-r1 \
  --expected-code-sha $(git rev-parse HEAD) \
  --source-lock artifacts/locks/v5-repair-2026-w6-source-lock.json \
  --previous-manifest <week5_rating_manifest_uri> \
  --local-output /tmp/v5_w6_ratings \
  --apply

# 3. Project ratings into Preview v5_rating_snapshots
zsh scripts/ops/with_preview_env.sh uv run python scripts/pipeline/publish_v5_intended_update_ratings.py \
  --season 2026 --environment preview --rating-manifest-uri <new_manifest_uri>
```

**Acceptance criteria:**
- Previous generation digests (`current_post_w0` through `w4`, `pregame_w0` through `w5`) match exactly.
- New generation `current_post_w5` (138 teams) and `pregame_w6` are created and verified.
- Preview `v5_rating_snapshots` populates post-Week 5 ratings.

---

### Task 5 — Market Capture, Forecast, and Serving Package

**Files:**
- `scripts/pipeline/build_v5_intended_update_forecasts.py`
- `scripts/pipeline/build_v5_intended_update_live_serving.py`
- `scripts/pipeline/package_v5_intended_update_live_run.py`
- `scripts/pipeline/verify_v5_intended_update_live_serving.py`

**Commands:**
```bash
# 1. Fresh market quote capture for Week 6
PYTHONPATH=src:. zsh scripts/ops/with_preview_env.sh uv run python scripts/data/fetch_cfbd_market_quotes.py \
  --season 2026 --week 6 --environment preview

# 2. Build forecast
PYTHONPATH=src:. uv run python scripts/pipeline/build_v5_intended_update_forecasts.py \
  --release-tag 20261007-w6 \
  --week 6 \
  --expected-code-sha $(git rev-parse HEAD) \
  --source-lock artifacts/locks/v5-repair-2026-w6-source-lock.json \
  --output /tmp/w6_forecasts

# 3. Build serving candidate and package run
PYTHONPATH=src:. uv run python scripts/pipeline/build_v5_intended_update_live_serving.py \
  --week 6 --release-tag 20261007-w6 --as-of $(date -u +"%Y-%m-%dT%H:%M:%SZ")

PYTHONPATH=src:. uv run python scripts/pipeline/package_v5_intended_update_live_run.py \
  --week 6 --release-tag 20261007-w6

# 4. Verify candidate
PYTHONPATH=src:. uv run python scripts/pipeline/verify_v5_intended_update_live_serving.py \
  --week 6 --release-tag 20261007-w6
```

**Acceptance criteria:**
- Serving candidate covers 58 FBS games.
- Independent verifier passes with zero errors.
- Run artifact is packaged with `evidence_class = 'pending'`.

---

### Task 6 — Team Stats & Matchup Data As-Of Week 6

**Files:**
- `scripts/pipeline/publish_team_stats.py`
- `scripts/pipeline/publish_matchup_data.py`

**Commands:**
```bash
# Preview: team stats as-of 6
PYTHONPATH=src:. zsh scripts/ops/with_preview_env.sh uv run python scripts/pipeline/publish_team_stats.py \
  --season 2026 --as-of-week 6 --environment preview

# Preview: matchup data bound to new rating manifest
PYTHONPATH=src:. zsh scripts/ops/with_preview_env.sh uv run python scripts/pipeline/publish_matchup_data.py \
  --season 2026 --environment preview \
  --rating-manifest-uri <new_rating_manifest_uri> \
  --measurement-manifest-uri <new_measurement_manifest_uri>
```

**Acceptance criteria:**
- `team_season_stats` has complete as-of-week 6 rows (138 teams) in Preview.
- Matchup tables populate clean metrics for Week 6 matchups.

---

### Task 7 — Preview Rehearsal & Verification

**Files:**
- Preview database operations.

**Commands:**
```bash
# Authorize in Preview
PYTHONPATH=src:. zsh scripts/ops/with_preview_env.sh uv run python scripts/pipeline/authorize_v5_intended_update_preview.py \
  --week 6 --release-tag 20261007-w6

# Publish and select in Preview
PYTHONPATH=src:. zsh scripts/ops/with_preview_env.sh uv run python scripts/pipeline/publish_to_db.py \
  --from-artifact <w6_artifact_uri> --environment preview

PYTHONPATH=src:. zsh scripts/ops/with_preview_env.sh uv run python scripts/pipeline/select_public_run.py \
  --year 2026 --week 6 --run-id <run_id> --reason "Week 6 display run rehearsal" --environment preview
```

**Validation:**
- Test Preview web routes (`/`, `/results`, `/ratings`, `/matchup/<game_id>`).
- Confirm Picks tab renders all 58 Week 6 games with spreads/totals and leans.
- Roll back Preview `current_week` pointer if needed, or leave active.

---

### Task 8 — Production Release (User Execution)

**Files:**
- Production database writes via `with_production_pipeline_env.sh` and admin credentials.

**Steps:**
1. Generate release packet with `scripts/pipeline/validate_v5_release_packet.py`.
2. User inserts authorization row into Production `v5_serving_authorizations` (owner role).
3. User publishes the artifact to Production via `publish_to_db.py --from-artifact --environment production`.
4. User selects the run via `select_public_run.py --year 2026 --week 6 --environment production`.
5. User projects ratings and publishes as-of-6 team stats & matchup data to Production.
6. Verify live Production routes return 200 with Week 6 picks and post-Week-5 ratings.
7. **CRITICAL GOVERNANCE RULE:** Do NOT execute `freeze_week.py` or `close_week.py`.

---

## Testing Strategy

1. **Byte Parity:** `tests/test_v5_intended_update_week_parameterization.py` verifies identical outputs for Week 5 p2 run.
2. **Silver Immutability Check:** Assertion script checking that Weeks 0–4 rows in Silver `plays` remain byte-identical before and after Week 5 ingest.
3. **Rating Invariance:** Built-in `--previous-manifest` check in `build_v5_intended_update_2026.py` verifies all past generation digests match.
4. **End-to-End Suite:** `uv run pytest`, `make contracts-check`, and `npx nx run web:build`.

## Risks and Edge Cases

- **Kickoff Hard Boundary in Freeze Code:** Calling `freeze_week.py` on this run would mark it `missed` and break selection. The run must explicitly remain in `state = 'published'`.
- **CFBD Past Play Retro-Modifications:** If CFBD modified any Week 0–4 plays in their API, re-pulling all completed weeks could alter historical Silver plays. The stop condition catches this immediately.
- **Single Kickoff Past:** Southern Miss @ Troy kicked off Tuesday. Market quote capture will show the game as started; the serving builder must handle or mark Troy without crashing the remaining 57 games.

## Definition of Done

- [ ] Task 1 (Source lock builder & script parameterization) complete and passing parity tests.
- [ ] Task 2 (Preview Silver refresh) complete with Weeks 0–4 row immutability verified.
- [ ] Task 3 (Production Silver promotion) executed by user.
- [ ] Task 4 (Ratings extension) complete and verified against previous manifest.
- [ ] Task 5 (Week 6 forecast & serving package) built and independently verified.
- [ ] Task 6 (Team stats & matchup data) published to Preview.
- [ ] Task 7 (Preview rehearsal) passes all route checks.
- [ ] Task 8 (Production release) executed by user and verified live.
- [ ] Documentation (`docs/status.md` and session logs) updated.
- [ ] Plan status updated to `Implemented`.

---

## Amendment 1 (2026-10-07, before Task 1): mechanical corrections and one added gate

Found while reconciling this contract with the repository. None changes the architecture, evidence class, scope or acceptance criteria; they correct commands and add a safety prerequisite.

- **No web change (user decision).** The optional banner (Proposed Approach item 6, `SlateView.tsx`) is removed. Evidence class stays `pending`.
- **Market capture command.** `scripts/data/fetch_cfbd_market_quotes.py` does not exist. The fresh Week 6 capture is `scripts/research/capture_data_first_phase2.py --kind pregame` (the command the daily "Data-first pregame capture" workflow runs, `--environment preview`, with `--run-id`, `--max-requests` and `--expected-code-sha`); the serving builder consumes it through `--market-ref-uri`. Task 5 step 1 uses that command with a dry run first.
- **Real CLIs.** `build_v5_intended_update_forecasts.py` takes `--release-tag --expected-code-sha --source-lock --local-output --bridge-source --rating-source [--apply --preflight-evidence]` and builds the weeks in the lock (the live week comes from the lock's `active_week`), so it needs no `--week`; the live-serving, package and verifier scripts require `--source-lock` (and `--local-output` for the first two) and have no week flag today. Task 1 adds `--week` (default 5) to the serving builder, packager, verifier and authorizer, validated against the lock's `active_week`; the authorizer's `--week` choices widen from `range(6)` to `range(7)`. Rating builds use the preflight-then-apply form (`--preflight-evidence`), as the operator guide describes.
- **`prepare-week` ordering (Task 2).** Its last step, `target_week_readiness` (`check_prepared_week.py`), fails while the new rating generation is unprojected. Expect the first Task 2 run to build Silver and Gold and then stop at that step; re-run the same pipeline-run ID after Task 4 projects the ratings (steps are resumable). Compare the Silver outputs at the stop point, before ratings.
- **Catalog dataset names.** Silver datasets are `byplay`, `drives`, `games`, `teams`, `game_outcomes` (not `plays`); Task 3 checks those.
- **Scratch paths.** Local outputs use the session scratchpad or `artifacts/`, not `/tmp`.
- **Added gate before Task 8: Production rollback.** The contract had no way back to the hold screen. Task 7 must define and rehearse in Preview the exact reversal of the Week 6 publication and selection (including what restores the "dropping soon" state and which steps need the owner role), and Task 8 may not start until the user has reviewed it.
- **Team stats pins.** Task 6 pins all five Silver inputs to the versions produced in Task 2 and dry-runs with `--diff`; as-of weeks 1-5 must show no change.

## Amendment 2 (2026-10-07, before Task 1): the original-lineage foundation refresh is a prerequisite

**Finding.** `build_v5_intended_update_2026.py::_inputs` reads the measurement manifest's `observations`, the rating manifest's `priors`, and calls `load_live_forecast_sources(measurement_uri, rating_uri, schedule_uri, bridge_uri, as_of, target_week)`; all of these come from the source lock's `research_source_import` (`replay_parents`, `live_manifest_*`). Today those parents end at Week 4 (`possession-v1-measurements-20260927-w4`, `possession-v1-rating-replay-20260927-w4`, live forecast `forecast-v1-2026w5-live-r2`). The Week 5 opening (`session_logs/2026-09-27/01.md`) refreshed them first. The contract's Task 4 starts at the lock and omits that refresh, so the successor rating build for Week 6 would have no Week 5 observations.

**Added task (inserted as Task 3B, after Silver promotion and before Task 4), using existing tooling, Preview only, new immutable run IDs, independent verifier after each step:**
1. Repair-2026 refresh through Week 5 (`verify_data_first_repair_v3.py`).
2. Possession measurements through Week 5 (`verify_data_first_possession_measurements.py`).
3. Original-lineage rating replay through Week 5 (`verify_data_first_possession_rating_replay.py`).
4. Contract 09 live forecast for Week 6 (`run_v5_live_forecast.py`: preflight, apply, verifier). It is the `live_manifest` parent of the successor chain; no spread or total from it is served directly.
Each step follows the operator guide (`docs/ops/v5_weekly_operator.md`; the cycle descriptor form `v5_weekly_cycle_v1` or the direct runners used on 2026-09-27), with the same fail-closed rules: review the preflight, then apply from a clean committed SHA.

**Effects on other tasks.** The Week 6 source lock (Task 4) pins these new parents (`research_2026_measurement_sha256`, `research_source_import.*`) instead of the Week 4-era ones, so the lock builder takes them as explicit inputs. Task 4's `--previous-manifest` check still compares generation digests only; if the refreshed measurements change any earlier week's values, the build fails closed and work stops for review. The original-lineage Week 6 forecast from step 4 is an intermediate artifact and is never selected or served.

**Scope/time.** This stays inside the Goal (extend the lineage through Week 5) and adds no new architecture, but it makes the work several sessions, not one; Task 1 (local code and tests) can proceed in parallel with nothing external being written.

---

## Closure (2026-10-07): superseded by the decision to hold Week 6 until the Week 7 cutover

**Decision (user, 2026-10-07):** do not publish a Week 6 display run. Week 6 keeps the hold screen and joins the corrected replay set after its finals stabilize, as the Stage 7B plan already assumes. No code, Silver, rating, forecast, database or Production change was made under this contract.

**Why it was stopped (reconciliation findings, kept for any future attempt):**
1. A `pending` successor run cannot be built or verified after a kickoff without weakening safety controls: `build_v5_intended_update_live_serving.py:245`, `package_v5_intended_update_live_run.py:179` and the independent verifier (`verify_v5_intended_update_live_serving.py:77-82`) all refuse once the first kickoff has passed, and the serving builder also requires a complete market for every game (Troy would have none) and a previous Production run for its schedule and market references.
2. The foundation refresh (Amendment 2) was missing from the plan and makes the work several sessions.
3. A Production rollback path back to the hold screen did not exist (Amendment 1).
The proposed remedy (an explicit, recorded `--display-only` mode in those three scripts, with the verifier independently checking the started-game set, and default behaviour unchanged) was put to the user and declined in favor of holding.

**Carry-forward for the Week 7 cutover:** Amendments 1 and 2 above describe real prerequisites that the cutover's pending Week 7 run will also meet (post-Week-5/6 Silver, the 07/08 refresh and Contract 09 live forecast as successor parents, a lock builder for the week, Week-5-specific hard-coding in the successor scripts). Treat them as inputs to that plan, not as approved work.
