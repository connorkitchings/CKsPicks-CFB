# Matchup Data Layer v2: Everything the V5 Ratings Use, Per Team, Per Week

- **Status:** Approved
- **Created:** 2026-10-02
- **Planner:** Sol (planned and executed in one session at the user's direction)
- **Approval source:** User approved the plan in-session on 2026-10-02 after review, with four refinements (2026 before 2025; grouped matchup metrics; delta reporting before any republish; explicit read indexes) and these decisions: source = V5 rating artifacts; raw on matchup pages, adjusted in its own table; non-offense scoring as a descriptive stat; 2025 backfilled with full parity but decoupled and later; weekly refresh as one step after the rating projection and lineage-agnostic; align the Silver-based play filter to V5's and republish 2026 weeks 1-5; separate adjusted table.
- **Implementation log (2026-10-02):** Task 0 and Tasks 1-7 are on `dev` (one commit each). Task 8 Phase A ran on **Preview**: migration 0021 applied, matchup data published and verified (payload `a4a1062db790164850f31707350a93d1f2650363b47502ad3b67b99407571215`), Silver team stats republished with the V5 filter, a real Week 5 matchup page viewed. **Production and Phase B (2025) are pending.**
- **Commit policy:** Contract committed first on `dev`; then one commit per task. Preview before production; production writes only on the user's explicit go (owner credential for migrations, `scripts/ops/with_production_pipeline_env.sh` for writes). Merge `dev` into `main` only after Phase A is verified.
- **Amends:** [contract 10](../2026-10-01/10-authentic-team-stats-pipeline.md) (metric list and play filter).

## Goal

Make every weekly per-team quantity that the V5 ratings are built from available to matchup pages, with the matchup page showing **raw** values and opponent-adjusted values stored separately. Success: for each 2026 week 0-5, Neon holds (a) V5-definition raw metrics per team, (b) opponent-adjusted values per team, (c) a per-game measurement log, and (d) a per-team rating decomposition (prior vs per-game evidence, variance, exposure), all bound to the exact rating manifest the site serves and reconciled to it by hard gates. Week 5 matchup pages show the new raw metrics on Preview. 2025 follows as a decoupled Phase B.

## Current State

- Contract 10 stores 10 raw metrics from Silver play-by-play (`team_season_stats`, live in production). The V5 ratings use the `possession_*` family instead: `ppp` (true points per possession), `epa_per_possession`, `plays_per_possession`, `non_offense_points` and components. Strictly, the rating consumes the PPP observation, priors, a 6-hour availability rule, opponent context, the 2025 z-scale and K=8; the other measures are descriptive companions.
- Serving lineage: repaired "intended-update" run `intended-update-2026/runs/v5-intended-update-2026-ratings-v1/` (Neon `v5_rating_snapshots` source SHA `e80ae3473d88d0c458325c19343e7dae6447924d9abad29b15089bc19cacd26b`), measurement parent run `measurements/runs/possession-v1-measurements-20260927-w4/`. Artifacts are research artifacts with signed manifests, not catalog-registered, in the bucket shared by Preview and production.
- Neon holds only team-level offense/defense/overall rating and variance per generation. Not in Neon: measurements, adjusted values, per-game evidence, prior/evidence weights, exposure, non-offense points.
- `ops project-v5-ratings` calls `publish_v5_ratings.py` (replay manifests); the served intended-update ratings were projected by `publish_v5_intended_update_ratings.py`, which ops does not call. The Week 6+ rating lineage is not yet defined.

### Phase 0 findings (read-only, 2026-10-02)

| Check | Result |
|---|---|
| Rating manifest raw SHA | `e80ae3473d88d0c458325c19343e7dae6447924d9abad29b15089bc19cacd26b` equals the production site's selected source (`site_week_selections` -> `prediction_runs.rating_manifest_sha256`) |
| Measurement parent | raw SHA of `…20260927-w4/measurement-manifest.json` = `c43f6620…` = `parents.measurement_manifest_sha256`. The rating manifest holds only the SHA, so the publisher takes `--measurement-manifest-uri` |
| Measurement `output_refs` | `adjusted_history`, `coverage`, `observations`, `population`, `possessions`, `scoring_events`, `snapshots`, `terminal` |
| Rating `output_refs` | `current_roles`, `current_teams`, `pregame_roles`, `pregame_teams`, `priors`; `post_week_cutoffs` 0-4 = 2026-09-03T04:00Z, 09-08T15:35Z, 09-13T18:18:22Z, 09-22T14:58Z, 09-27T14:15Z |
| Observation vs Neon `games` (2026) | 215 games, 0 missing, 0 week mismatches |
| Team names | 9 artifact names differ from game names (Appalachian State, Connecticut, Hawai_i, Louisiana Monroe, Sam Houston State, San Jose State, Southern Mississippi, UMass, UT San Antonio). A blind inverse of `TEAM_LOGO_MAP` is **wrong** for two (Hawai_i has three keys; FIU maps to "Florida International", which is already the game name). Resolve against the season's actual game names: pick the map key that exists in them, else identity |
| `rating_mean = prior_contribution + Σ contribution` | holds on all 1,380 `current_roles` rows (4e-16) |
| `prior_weight = variance / prior_variance` | exact (0.0) |
| `1/variance = 1/prior_variance + usable_exposure/k` | holds (9e-16) |
| `usable_exposure = Σ exposure`; `source_game_ids` (a JSON string) = evidence game ids | exact; equal on every row |
| z-scale | `adjusted_z` is linear in `adjusted_ppp`: offense `1.055458·adj − 1.713376`, defense `−0.837421·adj + 2.216972` (residual 2e-15). Store center/spread/sign per role |
| Stitched post-week terminals | season-to-date adjusted PPP equals the exposure-weighted per-game evidence for as_of weeks 1, 2, 5 but **not** weeks 3 and 4 (the older runs used different game sets). Do not stitch runs |
| Recompute with the existing adjuster | `possession_measurements._adjust` over the w4 observations (availability = kickoff + 6h <= `post_week_cutoffs[N-1]`, `week < N`) reproduces the rating evidence for **all** weeks 1-5 (max error 8.9e-16; 30, 180, 259, 271, 276 team-roles). This is the chosen method and a verification gate |
| 2025 population | r9 observations: 934 games, 230 teams (FCS included), weeks 1-16, 29,888 rows (906 missing), all `historically_reconstructed`. Neon 2025 `games`: 794; all 794 are in the observations, 0 week mismatches; 140 observation-only games involve FCS opponents |
| 2025 rating states | r9cert `possession_rating_state` for `ppp__rho_0_60__exposure` (selected): 3,736 rows, 230 teams, weeks 1-16, 934 games; `team_states` 1,868 rows. No per-game evidence for historical lineages. `adjusted_history` is 26M rows, so 2025 adjusted values are recomputed with `_adjust` rather than read |

Decisions that follow: stats aggregate FBS-vs-FBS games only (the 2026 population and Neon `games` agree, and it matches the Silver-based table); the game log keeps every game with `opponent_fbs` flagged; 2025 per-game evidence is omitted and labeled.

## Proposed Approach

Read the V5 rating artifacts (pinned by manifest SHA, verified by checksum and the independent verifier) with one lineage-agnostic publisher; build five new tables; recompute weekly adjusted values with the existing adjuster; reconcile everything to the served ratings with hard gates; expose only raw metrics to matchup pages. Details and rationale were reviewed with the user; the schema and tasks below are the decision-complete form.

## Scope

### Included
- Migration 0021 and five tables (below); a publisher and a read-only verifier; shared helper exposure in the ratings code; Silver play-filter alignment and republish of 2026 weeks 1-5 with delta reporting; web read layer and grouped matchup metrics (raw only); operator step; Phase A (2026) backfill on Preview then production; Phase B (2025) backfill afterwards.

### Excluded
- Preseason-prior input data (recruiting, returning production, coaching); the model's non-offense bridge offset; displaying adjusted values, game log, components or rating history on pages; opening 2025 matchup pages (public scope stays 2026); changing the V5 model or any artifact.

## Affected Components and Contracts

- `contracts/migrations/0021_matchup_data_v2.sql`, `contracts/schema.sql`, `contracts/schema.ts`, byte-identical `web/src/lib/schema.ts`, `contracts/validation.py`.
- `src/cks_picks_cfb/ratings/possession_measurements.py`, `possession_intended_update.py` (expose helpers, no behavior change); `src/cks_picks_cfb/data/matchup_data.py` (new); `src/cks_picks_cfb/data/team_stats.py`.
- `scripts/pipeline/publish_matchup_data.py`, `verify_matchup_data.py` (new); `publish_team_stats.py` (`--diff`).
- `src/cks_picks_cfb/ops/__main__.py` (new `publish-matchup-data` command); `docs/ops/*`, `Makefile`.
- `web/src/lib/queries.ts`, `team-stats.ts`, `matchup.ts`, `web/src/components/matchup/UnitMatchupTable.tsx`.

## Schema (migration 0021)

Every table: `GRANT SELECT TO cks_web; GRANT SELECT, INSERT, UPDATE TO cks_pipeline`. Read indexes: `team_possession_stats (season, as_of_week, team)`; `team_possession_adjusted (season, as_of_week, team)`; `team_game_measurements (season, game_id, team)` and `(season, team, week)`; `team_rating_components (v5_snapshot_id)` and `(season, as_of_week, team)`.

| Table | Grain | Content |
|---|---|---|
| `matchup_data_publications` | publication_id | season, lineage, rating manifest SHA+URI, measurement manifest SHA+URI, observations records SHA, as_of_weeks, rating scale JSONB, row counts, `payload_sha256`, code_sha, environment, published_at; UNIQUE (season, lineage, rating SHA, payload SHA) |
| `team_game_measurements` | season, game_id, team, unit_role, measurement_id | week, season_type, kickoff_utc, opponent, side, numerator, denominator, raw_value, usable_exposure, exposure_unit, coverage_status, missing_reason, quality_flags, timing_class, `rating_usable`, `opponent_fbs`, manifest SHA, source_versions. No FK to `games` |
| `team_possession_stats` (raw) | season, as_of_week, team, role, metric | metrics `ppp`, `epa_per_possession`, `epa_per_play`, `plays_per_possession`, `possessions_per_game`, `non_offense_points_per_game` (regulation); value, numerator, denominator, n, games, games_excluded, excluded JSONB, rank, cohort_size, as_of_cutoff, manifest SHAs |
| `team_possession_adjusted` (adjusted) | season, as_of_week, team, role, measurement_id (`ppp`, `epa_per_possession`) | raw_value, adjusted_value, `opponent_adjustment`, adjusted_rank, cohort_size, primary_exposure, games, adjustment_method (`measurement_iterative_4pass_v1`), manifest SHAs |
| `team_rating_components` | component_id = `{snapshot_id}:{unit_role}` | `v5_snapshot_id` FK to `v5_rating_snapshots` (null for 2025), lineage (`intended_update`/`historical_replay`), candidate_id, snapshot_class, week/as_of_week/game_id/cutoff, `rating_team` + `team`, rating_mean/variance, prior_mean/variance, prior_weight, prior_contribution, evidence_weight, process_variance, k, usable_exposure, completed_games, `evidence` JSONB, `excluded_observations` JSONB, prior_detail, fallback_reason. Append-only per manifest |

## Implementation Tasks

### Task 1: Migration 0021
**Files:** `contracts/migrations/0021_matchup_data_v2.sql`, `contracts/schema.sql`, `contracts/schema.ts`, `web/src/lib/schema.ts`, `tests/test_migration_integration.py`.
**Acceptance:** applies cleanly after 0020; idempotent re-apply returns nothing; CHECKs (roles, measurement ids, lineage) reject bad values; FK to `v5_rating_snapshots` enforced; grants present; `contracts/validation.py` passes.
**Validation:** migration test against a disposable Postgres; `make contracts-check`.

### Task 2: Expose shared helpers (no behavior change)
**Files:** `ratings/possession_measurements.py` (`_adjust` -> `adjust_possession_history`, `_eligible_play` -> `eligible_possession_play`), `ratings/possession_intended_update.py` (usable-row predicate from `_source_rows`), `ratings/possession_live_replay.py` (`_historical_scale`). Keep the old private names as aliases.
**Acceptance:** all existing ratings tests pass unchanged.

### Task 3: Pure builders
**Files:** `src/cks_picks_cfb/data/matchup_data.py`, `tests/test_matchup_data.py`.
**Changes:** verified loading (`audit/corpus.py` `read_any`/`concat_all`; `verify_signed_payload`; child-checksum pattern of `publish_v5_intended_update_ratings.py`); builders per table; name resolution against the season's game names; JSON parse of `source_game_ids` and `explanation`; `to_upsert_records`-style cleaner.
**Acceptance:** fixtures shaped from the real columns cover ratio-of-sums, usable vs excluded (an Ohio-State-style offense row with an unusable observation), the nine legacy names including Hawai_i and Florida International, cutoff filtering, adjuster equality with the measurement run, decomposition sums.

### Task 4: Publisher and verifier
**Files:** `scripts/pipeline/publish_matchup_data.py`, `scripts/pipeline/verify_matchup_data.py`, `tests/test_publish_matchup_data.py`.
**Changes:** args `--season`, `--lineage`, `--rating-manifest-uri`, `--measurement-manifest-uri`, `--weeks`, `--environment`, `--dry-run/--apply`, `--expect-payload-sha`. Checks in order: rating manifest schema/frozen/verifier SHA; measurement parent SHA; database environment and active pipeline lease; selected-source binding; required `v5_snapshot_id`s exist; stale-key check (pipeline role cannot DELETE); one transaction; receipt row. Storage is always the Preview-env storage.
**Acceptance:** fails on wrong SHA, unverified manifest, selected-source mismatch, missing snapshot id, stale key; dry run writes nothing; re-run is a no-op; a component conflict raises.

### Task 5: Align the Silver play filter and republish with deltas
**Files:** `src/cks_picks_cfb/data/team_stats.py`, `tests/test_team_stats.py`, `scripts/pipeline/publish_team_stats.py`.
**Changes:** use `eligible_possession_play`; fix the docstring; add `--diff` printing per-metric deltas (old vs new value, rank shifts, top movers, rows changed) from the published rows before any write.
**Acceptance:** Preview delta report reviewed and rank shifts small before production; production republish only on the user's go, in lockstep with migration 0021.

### Task 6: Web read layer
**Files:** `web/src/lib/queries.ts`, `team-stats.ts`, `matchup.ts`, `UnitMatchupTable.tsx`, fixtures, tests.
**Changes:** guarded `hasTeamPossessionStatsTable`/`getTeamPossessionStats` selecting **raw columns only** from `team_possession_stats`; merge into matchup rows; `UNIT_METRICS` grouped into three sections: *Core possession efficiency* (PPP, EPA/possession, EPA/play, plays/possession, non-offense pts), *Situational / down and distance* (success rate, explosive plays, 3rd/4th down, early-down EPA, pass/rush EPA), *Drive context* (scoring opps/drive, pts/scoring opp, average start). No readers for the adjusted table, game log or components.
**Acceptance:** a test proves the adjusted table is never queried; phone-width e2e passes; Playwright, lint, typecheck, `test:publication`, fixture build pass.

### Task 7: Weekly operator step
**Files:** `src/cks_picks_cfb/ops/__main__.py`, `docs/ops/weekly_pipeline.md`, `docs/ops/v5_weekly_operator.md`, `Makefile`.
**Changes:** `publish-matchup-data` beside `project-v5-ratings`, taking the same `--rating-manifest-uri`; resumable. Fix or document that `project-v5-ratings` does not dispatch the intended-update manifest.

### Task 8: Backfills (Preview first)
**Phase A (2026, ships first):** weeks 0-5 from the intended-update lineage and w4 observations (stats for weeks 1-5; components for 0-5); Preview, verify, production (owner-credential migration 0021, publish with `--expect-payload-sha`, verifier, Task 5 republish in lockstep). Complete when Week 5 matchup pages show the new data on Preview.
**Phase B (2025, after Phase A):** weeks 1-16 from r9 observations and r9cert states for `ppp__rho_0_60__exposure` (`lineage='historical_replay'`); FBS-vs-FBS aggregation, full game log with `opponent_fbs`; adjusted values recomputed with the adjuster; aggregate decomposition only. Data only.

### Task 9: Close-out
Contract log, `docs/status.md`, decision log, session log; amend contract 10's metric list and filter; mkdocs strict.

## Testing Strategy

Unit and fixture tests as listed per task; migration round trip; full Python suite with `-W error`; web lint/typecheck/unit/build/Playwright; Preview data runs with the verifier; a real Week 5 matchup page viewed (Ohio State at Iowa; San José State at Hawai'i).

### Verification gates (`verify_matchup_data.py`; any failure aborts a write)
1. Component `rating_mean`/`rating_variance` equal `v5_rating_snapshots` values joined on `v5_snapshot_id` (1e-12).
2. `prior_contribution + Σ contribution = rating_mean` (1e-9); `prior_weight = var/prior_var`; `1/var = 1/prior_var + exposure/k`; evidence game ids equal parsed `source_game_ids`.
3. Evidence matches the game log; evidence + excluded games = PPP observations in the window.
4. Raw stats: `games` = `len(evidence)` for PPP at current N; value = Σ numerator / Σ denominator.
5. Recomputed adjusted values equal the exposure-weighted per-game evidence (weeks 1-5) and the w4 terminal at week 5.
6. Silver comparison: per-team `games` equal `team_season_stats.games` (gated); V5 EPA/play vs Silver-weighted EPA Spearman >= 0.95 and PPP vs `scoring_opp_rate x pts_per_scoring_opp` >= 0.85 (reported).
7. Non-offense: a team's offense value equals the opponent's defense row per game; offensive + non-offense points vs final score reported for regulation games.
8. Every stored `team` exists in that season's `games`.

## Risks and Edge Cases

- Week 6+ rating lineage is unsettled; the publisher detects the manifest type; per-game evidence exists only for the intended-update lineage.
- 2025 parity is aggregate-level (no per-game evidence, different accepted lineage, reconstructed timing, FCS games in the log).
- Non-offense points come from the ledger's substring heuristic and exclude overtime; ranks have heavy ties; label "regulation non-offense points".
- Task 5 changes published matchup numbers slightly; production republish needs the user's go.
- Components multiply per weekly manifest (append-only); pruning of non-selected manifests is a later owner-role task.
- Artifacts are immutable but unregistered; a missing or changed object fails closed.
- Rollback: drop the five tables (web guards fall back to nothing), revert commits; `team_season_stats` is untouched except the Task 5 republish (reversible by republishing).

## Definition of Done

- [ ] Tasks 1-9 complete; gates pass on Preview and production for 2026 weeks 0-5.
- [ ] Week 5 matchup page on Preview shows the grouped raw metrics, viewed.
- [ ] 2025 backfill (Phase B) complete or explicitly deferred in the log.
- [ ] Documentation and session log updated; plan status set to `Implemented`.

## Amendments and Blockers

- 2026-10-02: Phase 0 recorded above. No blockers.
- 2026-10-02, Phase A on Preview (the user ran no production step): migration 0021 applied with the migrator role; `publish_matchup_data.py` dry run passed all 11 gates, published 6,880 game-log rows, 6,276 raw stats rows, 2,062 adjusted rows and 2,740 components (one receipt; a re-run changed nothing); `verify_matchup_data.py` reports 0 rows differing from the artifacts. Spot checks: Ohio State's Week 5 offense PPP 3.786 raw over 3 games (1 excluded) and 3.674 adjusted, equal to the rating evidence; the nine legacy-named teams are stored under game names (no legacy spellings in the stats tables).
- Task 5 finding: the old Silver play filter kept overtime drives (they start at the opponent's 25) and "End of Game" placeholder plays. The V5 filter drops 218 plays and 21 drives across weeks 1-5, which mainly moves *average starting field position* for teams with an overtime game (for example Purdue's defense, Week 3: rank 110 to 18); other metrics move little (1,955 of 10,460 rows changed; mean absolute value changes below 0.01 except field position). The delta report was reviewed before the Preview republish; the production republish waits for the user's go, in lockstep with migration 0021.
- Web: 14 metrics in three sections (*Core possession efficiency*, *Situational / down and distance*, *Drive context*); the matchup query reads `team_possession_stats` only (a test fails if the adjusted table is referenced). `possessions_per_game` is stored but not displayed (pace has no better/worse direction).
- Not done here: `ops project-v5-ratings` still does not dispatch the intended-update manifest (documented in the runbook); Phase B (2025, historical replay lineage) and all production steps.
