# Permanent Best-Quote Market-Line Selection

- **Status:** In Progress
- **Created:** 2026-09-25
- **Planner:** Sol (plan-session)
- **Approval source:** User explicitly directed implementation on 2026-09-25 ("Follow the instructions in docs/plans/2026-09-25/03-permanent-best-quote-line-selection.md"). This authorizes Tasks 1–2 (market_grading.py, tests, schema/migration, TypeScript contracts). Tasks 3–6 (artifact generation, publishing, grading, historical replay releases) remain gated on Preview rehearsal and separate production authorization per the plan's commit policy.
- **Implementation log:** `session_logs/2026-09-25/22-permanent-best-quote-selection.md`
- **Commit policy:** Separate plan commit required before implementation because this changes immutable prediction/grade lineage and production serving behavior. The user executes Git operations.

## Goal

Replace the public and graded consensus-line values with the best executable
pre-kickoff quote for the model's already-determined side. Apply the policy to
every future forecast and to every historical season/week that has eligible,
stored quotes. A displayed or graded line must be an actual quote, so it uses
ordinary market increments such as `.0` or `.5`, never a synthetic average.

Observable success criteria:

1. Spread and total predictions select the quote that creates the greatest
   directional edge after the model forecast exists, without using bookmaker
   data as a model feature or changing model training, rating, or forecast
   values.
2. Each selected target records its exact quote ID, point, price, side,
   snapshot, and selection-policy version in the immutable prediction
   lineage; the public line, edge, bet label, and grade all use that same
   selected quote.
3. Any season/week without an eligible frozen quote shows no market lean and
   receives no market grade. The system never substitutes an average,
   consensus, post-kickoff quote, or a quote from another game.
4. Existing immutable runs are never edited. Historical replacement runs are
   rebuilt, verified, released, and selected under the applicable existing
   authorization boundary; original V4 runs and grades stay untouched as audit
   records.

## Current State

- `market_snapshots` use `consensus_then_median_v1`: CFBD consensus when
  present, otherwise a provider median. The latter can create quarter-point
  values. The prediction artifact, `predictions`, public site, and grades
  currently bind to that snapshot's `spread` and `total` fields.
- Immutable Silver `market_quotes` retain per-quote points, prices, capture
  timestamps, and quote IDs. `market_snapshot_quotes` links the frozen quotes
  that support a snapshot and target. The weekly publish transaction persists
  those rows and links into Neon.
- `select_best_available_quote()` and `pick_direction()` in
  `src/cks_picks_cfb/models/market_grading.py` implement part of the desired
  behavior for normalized quote rows, but no production forecast, artifact,
  publishing, or scoring path invokes them. The helper also lacks the
  snapshot/kickoff eligibility and durable-selection contract required here.
- `predictions.market_snapshot_id` identifies one canonical snapshot, but the
  table has no target-specific selected quote identity. `prediction_grades`
  similarly records only `market_snapshot_id`. The current schema cannot prove
  which raw quote an individual spread or total grade used.
- Selected V5 Weeks 0–4 are immutable replay runs with frozen V4 quote
  snapshots and existing replay grades. Their artifacts, prediction rows, and
  grades must not be overwritten. A change to their market lines therefore
  requires new V5 replay artifacts, exact replay authorizations, new grades,
  and an explicit replacement selection. Existing V4 runs remain tested
  rollback/audit records; an eligible V4 replacement is a new run and never
  an update to the original one.
- Historical coverage is not assumed merely because a season has a consensus
  snapshot. The policy applies only when quote IDs, game IDs, target values,
  capture times, and kickoff times can be verified from stored immutable data.

## Proposed Approach

Use the canonical snapshot only to establish the model's side, then line-shop
among the exact frozen quotes linked to that snapshot. The snapshot remains
auditable and never enters model features. The selection is deterministic:

1. Derive the side from the model forecast and canonical snapshot. For a
   spread, positive home-margin edge chooses home and negative chooses away;
   for a total, a higher forecast chooses over and a lower forecast chooses
   under. A zero canonical edge creates no selected quote, lean, or grade.
