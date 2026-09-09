# 2025 Retrospective Model Context

- **Status:** Approved
- **Created:** 2026-09-08
- **Planner:** Sol
- **Approval source:** User explicitly requested implementation of the proposed plan on 2026-09-08.
- **Implementation log:** `session_logs/2026-09-08/09-2025-retrospective-model-context-implementation.md`
- **Commit policy:** Separate plan commit before implementation because this work adds immutable model lineage, an append-only database migration, production data publication, and public UI behavior.

## Goal

Give the 2026 prediction site honest historical context by showing the deployed
V4 design's retrospective 2025 spread and total hit rates for the full season
and the week matching the currently selected 2026 week.

Success means:

- the calculation reuses the certified, strictly temporal V4 replay in which
  every 2025 forecast has `training_max_year=2024`;
- reconstructed historical market references remain diagnostic-only and are
  never inserted into canonical prediction grades, live system records, ROI,
  selection, or promotion evidence;
- the public site retains the live 2026 record and adds clearly labeled 2025
  full-season and matching-week context;
- the verified full-season output is spread 379-366-16 (50.9%) and total
  398-358-5 (52.6%), with pushes excluded only from the percentage denominator.

## Current State

- The certified `rating_v4_historical_predictions_v1` ref is version
  `f4ec062c7f931f125ce6be99`, content SHA
  `6bdbe75ce83554c5828ac1a807056e26844db44c77defb6607d2ec7386efca2d`.
  It contains 761 2025 games x two targets and is strictly trained through
  2024. It already recovers the frozen V4 routes serving as the 2026 benchmark.
- The locked 2025 feature ref is version `fe55e75884c7665527e740d3`, content
  SHA `0bee7740705bdc61b37c00a1a9fec23383644a6a148e4c74581000e2758a9ecb`.
  It supplies the immutable game/week mapping for the forecast population.
- The reconstructed `phase2e_market_references_v1` ref is version
  `f963100462302311a853f6bb`, content SHA
  `37bf453c9698271b2c30cead4334fb224191c43d51ee2c1d65c454d07632c6b7`.
  It already applies `consensus_then_median_v1`, covers all 761 V4 games, and
  is stamped `historically_reconstructed` and
  `post_phase5_diagnostic_only`.
- `prediction_grades` and `system_stats` are the canonical, run-specific live
  record. They must not receive retrospective rows.
- The web app currently calls `getSystemStatsThroughWeek()` and renders
  `RecordBanner` only in prediction publication mode.
- The worktree contains pre-existing modifications to weekly scoring,
  publishing, Silver builders, and ops orchestration plus an untracked session
  log. They are user-owned and outside this contract.

## Proposed Approach

Build a new immutable diagnostic artifact from the three pinned refs, then
publish only its aggregate rows through a dedicated, idempotent path to a new
Neon table. The web app reads that table separately from the live record.

The builder must use the already-selected market lines without reselecting a
provider. For spread, choose home when `v4_prediction + spread_line >= 0`, then
settle using `actual + spread_line`. For total, choose over when
`v4_prediction >= total_line`, then settle using `actual - total_line`. Zero is
a push. The hit-rate denominator is wins plus losses; W-L-P and compared-game
counts remain visible.

The R2 artifact is the provenance authority and contains per-game comparisons,
period aggregates, source refs/checksums, calculation version, code/config SHA,
timing class, diagnostic usage, and an audit report. Neon is a derived serving
projection containing aggregates only.

## Scope

### Included

- Immutable 2025 V4 retrospective comparison and audit artifacts.
- Preview/production-safe aggregate publisher and append-only Neon migration.
- Canonical SQL/TypeScript schema, synchronized web schema, query types, UI,
  fixtures, tests, operating documentation, and implementation session log.
- Preview-first migration, artifact verification, publication, and visual
  verification; production rollout only after Preview parity.

### Excluded

- Retraining or rerunning the production-refit V4 bundle for 2025.
- Successor-model historical context.
- Canonical `prediction_runs`, `prediction_grades`, `system_stats`,
  `current_week`, profit/ROI, betting claims, selection, or promotion changes.
- Sourcing authentic historical pre-kick timestamps or exposing game-level
  retrospective comparisons publicly.
