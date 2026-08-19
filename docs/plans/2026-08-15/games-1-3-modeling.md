# Games 1–3 Modeling and Branch Consolidation

- **Status:** Superseded (2026-08-18) — the early-route methodology was redesigned and executed by
  [`docs/plans/2026-08-17/early-season-v4-modeling.md`](../2026-08-17/early-season-v4-modeling.md)
  (V4) under the
  [Week 0 launch contract](../2026-08-18/week0-launch-execution.md). This plan's
  deliverables (games-ordinal routing, timestamped market adapter, prediction-only
  promotion basis) shipped and were carried forward into V4/V5 lineage.
- **Created:** 2026-08-15
- **Planner:** Sol
- **Approval source:** User authorized implementation in this task on 2026-08-15.
- **Implementation log:** `session_logs/2026-08-15/05-games-1-3-modeling.md`
- **Commit policy:** Separate plan commit; implementation commits remain user-controlled.

## Goal

Consolidate the linear branch stack into `main`, then develop an early-season
model for each team’s first, second, and third games. The model must shrink
current-season metrics toward prior information independently for each team,
compare direct spread/total predictions against home/away-points-derived
predictions, and require both predictive and betting evidence before promotion.

## Current State

- The local history is linear: `main` → `codex/2026-ops-cleanup` →
  `feat/web-presentation`; the latter two are ahead of `main` by 17 and 18
  commits respectively. There is no `dev` branch.
- `artifacts/preview/` is an untracked, user-owned 48 MB directory and must be
  preserved.
- Existing routing uses completed-game labels (`preseason`, `one_game`,
  `two_games`, `three_games`, `established`), which makes the first scheduled
  game appear as a preseason route.
- Existing OOF candidates show unstable standalone one-game models and better
  performance from prior/current blends in several later early-season cells.
  All historical market-line values are currently missing because untimestamped
  legacy CFBD exports are correctly quarantined.

## Proposed Approach

Use a canonical ordinal route contract: a team’s first, second, and third
scheduled games map to `game_1`, `game_2`, and `game_3`; a matchup is
`established` only when both teams are entering game four or later. Retain
legacy parsing and stored rows, but publish new eight-cell model bundles.

Backfill timestamped historical NCAAF quotes through The Odds API, using the
last pre-kick snapshot and the best executable quote for the model-selected
direction. Market data is evaluation-only. Build team-specific empirical-Bayes
features, conduct the frozen candidate tournament, and promote only candidates
that pass both predictive and betting gates.

## Scope

### Included

- Local branch consolidation and creation of `codex/games-1-3-modeling`.
- Additive ordinal routing, bundle/schema compatibility, web labels, and
  Preview-only historical odds ingestion/grading.
- Team-specific shrinkage features and the direct-target versus points-derived
  model tournament for `game_1` through `game_3`.
- Nested temporal threshold selection, reproducible promotion reports, and
  Preview-only model refit/readiness.

### Excluded

- Retournamenting the existing established model.
- Production migrations, publication, Pick'em submission, or enabling
  high-confidence presentation without separate approval.
- Using bookmaker data as an input feature or reviving untimestamped legacy
  lines for selection, ROI, or grading.

## Affected Components and Contracts

- Point-in-time feature routing, early-season candidate generation, promotion,
  bundle loading/refit, and weekly prediction publication.
- Canonical data contracts for timestamped market quotes and prediction route
  values; legacy route values remain readable.
- SQL/TypeScript/web route representations and migration coverage.
- A new The Odds API source adapter, immutable captures, and quote-selection
  evaluation contract.

## Implementation Tasks

### Task 1 — Consolidate branch baseline

**Changes:**

- Preserve `artifacts/preview/` unchanged.
- Fetch `origin`, verify remote `main` is an ancestor of the consolidated tip,
  and stop on divergence.
- Fast-forward `main` through the current web tip, validate the combined
  revision, and create `codex/games-1-3-modeling` from it.
- After user-controlled push confirmation, remove merged local feature branches
  and the remote `codex/2026-ops-cleanup`; do not create `dev`.