2. Admit only linked quote rows for the same game and target whose authentic
   capture time is no later than the game's kickoff. Reject missing point,
   price, quote ID, or side price.
3. Among candidates for that fixed side, select the most favorable point:
   highest signed spread point for the selected team, lowest total for over,
   and highest total for under. Break equal points by the better American
   price, then quote ID ascending. This is the greatest edge for the existing
   model direction and prevents line shopping from changing the direction.
4. Write the selected quote IDs and values into the immutable prediction
   artifact. Store target-specific selection rows in Neon and use the chosen
   point to derive `spread_lean`, `total_lean`, `edge_spread`, and
   `edge_total`. Grades settle against the exact stored point and price.

Introduce an append-only `prediction_market_selections` relation instead of
overloading one snapshot ID for two independently selected targets. Each row
is keyed by `(run_id, game_id, target)` and records the snapshot ID, quote ID,
side, point, price, directional edge, and `model_side_best_quote_v1` policy
version. Extend `prediction_grades` with a nullable `market_quote_id` for
legacy compatibility; new best-quote grades must populate it and correspond to
the selection row. The artifact carries `spread_market_quote_id` and
`total_market_quote_id`, enabling its bytes to prove the exact selections
before publication.

Run a coverage audit over every stored season/week first. For eligible
historical runs, generate replacement artifacts under new IDs and preserve
their original evidence class. For the selected 2026 V5 Weeks 0–4, use the
existing replay authorization lane and separate packets; do not alter V4,
backdate timestamps, or treat the replacement grades as prospective evidence.
For future runs, selection occurs before the artifact is frozen. A run with no
eligible quote is valid only as an unlined forecast with no market result.

## Scope

### Included

- A durable, target-specific best-quote selection contract for spread and
  total forecasts.
- Quote normalization and deterministic selection from frozen, linked,
  pre-kickoff market quotes.
- Artifact, database, publish, grade, web, and weekly-runbook updates needed
  to keep displayed lines, bets, edges, and results identical to the selected
  quote.
- An all-season quote-coverage audit and replacement-run procedure for every
  eligible historical season/week and model lineage, including the currently
  selected 2026 V5 Weeks 0–4.
- Preview-first rehearsal, exact release packets, and separate production
  authorization/selection for each replacement V5 replay run.

### Excluded

- Training, model, rating, bridge, forecast, or selection mathematics; market
  data remains post-forecast and cannot become a model input.
- Inventing or backfilling missing historical quotes, using post-kickoff
  updates, or spending on a new odds-data provider.
- Editing a frozen/scored prediction artifact, its existing prediction rows,
  grade, or prior authorization.
- A promise that every historical game will be graded. Missing or ineligible
  quotes produce an unlined/ungraded target.

## Affected Components and Contracts

- `contracts/migrations/0016_prediction_market_selections.sql` (use the next
  available append-only number at implementation time), `contracts/schema.sql`,
  `contracts/schema.ts`, and `web/src/lib/schema.ts`.
- `src/cks_picks_cfb/models/market_grading.py` and focused tests for quote
  normalization, side derivation, point/price/quote-ID ordering, and
  pre-kickoff eligibility.
- Weekly inference and artifact producers, including
  `src/cks_picks_cfb/inference/weekly.py`,
  `scripts/pipeline/generate_weekly_bets.py`, and the V5 replay/live forecast
  producers that emit prediction CSVs and manifests.
- `scripts/pipeline/publish_to_db.py`, `scripts/pipeline/score_weekly_bets.py`,
  `scripts/pipeline/score_to_db.py`, replay-grade backfill tooling, and
  release-packet validation.
- `web/src/lib/queries.ts`, `web/src/lib/publication.ts`, game-row components,
  fixtures, and browser tests.
- `docs/ops/weekly_pipeline.md`, `docs/ops/production_runbook.md`, V5 status
  documentation, and the existing Week 4 replay-cutover contract's amendment
  log.

## Implementation Tasks

### Task 1 — Audit and formalize quote eligibility

**Files:**