- Changes to the unrelated pre-existing worktree modifications.

## Affected Components and Contracts

- Python calculation contracts under `src/cks_picks_cfb/`, a pipeline CLI under
  `scripts/pipeline/`, a pinned configuration under `conf/`, and focused tests.
- A new `historical_model_context` public-schema table introduced by migration
  `0012`, mirrored in `contracts/schema.sql`, `contracts/schema.ts`, and
  `web/src/lib/schema.ts`.
- The web query interface gains `HistoricalContextPeriod`,
  `HistoricalModelContext`, and
  `getHistoricalModelContext(comparisonSeason, selectedWeek)`.
- The home page gains a prediction-mode-only historical context component;
  the existing `Stats` and `RecordBanner` interfaces remain unchanged.

## Implementation Tasks

### Task 1 — Implement the immutable diagnostic calculation

**Files:**

- `src/cks_picks_cfb/models/historical_model_context.py`
- `conf/weekly_bets/v4_2025_retrospective_context.yaml`
- `scripts/pipeline/build_historical_model_context.py`

**Changes:**

- Pin and checksum-verify the exact prediction, locked-feature, and market refs
  listed above; reject substitutions unless this contract is amended.
- Enforce season 2025 only, targets exactly spread/total, unique
  game/target keys, 761 common games, `training_max_year=2024`, complete week
  mapping, non-null comparison lines, `consensus_then_median_v1`, reconstructed
  timing, and diagnostic-only usage.
- Produce one deterministic per-game comparison row per game/target and
  aggregate rows for the full season and Weeks 1-15. Carry model identity,
  period, W-L-P, compared count, hit-rate numerator/denominator semantics, all
  parent refs, calculation version, and code/config identity.
- Write the data, manifest, ref, and independent audit under an immutable
  Preview R2 prefix. Same-identity reruns must verify and return the identical
  artifact rather than overwrite it.

**Acceptance criteria:**

- Full season: spread 379-366-16 and total 398-358-5.
- Week 2: spread 26-22-2 and total 28-22-0.
- No Week 0 row is invented.
- The audit proves 1,522 unique comparison rows, 761 games, exact parent
  identity, complete line/week coverage, strict chronology, and aggregate
  parity.

**Validation:**

- Focused unit and local-storage integration tests for contracts, settlement,
  aggregation, provenance rejection, and deterministic reruns.

### Task 2 — Add the derived Neon serving contract

**Files:**

- `contracts/migrations/0012_historical_model_context.sql`
- `contracts/schema.sql`
- `contracts/schema.ts`
- `web/src/lib/schema.ts`
- `scripts/pipeline/publish_historical_model_context.py`

**Changes:**

- Add `historical_model_context` with a deterministic text primary key; model
  ID/name; comparison season; `period_scope` (`season` or `week`); nullable
  comparison week; spread/total W-L-P and compared counts; calculation version;
  timing class; usage; source artifact URI/SHA; and timestamps.
- Add check constraints so season rows have no week and week rows have a
  non-negative week. Add partial unique indexes for one season row and one row
  per numbered week for a model/season/calculation version.
- Grant read-only access to `cks_web`. Keep migration history append-only and
  both TypeScript schema copies byte-equivalent through existing contract
  validation.
- The publisher reads and checksum-verifies only the aggregate artifact,
  validates every row before one transactional upsert, and accepts an explicit
  Preview or production environment. It must not issue SQL against canonical
  run, grade, record, or current-week tables.

**Acceptance criteria:**

- Repeated publication is idempotent.
- Invalid artifact identity, missing periods, or mixed model/calculation
  versions fail before writes.
- Row-count/checksum snapshots prove canonical live tables are unchanged.

**Validation:**

- Migration tests on empty and current schemas, publisher transaction tests,
  `make contracts-check`, and the Python contract suite.

### Task 3 — Add the public historical context panel

**Files:**

- `web/src/lib/queries.ts`
- `web/src/components/HistoricalModelContext.tsx`
- `web/src/app/page.tsx`
- `web/src/test/fixtures/publication.ts`

**Changes:**

- Add `getHistoricalModelContext(comparisonSeason, selectedWeek)`, returning
  the full-season row and nullable exact-week row for the pinned deployed V4
  context. Missing or duplicate rows fail closed rather than choosing silently.
