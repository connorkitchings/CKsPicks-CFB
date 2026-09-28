# Weekly Ratings History Replay (Post-Week 0–2)

- **Status:** Implemented 2026-09-28
- **Created:** 2026-09-27
- **Planner:** Sol
- **Approval source:** User explicitly authorized implementation of this exact contract path in session on 2026-09-27; Amendment 2 (all-five scope, W3/W4 verify-only) approved same day
- **Implementation log:** `session_logs/2026-09-27/18-ratings-history-task1-silver.md`, `session_logs/2026-09-27/19-amendment2-sealed-changes.md`, `session_logs/2026-09-27/20-ratings-history-execution.md`, `session_logs/2026-09-27/21-ratings-history-live-verification.md`
- **Commit policy:** Separate plan commit recommended; user controls staging and commits

## Goal

Serve a truthful per-week ratings timeline — Preseason, Post-Week 0, Post-Week 1,
Post-Week 2, Post-Week 3, Post-Week 4 — where every tab shows a genuinely
different frozen assessment. Today only two `current`-class generations exist
in production (cutoffs 2026-09-22 and 2026-09-27), so Post-Week 0/1/2 have no
frozen evidence and cannot be served. Success is three new independently
verified rating generations projected to production Neon, six week-labeled tabs
each pinned to its own immutable generation, and 138-team resolvability on
every tab.

## Current State

- Production `v5_rating_snapshots` (season 2026, 1296 rows, read 2026-09-27):
  `current` class exists only for two generations — cutoff `2026-09-22T14:58Z`
  (replay `possession-v1-rating-replay-20260922-fcaa571`, weeks 1–3 rows) and
  cutoff `2026-09-27T14:15Z` (replay `possession-v1-rating-replay-20260927-w4`,
  weeks 2–4 rows). No `current` rows for week 0; per-week team coverage is
  partial (e.g. week 4: 116/138 teams; gaps resolve via priors fallback).
- `pregame` snapshots cover weeks 0–4 but with partial team coverage
  (week 1: 86, week 2: 98, week 3: 114 teams) and per-game cutoffs — not usable
  as full-coverage post-week assessments. Preseason priors exist
  (`:preseason` snapshot IDs, full 138 coverage).
- Only two rating-replay runs and no post-W0/W1/W2 measurement runs exist in
  Preview R2. Measurements builder (`scripts/pipeline/build_rating_measurements.py`)
  is Preview-only and requires immutable parent refs plus `--as-of`.
- Replay runner (`scripts/research/run_data_first_possession_rating_replay.py`)
  is Preview-only; requires `--as-of`, `--measurement-manifest-uri`,
  `--historical-rating-manifest-uri`, recruiting/returning-production/coaches
  manifests, frozen config
  (`conf/research/data_first_football_v1/possession_rating_replay_2026_v1.yaml`),
  `--run-id`, and `--expected-code-sha`.
- Projection (`scripts/pipeline/publish_v5_ratings.py`) enforces frozen V5
  candidate + matching independent verifier + intact measurement/historical
  parents, inserts with `ON CONFLICT (snapshot_id) DO NOTHING` under the
  pipeline lease and `v5_release_policy`. Per-run `snapshot_id` prefixes make
  new generations collision-free against existing rows.
- `build_current_team_states` enforces a 6-hour evidence-availability buffer
  (`_AVAILABILITY_HOURS = 6`): a post-Week N cutoff must clear the last
  certified final of week N by 6h.
- Web (`web/src/lib/v5.ts`, commit `7ba4582`) serves a data-driven generation
  timeline with no-drift semantics: exact cutoff id → that generation's frozen
  rows; no source pin on historical entries. There are no week-labeled tabs.

## Proposed Approach

Replay the unchanged certified rating design at three earlier evidence cutoffs
(post-Week 0, post-Week 1, post-Week 2), verify each replay independently,
project all three generations to production Neon through the existing guarded
projection, then extend the web timeline with week labels pinned to exact
generation cutoffs — preserving the no-drift property. Reuse the certified
historical parents (historical rating, recruiting, returning production,
coaches) unchanged; only the 2026 measurements parent varies by cutoff.
No rating-design, config, schema, or V4 changes.