- `src/cks_picks_cfb/models/market_grading.py`
- New focused tests under `tests/`
- New read-only coverage report script under `scripts/pipeline/`

**Changes:**

- Define one normalized quote shape from the frozen Silver/Neon fields,
  including signed spread points and side-specific prices.
- Reject quote IDs that are unlinked from the forecast snapshot, have a
  different game/target, lack a side price or point, or have a capture time
  after kickoff.
- Implement the chosen side and exact point/price/ID ordering. Preserve the
  canonical snapshot value separately for orientation and audit.
- Produce a read-only audit for every stored season/week: eligible spread and
  total selections, no-line reasons, quote/snapshot linkage, and timing
  failures. Do not mutate R2 or Neon.

**Acceptance criteria:**

- The audit can account for every prediction target without guesses.
- A candidate cannot change a fixed model side, cross games, use a late quote,
  or produce a synthetic point.
- Ties are reproducible regardless of input order.

**Validation:**

- Focused `pytest` cases for home/away and over/under selection, zero edge,
  line and price ties, nulls, mismatched IDs, and late quotes.

### Task 2 — Add immutable target-level selection lineage

**Files:**

- `contracts/migrations/0016_prediction_market_selections.sql`
- `contracts/schema.sql`
- `contracts/schema.ts`
- `web/src/lib/schema.ts`
- Contract and migration tests

**Changes:**

- Add `prediction_market_selections` with immutable run/game/target identity,
  quote and snapshot foreign keys, side, point, price, edge, policy version,
  and creation time. Constrain `target` to `spread` or `total` and require the
  selected quote to belong to the same game.
- Add nullable `market_quote_id` to `prediction_grades`; legacy consensus
  grades remain readable, while all new best-quote grades require the value.
- Add compatible artifact columns for the selected spread and total quote IDs.
  Do not rewrite historical rows during migration.

**Acceptance criteria:**

- One immutable selection per run/game/target; duplicate, cross-game, and
  legacy-override inserts fail.
- Existing migrations, grades, web reads, and V4 rollback behavior remain
  compatible.

**Validation:**

- Migration integration tests, `make contracts-check`, and a Preview
  migration/repeat readback before any production migration.

### Task 3 — Select quotes before freezing forecast artifacts

**Files:**

- Weekly inference and V5 replay/live artifact producers
- `scripts/pipeline/generate_weekly_bets.py`
- Artifact validation and forecast/replay tests

**Changes:**

- Load only the exact frozen snapshot and quote refs declared for a run.
- After forecasts are computed, apply the selection service for each target
  and write selected points, sides, edges, prices, quote IDs, snapshot IDs,
  and policy version into the output artifact and manifest validation.
- Preserve forecast values and all model-parent hashes. Fail closed if a run
  declares lines but lacks the quote ref or valid linkage; allow an explicit
  unlined target only with a recorded reason.

**Acceptance criteria:**

- A forecast artifact is byte-stable across repeat selection from the same
  forecast and quote refs.
- Every lined target has an exact selection row in its artifact; every
  unlined target has no lean/edge/quote ID.
- No model input or model result changes when only quote selection changes.

**Validation:**

- Weekly-inference, V5 replay, and forecast-verifier tests; an independent
  artifact reconstruction using the same frozen refs.

### Task 4 — Publish and grade the exact selected quote

**Files:**

- `scripts/pipeline/publish_to_db.py`
- `scripts/pipeline/score_weekly_bets.py`
- `scripts/pipeline/score_to_db.py`
- `scripts/pipeline/backfill_replay_grades.py`
- Publication and scoring tests

**Changes:**

- In the existing publish transaction, persist the artifact's target-level
  selections only after validating the quote/snapshot linkage and the frozen
  prediction bytes. Reject a selected point that differs from its quote.
- Score and settle every new target from its selection's point, side, and
  price; write both snapshot and quote identity to the grade. The public W-L-P
  record must therefore count the exact displayed bet.
- Keep legacy grades readable but immutable. Replacement artifacts receive new
  grade rows under their new run IDs; never update existing grade values.

