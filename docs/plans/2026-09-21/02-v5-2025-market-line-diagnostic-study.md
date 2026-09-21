# V5-02: 2025 Market-Line Diagnostic Study

- **Status:** In Progress
- **Created:** 2026-09-21
- **Planner:** Sol
- **Approval source:** User explicitly authorized with "proceed" on 2026-09-21 for
  the exact plan presented (replay lines now as a labeled diagnostic, V5-only).
- **Implementation log:** `session_logs/2026-09-21/05-v5-2025-market-line-diagnostic-study.md`
- **Commit policy:** Separate commits — a plan checkpoint (this contract + index
  row + planning log), then implementation checkpoints per Terra's evidence
  stages. User controls Git operations.

## Goal

Compare the 11A-verified V5 conditional 2025 forecasts against replay
provider-recorded lines as a **diagnostic comparison only**. Success is a signed,
independently verified Preview publication plus a report that answers one
question: how close were the conditional V5 margin/total forecasts to
market-implied predictions on the 2025 intersection population? The study must be
honestly labeled as a reconstructed diagnostic — it is **not** closing-line or
CLV evidence and has no effect on readiness gates, eligibility, Contract 11/12,
or the 04/04B lifecycle.

## Current State

- The conditional-results lane is complete: 11A independently reconstructed the
  frozen forecast artifact `forecast-v1-20260917-4600ddd-04b` under Preview run
  `conditional-v1-20260919-9265314-11a`, and 12A published a V5-only scorecard
  (`conditional-v1-20260921-scorecard`, manifest SHA `0f4fbf33...`) for 934 2025
  games per target (margin MAE 14.382, total MAE 13.200). Permitted use is
  `conditional_historical_results_only`, and 12A explicitly bars market access —
  this study requires its own contract (this one).
- No genuinely timestamped 2025 pre-kickoff quotes exist in the lake. The only
  timestamped path (The Odds API historical backfill, ~6,100 credits for 2025)
  is deferred as a staged follow-up pending this study's outcome and separate
  spend approval.
- The 2025 V4 operational replay consumed post-season CFBD provider-recorded
  lines (`raw/betting_lines/year=2025`) normalized via `consensus_then_median_v1`
  and registered immutable Silver versions: `market_snapshots` version
  `e4061aab...` (per-game canonical lines, 762/762 FBS-FBS games incl.
  Army-Navy week 16) and `market_quotes` version `32db239e...`. These versions
  were set to `quarantined` in the Preview catalog on 2026-09-13 for lacking
  Bronze lineage; their R2 artifact bytes are immutable and untouched.
- V5 forecast rows carry `(horizon, head, target, season, week, game_id, actual,
  prediction, ...)` and join to lines on `game_id` per target. The V5 2025
  population (934 incl. FBS-FCS) exceeds the lined set (762 FBS-FBS), so the
  study population is the intersection with full accounting of exclusions.
- Margin sign convention is the principal correctness risk: V5 margin orientation
  (home-minus-away) must be reconciled against market-implied margin
  (`-home_team_spread_line`) before any metric is computed.

## Proposed Approach

Read the quarantined `market_snapshots` bytes directly from R2 (no catalog
writes, no un-quarantine) with checksum verification, recompute the 11A-verified
forecast record through the established fail-closed entry gate, join on
`game_id`, validate the sign convention against fixture games, then compute
paired V5-vs-market football metrics and publish signed Preview evidence plus a
report — mirroring the 12A preflight/apply/verify publication pattern. Rejected
alternative: reopening canonical market pipelines or touching catalog state,
which would violate the quarantine invariant for zero diagnostic gain.

## Scope

### Included

- 2025-only, both targets (margin, total), V5-only (no V4 benchmark).
- Reuse of the 11A fail-closed forecast loader (`historical_scorecard.py`
  entry-gate pins: raw SHA `5a7e7d48...`, canonical `7ce47863...`, record
  `7ee050b4...`); sign-convention validation; intersection accounting;
  paired V5-vs-market metrics with deterministic bootstrap CIs; stage slices;
  signed Preview publication with independent re-read and idempotent repeat;
  a `docs/research/` report labeled `diagnostic_comparison_only`.

### Excluded

- The Odds API backfill, 2022-2024 extensions, V4 comparisons, ROI/bet
  selection, CLV claims, any readiness/eligibility effect, any catalog/Neon/
  production writes, any change to quarantined states, any market data entering
  features or selection, any 2020/2026 data.

## Affected Components and Contracts

- New research code under `src/cks_picks_cfb/forecast/` (no production paths).
- New CLI under `scripts/research/`; new tests under `tests/`.
- New research-namespace R2 artifacts under
  `artifacts/research/data-first-football-v1/market-diagnostics/`
  (Preview only).
- Read-only inputs: 11A verification record, `market_snapshots` version
  `e4061aab...` bytes.
- Docs: new `docs/research/2026-09-21-v5-2025-market-line-diagnostic-report.md`,
  index row in `docs/plans/index.md`.
- No interface, schema, migration, Neon, bundle, or web changes.

## Implementation Tasks

### Task 1 — Entry-gate resolution and sign-convention validation

**Files:**

- `src/cks_picks_cfb/forecast/market_diagnostic.py`
- `scripts/research/run_v5_market_diagnostic.py` (`preflight`)

**Changes:**