First-proposal cutoffs (Terra verifies each against certified finals + 6h
buffer before running): post-W0 `2026-09-01T00:00:00Z`, post-W1
`2026-09-08T00:00:00Z`, post-W2 `2026-09-15T00:00:00Z`. Post-W3 reuses the
09-22 generation; post-W4 reuses the 09-27 generation; no replay needed for
those two.

## Scope

### Included

- Measurements (Preview-only) at the three earlier cutoffs, reusing Repair v2
  lineage parents where `as_of`-compatible, rebuilding only what is missing.
- Three rating replays + independent verifications + Preview projections.
- Three production projections via the restricted pipeline role.
- Web week-labeled tabs pinned to exact generation cutoffs.
- Session log evidence per stage (replay receipts, verifier receipts,
  projection counts, live tab spot-checks).

### Excluded

- Any change to the rating design, config, priors, or bridge mathematics.
- Schema or migration changes (same `v5_rating_snapshots` table).
- V4 bundles, runs, or rollback paths.
- Backfilling or relabeling `pregame` snapshots as post-week assessments.
- Freeze/close/score flow changes; Week 5 operations continue independently.

## Affected Components and Contracts

- Research ops (Preview R2 only): `scripts/pipeline/build_rating_measurements.py`,
  `scripts/research/run_data_first_possession_rating_replay.py`,
  `scripts/research/verify_data_first_possession_rating_replay.py`.
- Production serving data: `v5_rating_snapshots` (append-only inserts, no
  migration) via `scripts/pipeline/publish_v5_ratings.py` and
  `zsh scripts/ops/with_production_pipeline_env.sh`.
- Web read path only: `web/src/lib/v5.ts` (`getRatingPeriods`,
  `getWeeklyRatings`), `web/src/app/ratings/page.tsx`,
  `web/src/lib/ratings.test.ts`.
- Docs: `docs/modeling/v5_status.md` (ratings lineage note),
  `docs/ops/weekly_pipeline.md` (projection cadence note),
  `docs/plans/index.md` (lifecycle entry).

## Implementation Tasks

### Task 1 — Resolve measurement parents per cutoff

**Files:**

- Preview R2 research prefix (new run IDs only; never overwrite)
- `session_logs/2026-09-27/` (evidence log)

**Changes:**

- For each of post-W0/W1/W2, confirm the certified Repair v2 outputs cover
  games through the cutoff; reuse existing immutable byplay/drives/games/
  outcomes/team-game/observations/snapshots/terminal refs where
  `as_of`-compatible, else rebuild the missing parents first.
- Record the exact parent URIs + raw SHA-256 per cutoff for the replay.

**Acceptance criteria:**

- Three complete, immutable measurement parent sets, one per cutoff, with
  recorded URIs and hashes. Any parent requiring new ingestion beyond Repair v2
  lineage stops the task for re-planning instead of improvising.

**Validation:**

- `build_rating_measurements.py` preflight (no apply) per cutoff; coverage
  report shows all completed games through cutoff included.

### Task 2 — Replay and independently verify three generations

**Files:**

- `scripts/research/run_data_first_possession_rating_replay.py` (unchanged;
  invoked with new `--run-id` / `--as-of` / `--measurement-manifest-uri`)
- `scripts/research/verify_data_first_possession_rating_replay.py` (unchanged)

**Changes:**

- Run three replays (suggested run IDs
  `possession-v1-rating-replay-2026w0`, `-2026w1`, `-2026w2`) with the frozen
  config, same historical parents, and the current committed code SHA.
- Verify each with the independent verifier; both manifests must reach
  `frozen` / `verified` states with matching SHA binding.

**Acceptance criteria:**

- Three `frozen` replay manifests + three `verified` verifier manifests with
  matching `retained_manifest_raw_sha256`. Failed verification blocks
  projection for that generation only.

**Validation:**

- Verifier receipts; manifest SHA cross-checks; row-count sanity (expect
  full-team `current` frame per generation, gaps documented).

### Task 3 — Project generations to Preview, then production

**Files:**

- `scripts/pipeline/publish_v5_ratings.py` (unchanged; invoked per manifest)

**Changes:**

- Dry-run (`--apply` omitted) per manifest in Preview; then `--apply` to
  Preview; verify 138-team resolvability per new cutoff via read-only queries.
- Production `--apply` through `with_production_pipeline_env.sh` (restricted
  `cks_prod_pipeline` role, active lease), one manifest at a time.

**Acceptance criteria:**