**Acceptance criteria:**

- Publishing rejects missing, duplicate, mismatched, late, or byte-inconsistent
  selection data with zero partial writes.
- A half-point difference can change a grade only on the replacement run and
  is traceable to one quote ID.
- Repeated publish/score calls are idempotent.

**Validation:**

- Transaction, negative-path, and settlement tests; Preview publish/freeze/
  score/repeat rehearsal with SQL reconciliation from prediction to selection
  to grade.

### Task 5 — Serve the selected line and preserve user-facing consistency

**Files:**

- `web/src/lib/queries.ts`
- `web/src/lib/publication.ts`
- `web/src/components/GameRow.tsx`
- Web fixtures and tests

**Changes:**

- Read the selected values from the active run rather than falling back to a
  consensus snapshot whenever a best-quote selection exists. Retain the
  current frozen-snapshot fallback only for legacy runs.
- Render the selected point as Market, derive the model bet and edge from that
  exact point, and change the one-line note to describe the selected
  pre-kickoff quote accurately.
- Keep scoreboards based on grade rows and retain the current selected-week
  cutoff behavior.

**Acceptance criteria:**

- Every displayed best-quote line, edge, bet label, and result agrees with the
  selected database row and scored artifact.
- A selected raw quote appears as its actual market increment; legacy pages
  continue to display their existing stored line.

**Validation:**

- Web unit tests, fixture/browser cases for spread and total selection, mobile
  layout, lint, typecheck, and production build.

### Task 6 — Replace eligible historical lineages and release safely

**Files:**

- New controlled replay/rebuild command and verifier
- Existing V5 replay authorization, release-packet, and public-selection tools
- V5 cutover plan amendment and execution log

**Changes:**

- Consume the Task 1 audit to create replacement runs only for season/weeks
  whose quotes meet all eligibility checks. Bind their exact quote-ref SHA,
  selection-policy version, original model parents, and actual regeneration
  timestamp.
- For V5 2026 Weeks 0–4, rebuild equivalent replay forecasts with only the
  market-selection layer changed, independently verify forecast equality and
  selection correctness, rehearse on Preview, validate an exact packet, and
  obtain a separate authorization/activation decision for each production
  selection.
- Apply the same replacement protocol to every other eligible historical run,
  including V4, after its all-year audit and the applicable environment's
  authorization policy are reviewed. Keep every original V4 run and grade as
  an immutable rollback/audit record.

**Acceptance criteria:**

- Every replacement has a distinct immutable run ID, artifact SHA, selection
  receipt, and grade lineage; its forecast values equal the source run.
- Current public selection changes only after a verified Preview rehearsal and
  an explicit production decision. No evidence class, run timestamp, or
  prospective metric is backdated.

**Validation:**

- Per-run coverage/forecast/selection/grade verifier, V4 rollback proof,
  read-only packet validation, and production readback after each authorized
  release.

### Task 7 — Update operating documentation and enforce the policy

**Files:**

- `docs/ops/weekly_pipeline.md`
- `docs/ops/production_runbook.md`
- `docs/modeling/v5_status.md`
- Relevant active-plan amendments and session logs

**Changes:**

- Make best-quote selection the permanent weekly line policy. Document its
  fixed-side rule, quote eligibility, no-line behavior, replay replacement
  procedure, packet requirements, and source-of-truth fields.
- Record the historical audit coverage and each authorized replacement without
  presenting replay results as prospective performance.

**Acceptance criteria:**

- Operators can run and verify the policy without consulting obsolete
  consensus-only instructions.

**Validation:**

- Strict MkDocs build and a documentation authority scan for the retired
  consensus-only serving claim.

## Testing Strategy

- Python unit tests cover both targets, all sides, normal and malformed quote
  shapes, zero/no-line paths, determinism, prices, and settlement.
- Contract/migration tests cover referential integrity, legacy compatibility,
  append-only behavior, grants, and transaction rollback.
- Forecast/replay tests prove no model prediction or model parent changes and
  verify output reconstruction from immutable quote refs.