- On the 2026 page, request season `2025` and the selected week in parallel with
  games and live stats. Render only in prediction mode and only when the
  full-season context exists.
- Keep `RecordBanner` unchanged. Render a separate accessible panel titled
  `2025 Retrospective Model Context` with full-season and matching-week sections,
  separate spread and total hit rates, W-L-P, and sample counts.
- Week 0 retains the full-season section and displays
  `No 2025 Week 0 comparison`. Other missing weeks use the same explicit
  unavailable state.
- Display: `Uses reconstructed historical reference lines captured after the
  season; diagnostic context, not an official pregame betting record.`

**Acceptance criteria:**

- The existing live 2026 record and historical context render together without
  changing publication boundaries.
- Market-only mode never queries or renders model context.
- Database/context failure does not expose partial or mislabeled results and
  does not prevent games or the live record from rendering.

**Validation:**

- Query/component tests for Week 2, Week 0, missing context, duplicate context,
  prediction mode, and market-only mode; web lint, typecheck, build, and browser
  smoke/visual checks at desktop and mobile widths.

### Task 4 — Preview verification and production rollout

**Changes:**

- Commit the implementation checkpoint before any immutable apply run.
- Run the builder dry-run, Preview apply, and independent artifact verification.
- Apply migration 0012 to Preview, publish aggregates, and confirm exact query
  values and unchanged canonical table snapshots.
- Verify the Preview UI for selected Weeks 0, 1, and 2.
- Only after Preview parity, apply migration 0012 and publish the exact verified
  aggregate artifact to production, deploy the web app through the established
  workflow, and verify live values plus unchanged 2026 records.
- Update the operating documentation, this contract to `Implemented`, and the
  implementation session log with artifact identity, migration evidence,
  validation results, and rollback notes.

**Acceptance criteria:**

- Production reads the same source artifact SHA verified in Preview.
- The context panel is visible in prediction mode and all live Week 0-2 game,
  grade, and record behavior is unchanged.
- Rollback can remove the panel by web rollback without deleting immutable R2
  evidence or canonical live data; serving rows may remain inert.

## Testing Strategy

- Unit tests cover sign conventions, ties/pushes, percentage denominators,
  missing values, duplicate keys, chronology, provenance, period aggregation,
  and Week 0 absence.
- Artifact integration tests cover local immutable writes, manifest/ref/audit
  checksums, repeat-run identity, and exact 2025 invariants.
- Database tests cover migration compatibility, constraints, partial uniqueness,
  grants, transactional/idempotent publication, and canonical-table isolation.
- Web tests cover query mapping, accessible copy, conditional publication-mode
  rendering, unavailable states, responsive layout, and preservation of the
  live record.
- Required gates: focused Python tests, `uv run ruff check`, contract validation,
  `git diff --check`, `uv run mkdocs build --quiet`, web lint, typecheck, build,
  and browser smoke verification.

## Risks and Edge Cases

- Historical lines were captured after the games. Every layer must retain the
  reconstructed/diagnostic label; no code may alias these rows to canonical
  grades or imply a verified betting record.
- Spread values are home-team lines. Reversing the sign silently changes the
  record, so the exact known aggregates are hard acceptance gates.
- Pushes remain visible and excluded from the percentage denominator.
- 2025 has no Week 0; do not map it to Week 1.
- The builder must not use the V4 production-refit bundle, because that bundle
  trained on 2025.
- The current dirty worktree overlaps weekly pipeline code. Preserve it and
  avoid broad formatting; begin Terra implementation from a user-controlled
  committed checkpoint.

## Definition of Done

- [ ] The immutable artifact and independent audit pass with exact expected counts.
- [ ] Migration, schema copies, and idempotent publisher are complete and validated.
- [ ] Preview-first and production publication evidence is recorded.
- [ ] The accessible panel renders correctly without changing live records.
- [ ] All required validation passes.
- [ ] Documentation and implementation session log are updated.
- [ ] Plan status is updated to `Implemented`.

## Amendments

Any material change to pinned inputs, provenance classification, settlement
semantics, database shape, public labeling, production isolation, or rollout
order requires an explicit amendment here and renewed user approval before
implementation continues.