- Production holds five `current`-class generations (two existing + three
  new) with distinct cutoffs; each resolves to a full team list with the
  existing priors-fallback semantics; `ON CONFLICT DO NOTHING` changes zero
  existing rows (verify counts before/after).

**Validation:**

- Read-only production queries: distinct cutoffs = 5; per-cutoff team counts;
  spot-check a team whose rating must move monotonically-plausibly across
  generations (record values, do not assert direction).

### Task 4 — Week-labeled tabs pinned to exact generations

**Files:**

- `web/src/lib/v5.ts`
- `web/src/app/ratings/page.tsx`
- `web/src/lib/ratings.test.ts`

**Changes:**

- Extend the timeline so each entry carries a week label (Preseason, Post-Week
  0 … Post-Week 4) mapped to its generation's exact cutoff ISO id. Keep the
  no-drift rule: historical entries query by exact `cutoffUtc` equality with
  no source pin; default/`current` serves the newest generation.
- Preseason tab behavior unchanged.

**Acceptance criteria:**

- Six tabs render with week labels; each tab's label matches the generation it
  serves; selecting any tab shows values identical to the direct generation
  query; a future sixth generation appears without breaking existing tabs.

**Validation:**

- `web:lint`, `typecheck`, `build`, `test-publication` (extend
  `ratings.test.ts` with week-label → cutoff mapping cases); live `/ratings`
  spot-check recording one team's value per tab.

## Testing Strategy

- Research stages: preflight-then-apply per component with signed-manifest
  verification; no production writes until Preview evidence is reviewed.
- DB: read-only count/coverage queries before and after each projection;
  assert zero mutations to pre-existing rows.
- Web: unit tests for the label→cutoff map, publication-boundary tests,
  Next.js build, plus live readback of all six tabs.
- Regression: full Python suite (`-n 4 --dist loadfile`) and `make
  contracts-check` after any tracked change; `git diff --check`.

## Risks and Edge Cases

- Earlier-cutoff measurements may require parent rebuilds beyond Repair v2
  (scope growth) — stop and return for a revised contract rather than
  expanding scope inline.
- Partial team coverage in new generations must resolve to 138 teams via the
  existing priors fallback; if any tab cannot, label the gap explicitly
  rather than silently narrowing coverage.
- Production inserts are append-only and idempotent, but each needs its own
  pipeline-lease session; concurrent Week 5 freeze/close work must not share
  the lease window — coordinate sequencing in the session log.
- `snapshot_id` values are per-run prefixed; collisions with existing rows
  indicate a run-id reuse bug — abort projection if any conflict updates
  (none should; `DO NOTHING` must affect zero existing rows).

## Definition of Done

- [x] Three verified historical generations projected to production; five
  distinct `current` cutoffs present (09-03, 09-08, 09-13, 09-22, 09-27).
- [x] Six week-labeled tabs live, each serving its pinned generation with
  recorded per-tab spot values (Indiana overall: pre 1.20, W0 1.20, W1 1.67,
  W2 2.02, W3 2.03, W4 1.88; ranks 1/1/2/1/1/3).
- [x] Required validation passes (verifier receipts, DB counts, web gates,
  live readback, CI green on deploy commit).
- [x] Documentation (`v5_status.md` note below, session logs) updated; plan
  status set to `Implemented`.

Live verification (2026-09-28, production): all six tabs render 138 teams;
Post-Week 0 = 16 rated + 122 prior-backed teams; default view unchanged
(Post-Week 4); retired `?period=post-0` resolves to the Post-Week 0 tab.
W3/W4 repro digests bit-identical to certified generations (never projected).

## Amendments

### Amendment 1 — Reuse the w4 repair as the measurement parent (no new repairs)

**Reason:** Task 1 investigation found the sealed repair path pins exact W4
Silver versions in code (`SEASON_2026_SILVER_INPUTS`), and no live-state repair
runs exist at post-W0/W1/W2 cutoffs (only reconstructed Sep-9 runs, which must
not parent new generations). Changing the pin table would alter sealed
Contract 07 lineage beyond this contract's scope.

**Original approach:** Reuse Repair v2 lineage parents where `as_of`-compatible,
rebuilding only what is missing.

**Revised approach:** Use the immutable w4 repair
(`repair-2026-20260927T151800Z`) as the single measurement parent for all three
historical cutoffs. The measurements builder filters observations by `--as-of`,
the replay enforces the 6h availability buffer and rejects target-week/future
outcomes, and both stages carry independent verifiers. Historical rating and
preseason parents are reused unchanged from the w4 replay manifest.