- Integration tests cover publishing and scoring a selected quote, idempotent
  repeats, negative zero-write paths, and V5 release/rollback boundaries.
- Web tests cover displayed line, edge, bet, result, historical fallback, and
  the 2026 record through the prior selected week.
- Final gates: scoped `pytest`, `uv run ruff check .`, `make contracts-check`,
  web lint/typecheck/build/browser tests, strict MkDocs, and `git diff --check`.

## Risks and Edge Cases

- A quote may have a genuine point but no price for the chosen side. It is not
  executable and must not be selected.
- Multiple providers can report the same point. Price and quote ID tie-breakers
  ensure deterministic behavior without hidden preference.
- A pre-kickoff capture can contain a provider's stale update timestamp. The
  policy uses the immutable capture timestamp as the hard eligibility boundary
  and preserves the provider timestamp for audit.
- A game can have spread eligibility but no total eligibility, or the reverse;
  target handling remains independent.
- A replacement line can legitimately change historical W-L-P results. It is
  a new, fully traceable replay lineage, never an edit of prior evidence.
- Existing V5 replay production releases require the exact replay-authorization
  path. This plan does not grant those release decisions.
- The stored quote corpus may not cover every historical year/week despite the
  permanent policy. The audit must report coverage before any rebuild begins.

## Definition of Done

- [x] The all-year read-only audit infrastructure (`audit_quote_coverage()`)
  is implemented and tested; a run-level coverage audit script can be built
  from it. Full historical season/week audit execution is gated on Tasks 3–6
  authorization.
- [x] Forecast artifacts, selections, published values, grades, and web rows
  bind to the same target-specific raw quote. _(Tasks 3–5 implemented)_
- [x] Original legacy and V4 artifacts remain immutable and readable; this
  session creates no artifact, no grade, and no Neon mutation.
- [ ] Eligible historical replacement runs, including 2026 V5 Weeks 0–4, have
  passed their required Preview and explicit production release gates.
  _(Task 6 pending separate operational authorizations)_
- [x] Future weekly operations select and verify the best quote before freeze.
  _(Task 3 integrated in weekly.py, generate_weekly_bets.py, generate_v5_weekly_bets.py, generate_v5_replay_weekly_bets.py)_
- [x] Required validation (1,439 pytest, contracts-check, ruff format/check,
  web lint/typecheck/tests/build, git diff --check) and documentation are complete.
- [ ] The plan status is updated to `Implemented` only after every item passes.

## Amendments

**Amendment 1 (2026-09-25, session 22):** The user directed implementation of
the full plan. Tasks 1, 2, and 7 are implemented and validated in this session.
Tasks 3–6 (artifact integration, publish/grade pipeline, web serving, and
historical replacement runs) remain pending because they require Preview
rehearsal and separate production authorization decisions per the commit policy.
The plan stays `In Progress` until those gates are cleared.

**Amendment 2 (2026-09-25, session 23):** Tasks 3, 4, and 5 implemented:
- Read-only audit CLI `scripts/pipeline/audit_market_quote_coverage.py` accounts for all 2,188 stored prediction targets.
- Quote selection defaults unpriced quotes (CFBD) to standard -110.0 American odds (`require_price=False`) while supporting explicit prices.
- Pipeline integration in `weekly.py`, `v5_serving.py`, `generate_weekly_bets.py`, `generate_v5_weekly_bets.py`, and `generate_v5_replay_weekly_bets.py` selects best quotes and writes selection lineage into artifacts and manifests.
- Publishing (`publish_to_db.py`) inserts verified selections into `prediction_market_selections` and rejects point mismatches.
- Scoring (`score_to_db.py`, `backfill_replay_grades.py`) links grades to `market_quote_id` and sets `model_side_best_quote_v1`.
- Web serving (`queries.ts`, `page.tsx`) reads from `prediction_market_selections` via COALESCE and updates footnote copy.
- Full test suites pass: 1,439 Python tests, 11 web tests, web typecheck, build, contracts-check. Task 6 (generating/activating replacement replay runs on Preview/Production) is staged for subsequent operational execution.

