# Weekly Ratings History Replay (Post-Week 0–2)

- **Status:** Draft
- **Created:** 2026-09-27
- **Planner:** Sol
- **Approval source:** Pending (user selected "replay + project history" direction in session; needs explicit approval of this contract)
- **Implementation log:** Pending
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

- [ ] Three verified historical generations projected to production; five
  distinct `current` cutoffs present.
- [ ] Six week-labeled tabs live, each serving its pinned generation with
  recorded per-tab spot values.
- [ ] Required validation passes (verifier receipts, DB counts, web gates,
  live readback).
- [ ] Documentation (`v5_status.md`, `weekly_pipeline.md`) and session log
  updated; plan status set to `Implemented`.

## Amendments

None.