**Acceptance criteria:**

- The new modeling branch is based on the consolidated local `main`.
- Preview artifacts remain unmodified and unstaged.

### Task 2 — Add canonical game-ordinal routing

**Changes:**

- Compute `game_ordinal = completed_game_count + 1` independently by team.
- Route a matchup by its least-experienced team: `game_1`, `game_2`, `game_3`,
  otherwise `established` when both teams enter game four or later.
- Add migration/schema/web support for the new names while retaining legacy
  values and mapping legacy bundle/row values on read.
- Publish a model-bundle revision with two targets × four canonical routes;
  retain legacy bundle loading for historic runs.

**Acceptance criteria:**

- Byes, unequal team game counts, cancelled games, and historic predictions
  route correctly without relabeling stored data.

### Task 3 — Ingest timestamped historical odds

**Changes:**

- Add `THE_ODDS_API_KEY` configuration and a quota-aware, resumable The Odds
  API adapter for 2021–2025 NCAAF spreads and totals.
- Query at `kickoff - 1 second`, cache one immutable response per kickoff slot,
  record provider timestamps/prices, and reject updates at or after kickoff.
- Match events through normalized teams and kickoff tolerance; keep unmatched
  or ambiguous games explicitly ungraded.
- Decide direction against the median market line, then choose the best
  available executable quote for that direction: best line, then best price,
  then lexical bookmaker key.
- Provide a dry-run request/credit estimate before any paid backfill and require
  explicit user approval for the paid calls.

**Acceptance criteria:**

- Quotes are immutable, timestamped, pre-kick, traceable to source captures,
  and unavailable to model features.

### Task 4 — Train and evaluate first-three-game candidates

**Changes:**

- Construct team-side empirical-Bayes features with frozen prior-strength grids:
  plays `{50,100,200,400}`, drives `{5,10,20,40}`, games `{1,2,4,8}`.
- Preserve raw prior/current values, exposures, missingness, shrinkage weights,
  and opponent-adjustment lineage.
- Compare direct Ridge, direct CatBoost, points-derived Ridge, and
  points-derived CatBoost per target and ordinal; retain the existing blend as
  frozen baseline and the established model as current-evidence anchor.
- Select design only from 2022–2024 temporal OOF rows; keep 2025 sealed until
  the design SHA is frozen; refit unchanged design on 2021–2025.

**Acceptance criteria:**

- No 2020 label/feature lineage, no future data leakage, and target-specific
  candidates can independently win each ordinal route.

### Task 5 — Grade and promote with executable quotes

**Changes:**

- Grade at actual quoted prices, count pushes as zero-return wagers, and retain
  complete quote provenance.
- Search candidate-specific thresholds from `0.0` to `10.0` in `0.5`-point
  increments. For 2023, learn from 2022; for 2024, learn from 2022–2023; freeze
  2025/production thresholds from all selection years.
- Require at least 30 tuning bets; tie-break threshold choices by net units,
  volume, then lower threshold.
- Promote only with 0.10 MAE lift and positive paired 95% bootstrap interval,
  acceptable RMSE/calibration, 100 cross-fitted bets, positive ROI with a
  positive stratified-bootstrap lower bound, nonnegative 2023/2024 net units,
  acceptable drawdown, and no greater than 10% locked-2025 regression or
  negative locked-year ROI.

**Acceptance criteria:**

- Failed cells remain visible but display-only; no gate may be represented as
  passed without authentic quote evidence.

## Testing Strategy

- Unit-test ordinal routing, asymmetric counts, cancellations, feature
  shrinkage, legacy bundle compatibility, and nonnegative points derivation.
- Test odds cutoff/reconciliation/caching/quota behavior, best-price selection,
  spread and total signs, pushes, and market-feature exclusion.
- Test sealed 2025 access, nested thresholds, bootstrap/promotion gates, and
  deterministic reruns.
- Cover database migration from current schema, web labels, full Preview
  prediction/grading, and immutable lineage audits.