**Impact:** No new ingestion, no sealed-code changes, no schema changes. Known
limitation recorded for the session log: repair-stage cleaning observed the
full W0–W4 corpus, so these generations are retrospective display history and
must never become forecasting parents. No task acceptance criteria change.

### Amendment 1a — INVALIDATED: `as_of` is metadata-only downstream of repair

**Reason:** Implementation investigation proved the premise false. No stage
filters by `as_of`: `_load_2026_frames` loads bundle Silver frames unfiltered
(season + completed only); `build_population` passes the repair population
through with pinned-count checks; `build_measurements` iterates the full
population; `build_live_replay` replays every population game with per-game
kickoff cutoffs and takes no `as_of` input. A w4-repair + earlier-`as_of`
build would compute all 215 games mislabeled with the earlier cutoff
(fail-closed only later, at projection via the 6h-buffer guard).

**Consequence:** Task 1 hits the contract's stop condition. The only valid
path is per-cutoff repairs from contemporary Silver inputs (validated batches
exist: 08-31, 09-06, 09-13), which requires constructing new
`season_2026_inputs` bundles AND changing the sealed
`SEASON_2026_SILVER_INPUTS` pin table — a Contract 07 lineage change beyond
Terra's amendment authority. Execution STOPS here pending a Sol amendment
decision. No R2 or Neon writes were made; all work above was read-only plus
one local dry-run preflight.

### Amendment 2 — Per-cutoff sealed parents, all-five scope (STATUS: APPROVED 2026-09-27)

**Reason:** Amendment 1a proved `as_of` cannot substitute for cutoff-correct
inputs. Contemporary validated Silver batches exist for the three missing
cutoffs. User explicitly approved rerunning all five weeks with the constraint
that certified Weeks 3–4 must be unreachable by the new work.

**Scope decision (user-approved): rerun all five; publish only the three new.
W3/W4 reruns are verification-only.** They reuse their exact original parents
and cutoff instants with current HEAD recorded:
- W3 rerun: repair `repair-2026-20260922T145500Z` chain +
  measurements `possession-v1-measurements-20260922-2026*`, `as_of`
  `2026-09-22T14:58:00Z`; compare canonical digests against replay
  `possession-v1-rating-replay-20260922-fcaa571`.
- W4 rerun: repair `repair-2026-20260927T151800Z` +
  measurements `possession-v1-measurements-20260927-w4`, `as_of`
  `2026-09-27T14:15:00Z`; compare against replay
  `possession-v1-rating-replay-20260927-w4`.
Compare gate is fail-closed across the whole contract: any W3/W4 digest
mismatch stops everything (non-determinism would poison trust in the new runs
too). On match, the reruns are recorded as reproducibility evidence and never
projected. The two rerun IDs are never passed to the projection script.
No seal changes are needed for the W3/W4 reruns.

**Sealed changes (all reviewed as one unit, committed before any `--apply`):**