- Resolve the exact full version SHA of `market_snapshots` (prefix `e4061aab`)
  from the immutable `v4replay-2025-w*` run input refs; checksum-verify the R2
  bytes; record full SHA, URI, `consensus_then_median_v1` policy,
  `line_semantics: provider_recorded_lines_postseason_capture`, and
  `catalog_state: quarantined_preview` in the study manifest. Fail closed on
  any mismatch.
- Re-read the 11A-verified forecast output parquet via the 12A loader path and
  its exact SHA pins; fail closed on mismatch.
- Validate margin orientation: V5 margin must be home-minus-away. Confirm by
  fixture (Army-Navy `401762521`: market-implied home margin +6 vs V4 reference
  prediction) and by a positive-correlation check between V5 margin predictions
  and market-implied margins. Fail closed if anti-correlated or uncorrelated.

**Acceptance criteria:**

- Preflight resolves and pins both artifact identities with verified checksums.
- Convention validation evidence is recorded before any metric is computed.
- Intersection population per target is reported with explicit excluded-game
  accounting; halt and return to Sol if intersection < 500 games per target.

**Validation:**

- Focused unit tests for pin mismatch, duplicated game keys, missing lines,
  and flipped-sign fixtures (all must fail closed).
- Preview R2 `preflight` run on the pinned inputs, zero writes.

### Task 2 — Paired metrics and report rendering

**Files:**

- `src/cks_picks_cfb/forecast/market_diagnostic.py`
- `scripts/research/run_v5_market_diagnostic.py` (`apply`)

**Changes:**

- Compute, per target on identical games: V5 vs market MAE/RMSE/bias; paired
  per-game absolute-error deltas; mean delta with deterministic seeded
  bootstrap 95% CI; V5-closer / market-closer / tie counts; completed-game-stage
  slices (0/1/2/3/4+); edge (V5 minus market-implied) distribution
  mean/sd/deciles — descriptive only. No ROI, no selection, no CLV.
- Render the Markdown report with the mandatory labeling block:
  `permitted_use: diagnostic_comparison_only`,
  `line_semantics: provider_recorded_lines_postseason_capture`,
  `not closing-line or CLV evidence; no readiness, eligibility, selection, or
  betting use`.

**Acceptance criteria:**

- Metrics reproduce deterministically (seeded bootstrap, pinned inputs);
  stage slices match 12A slice definitions; report carries the labeling block
  verbatim and contains no readiness recommendation.

**Validation:**

- `tests/test_market_diagnostic.py` passes (positive fixtures with hand-checked
  metric values plus all negative fail-closed cases).
- `ruff check` / `ruff format` clean on touched paths.

### Task 3 — Signed publication, independent verification, repeat

**Files:**

- `src/cks_picks_cfb/forecast/market_diagnostic_publication.py`
- `scripts/research/run_v5_market_diagnostic.py` (`verify`)

**Changes:**

- Publish the diagnostic JSON and signed terminal manifest to Preview R2 under
  `artifacts/research/data-first-football-v1/market-diagnostics/v1/runs/<run-id>/`;
  verifier-owned re-read of signatures and hashes directly from storage;
  idempotent repeat must return `already_applied`.

**Acceptance criteria:**

- Independent re-read returns `verified: true`; repeat apply returns
  `already_applied`; report is saved to
  `docs/research/2026-09-21-v5-2025-market-line-diagnostic-report.md`.

**Validation:**

- End-to-end CLI cycle in Preview: `preflight` → `apply` → `apply` (repeat) →
  `verify`; `uv run python contracts/validation.py`;
  `uv run mkdocs build --strict --quiet`; `git diff --check`.

## Testing Strategy

- Unit: hand-checked metric fixtures, bootstrap determinism, stage slicing,
  edge-distribution math, report-labeling presence.
- Negative: wrong forecast SHA, wrong market version SHA, duplicate game keys,
  missing lines, flipped-sign fixture — each must fail closed with a named
  error, never silently proceed.
- Integration: full CLI cycle against Preview R2 (preflight/apply/repeat/verify).
- Regression: scoped existing suites for touched forecast/audit modules; full
  suite only if shared helpers are modified (they should not be).

## Risks and Edge Cases

- **Sign-convention mismatch:** the highest-severity risk; mitigated by
  Task 1 fixture + correlation gates executed before metrics (fail closed).
- **Intersection shortfall** (e.g., V5 934 vs lined 762, FBS-FCS gaps):
  accounting-first preflight with a 500-game/target hard floor.
- **Misreading quarantined state as usable lineage:** the study reads raw bytes
  only and records the quarantine in its manifest; no catalog interaction.
- **Diagnostic misinterpretation as eligibility evidence:** mandatory
  permitted-use labeling in the artifact manifest and report; contract states
  the null effect on all gates.

## Definition of Done

- [ ] Entry-gate SHAs verified fail-closed for forecasts and market snapshots.
- [ ] Sign-convention validation passes with recorded evidence before metrics.
- [ ] Intersection accounting complete per target; integrity checks fail closed.
- [ ] Deterministic paired metrics, stage slices, and edge distributions computed.
- [ ] Signed Preview publication, independent re-read verify, idempotent repeat.
- [ ] Report published with `diagnostic_comparison_only` labeling; no readiness claims.
- [ ] Tests, ruff, contracts validation, strict MkDocs, `git diff --check` pass.
- [ ] This contract and `docs/plans/index.md` updated to `Implemented`.

## Amendments

None. Terra may append a minor amendment only if it preserves lineage scope,
artifact identities, permitted-use labeling, and the no-readiness-effect
boundary; anything else returns to Sol.