- Run full Python tests, Ruff check and targeted format checks, contracts and
  migration integration checks, MkDocs, web lint/typecheck/publication/build,
  and `git diff --check`.

## Risks and Edge Cases

- The Odds API is paid and quota-metered; implementation must provide a
  read-only estimate before issuing paid requests.
- Best-available pricing intentionally models active line shopping; quoted
  price and bookmaker must therefore be persisted with each graded wager.
- Historical coverage may leave underpowered routes. A route that cannot clear
  all gates stays display-only rather than forcing promotion.
- 2026 talent availability remains incomplete; missing inputs require explicit
  fallback/missingness, never inferred values.

## Definition of Done

- [x] Branch baseline is consolidated locally and the new modeling branch exists.
- [x] Canonical ordinal routing and legacy compatibility are implemented.
- [x] Timestamped market adapter and grading contract are implemented and tested.
- [x] Candidate tournament, thresholding, and promotion gates are reproducible.
- [x] Preview-only refit/readiness is validated or the precise external blocker is documented.
- [x] All required validation passes.
- [x] Documentation and implementation session log are updated.
- [x] Plan status is updated to `Superseded` (2026-08-18): work concluded under
  the V4 plan rather than reaching `Implemented` here; its V3 bundle
  (`week0-2026-games-ordinal-v3-20260816-r2`) served as the tournament baseline
  lineage for V4.

## Amendments

### 2026-08-16 — Prediction-only promotion authorized

The user explicitly authorized Games 1–3 selection, refitting, and 2026
activation using historical game results alone. Historical odds remain an
optional, decoupled module: it is neither an input feature nor a readiness,
promotion, or refit dependency. Result-only promotion uses 2022–2024 OOF MAE,
RMSE, bias, season stability, and paired bootstrap evidence; 2025 remains the
sealed anti-regression test. Bundle manifests must state
`selection_basis=predictive_results_only` and
`betting_validation_status=not_evaluated`.

### 2026-08-15 — External historical-odds execution deferred

The code includes a no-spend estimate command and an explicit The Odds API
adapter, but does not issue paid provider requests. Any future historical
betting backtest requires an authorized `THE_ODDS_API_KEY` and separate user
approval after reviewing the estimate. This does not block prediction-only
selection or refitting.

### 2026-08-16 — Sealed Preview tournament workflow

The initial single-pass candidate command was amended before Preview execution:
selection now emits only 2022–2024 OOF rows and freezes an immutable design
report before 2025 can be generated. The guarded 2025 baseline requires that
report SHA, and locked validation produces a separate final routing report
with route-local baseline fallback. The tournament evaluates the full frozen
shrinkage grid with Ridge, then CatBoost only on Ridge-selected designs; the
canonical blend is selection-only and uses a prior-only Game 1 invariant.

The v3 Preview bundle refits baseline, blend, direct, and points-derived
routes according to that final report. It compatibility-refits established
Ridge routes without retournamenting them. Preview comparison is private: it
does not change the current v2 Preview run, champion configuration, or public
publication state.

### 2026-08-16 — Preview execution result and readiness blocker

The result-only Preview tournament completed with frozen selection design SHA
`8a80aac1b62327c6a5af1437e99878ee4c7c816fdced531dca7cc666ea7e343c`.
Locked 2025 preserved the selected routes: spread Game 1 uses points-derived
CatBoost; spread Games 2–3 and total Game 1 use the prior-only baseline; total
Games 2–3 use the frozen blend. The complete private v3 bundle is
`week0-2026-games-ordinal-v3-20260816-r2`.

Private prediction generation against the active eight-game Week 0 input
snapshot passed. The v2-v3 comparison found two spread-lean and eight
total-lean changes. Weekly preflight remains blocked by pre-existing Preview
operational state: the isolated Neon branch lacks the pipeline/publication
tables and `current_week.active_run_id`, and the 2026-08-16 preseason snapshot
is incomplete. The v2 Preview run and public market-only configuration remain
unchanged pending that separate readiness repair.