1. `scripts/research/run_data_first_repair_v2.py` — extend
   `SEASON_2026_SILVER_INPUTS` from one pinned set to per-cutoff entries
   (`w0`, `w1`, `w2`, plus existing `w4`), each entry exact-pinning
   `version_id`/`content_sha`/`uri`/`schema_version` for `games`,
   `game_outcomes`, `byplay`, `team_games`. The runner selects the entry
   matching the run's declared cutoff; anything else fails closed as today.
   Approved values (Task 1 verified: 2026-only partitions, exact week sets,
   completed+scored finals matching schedule IDs, last-kickoff + 6h inside the
   batch `as_of`; full SHAs/URIs below, all `validated` in Preview catalog):
   - w0, generation `as_of` 2026-09-03T04:00:00Z (8 completed, week 0; last
     kickoff 08-30 02:00Z): games `9382b185`→ **corrected to `df578991`**
     (`8bab4bbf…613d2454`, `games_v2`,
     `lake/silver/dataset=games/version=df5789918474f3b33edbba81/data.parquet`),
     outcomes `68924633`→ **corrected to `8c7271c1`**
     (`6c6b5ff2…914ecb79`, `game_outcomes_v1`, `.../game_outcomes/version=8c7271c1d660490795c2595b/data.parquet`),
     byplay `42945ece`→ **corrected to `cf817b49`**
     (`acc24619…37d9e041`, `byplay_v1`, `.../byplay/version=cf817b49b4e88630ff3a62b7/data.parquet`),
     team_games `be569ae8`→ **corrected to `afa0b238`**
     (`b32db94b…7206e6d841`, `team_game_v1`, `.../reconciled_team_game/version=afa0b2381e2d7b991941b12f/data.parquet`).
     (The first-draft IDs were historical-season partitions sharing the same
     batch `as_of` — rejected in Task 1.)
   - w1, generation `as_of` 2026-09-08T15:35:00Z (51 completed, weeks 0–1;
     last kickoff 09-07 23:30Z): games `a64e5e6b`
     (`0fd6b4f2…6a6c44b50f8`, `games_v2`,
     `.../games/version=a64e5e6b1bed41d12caa4256/data.parquet`; earliest of
     three same-content 761-row builds), outcomes `eac8749a`
     (`50cae510…e7c44eeb2e0`, `game_outcomes_v1`,
     `.../game_outcomes/version=eac8749ab5e369166daf2fd3/data.parquet`;
     the earlier `6b7d011c` build carries 48 phantom completed rows for
     game_ids absent from the schedule — rejected), byplay `886a189e`
     (`fa8f6e1e…682cb03450`, `byplay_v1`,
     `.../byplay/version=886a189e17af627e0c09c2da/data.parquet`),
     team_games `6b0f9c71` (`ef173a5d…93a94e5c93`, `team_game_v1`,
     `.../reconciled_team_game/version=6b0f9c71df7ad3a64bdc302f/data.parquet`).
     (First-draft IDs were historical partitions — rejected.)
   - w2, generation `as_of` 2026-09-13T18:18:22Z (100 completed, weeks 0–2;
     last kickoff 09-13 03:59Z): games `931180a9`
     (`a461644e…f2e8008b`, `games_v2`,
     `.../games/version=931180a996b0f1aeabf5b734/data.parquet`), outcomes
     `d822f1fa` (`abc4f0ae…580f445b34977`, `game_outcomes_v1`,
     `.../game_outcomes/version=d822f1faac694b62064aff71/data.parquet`;
     the multi-season `4228e05e` is superseded for this purpose), byplay
     `447e11b7` (`be270589…e72f0ce9863a41`, `byplay_v1`,
     `.../byplay/version=447e11b7e8892104bb1c9b55/data.parquet`), team_games
     `69fd8ca5` (`f1f19b43…4714f01fe56dab8`, `team_game_v1`,
     `.../reconciled_team_game/version=69fd8ca511c464e20a70b153/data.parquet`).
     W2 row-count anomaly resolved: the batch is cumulative (100 × ~165
     plays/game); the larger rows first compared were other seasons'
     partitions.
   Drives versions ride with the same batches (W0 `60000707`, W1 `853949e9`,
   W2 `7ed98492`; week sets {0}, {0,1}, {0,1,2}; 2026-only) but are not
   repair-pin inputs.
2. New sealed measurement configs
   `conf/research/data_first_football_v1/possession_measurement_2026_w{0,1,2}_v1.yaml`
   — byte-identical design to `possession_measurement_2026_v1.yaml` except
   `expected_population` declares the Task-1-verified counts (w0: rows 8,
   forecast_eligible 8; w1: 51/51; w2: 100/100). Register all three in the
   measurements runner's `SEALED_CONFIGS`.
3. New `season_2026_inputs` bundles (R2 JSON, schema
   `data_first_2026_silver_inputs_v1`) per cutoff binding the refs above;
   `prepare_week_run` set to an explicit historical marker (it is carried,
   never validated). Bundle construction is data, not code.

**No change:** historical rating parents, priors, bridge, replay/verifier logic
(verified adaptable: manifest-relative checks only), projection path, web
serving semantics, V4, schema/migrations. Repair/measurements/replay
`--expected-code-sha` + clean-tree gates apply unchanged (user commits the
sealed changes first).

**Revised execution:** Task 1 (Silver verification) is COMPLETE — see session
log `18-ratings-history-task1-silver.md` for the evidence table. Remaining:
implement the sealed changes above, commit, then per cutoff (W0, W1, W2):
repair → verify v3 → measurements → verify → replay → verify → Preview
project → production project (Tasks 2–3 unchanged); W3/W4 reruns compare-only.
Task 4 unchanged.
