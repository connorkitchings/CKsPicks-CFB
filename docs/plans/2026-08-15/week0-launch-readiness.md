# Week 0 Launch Readiness

- **Status:** Implemented
- **Created:** 2026-08-15
- **Planner:** Sol
- **Approval source:** User instruction in the originating Codex task: “Implement the proposed plan.”
- **Implementation log:** `session_logs/2026-08-15/02-week0-launch-implementation.md`
- **Commit policy:** Separate, reviewable launch commits after Preview rehearsal; commits and pushes remain user-controlled.

## Goal

Make the 2026 Week 0 workflow operational before the first kickoff on August 29, 2026. Observable success means that immutable R2 data is registered and ready, a private Week 0 prediction run can drive Pick'em, the public application can safely show the schedule and market lines without model output, and production release steps have explicit go/no-go evidence.

## Current State

- Preview R2 contains historical/model-ready artifacts, a ten-route fallback bundle, and the eight identified Week 0 FBS matchups.
- Preview Neon contains 7,156 registered source captures but no dataset versions. A failed hydration run and a stale raw-import run remain as incident evidence.
- All model routes are display fallbacks and are ineligible for high-confidence labeling.
- Production Neon is on the legacy schema and still points at 2025 Week 16.
- The canonical Vercel production alias is unavailable; the protected Preview deployment is stale.
- Pick'em export and submission code exists, but no current Week 0 run or prediction token is available.
- The worktree contains ongoing launch work that must be preserved. Current local tests, lint, contract checks, typecheck, and build pass.

## Proposed Approach

Repair the Preview control plane by registering existing immutable R2 artifacts rather than repeating raw import. Create a private immutable fallback run for pipeline and Pick'em rehearsal. Add an explicit, fail-closed public publication mode that queries and displays schedule and market information without selecting model output. Rehearse all operations in Preview before proposing production migration and deployment.

## Scope

### Included

- Preview catalog repair, audit, readiness, and private Week 0 publication.
- A public market-only application mode and tests preventing model-output exposure.
- Pick'em export, API reconciliation, dry-run, and an approval-gated submit procedure.
- Production migration/deployment readiness evidence and launch documentation.

### Excluded

- Automatic public promotion of the fallback model.
- High-confidence branding for an unpromoted route.
- Unattended Pick'em submission.
- Destructive cleanup of failed operational history.
- Automatic Git commits, pushes, production migrations, or production deployments.

## Affected Components and Contracts

- Public web query and rendering contracts under `web/src/`.
- Server-side publication variables documented in `web/.env.example` and operational docs.
- Preview catalog and weekly operation records in Neon; immutable artifacts in R2.
- Pick'em export/reconciliation procedure in `scripts/pipeline/export_cfbd_pickem.py` and the Make target.
- Run-aware database migrations 0002–0005 and Vercel environment configuration.

## Implementation Tasks

### Task 1 — Repair Preview catalog registration

**Files:** Operational records only; existing R2 artifacts remain immutable.

**Changes:**

- Preserve the failed hydration and stale raw-import runs.
- Start a new `import-history-silver` operation through the Preview credential wrapper.
- Register the existing Silver/Gold artifacts and verify checksums and dataset lineage.

**Acceptance criteria:**

- Dataset versions are populated and selected refs resolve to immutable R2 objects.
- The catalog retains the historical incident records without resuming the raw import.

**Validation:**

- Query catalog counts and states without printing credentials.
- Run the data audit against Preview.

### Task 2 — Produce a private Week 0 run

**Files:** Existing weekly pipeline, Preview Neon records, and immutable Preview R2 artifacts.

**Changes:**

- Refresh 2026 schedule, preseason sources, and market lines as of the rehearsal cutoff.
- Run Week 0 readiness with `conf/weekly_bets/v2_preview_2026.yaml`.
- Publish a new immutable Preview fallback run for private use.

**Acceptance criteria:**

- Exactly eight expected FBS-vs-FBS games are reconciled.
- The run records manifest checksums, cutoff, prediction coverage, and market coverage.
- No prediction is marked high-confidence.

**Validation:**

- Run audit, readiness, publication, and run-state queries in Preview.
- Stop on checksum drift, duplicates, missing required features, or wrong-environment credentials.

### Task 3 — Implement market-only public publication

**Files:** `web/src/lib/publication.ts`, web queries, page/components, tests, environment examples, and operational documentation.

**Changes:**

- Add an explicit server-side mode that defaults to market-only and requires an exact opt-in to expose predictions.
- In market-only mode, query only schedule, current market spread/total, and freshness fields.
- Hide predictions, leans, edges, confidence, regime, model metadata, and prediction-derived records and controls.
- Keep prediction mode compatible with the existing run-aware UI.

**Acceptance criteria:**

- Week 0 renders matchups, kickoffs, and market lines in market-only mode.
- Neither the server projection nor rendered page exposes model-only fields in that mode.
- Prediction mode retains existing behavior when explicitly enabled.

**Validation:**

- Add focused publication/query/component tests.
- Run web lint, typecheck, and production build.

### Task 4 — Rehearse Pick'em without submission

**Files:** Existing Pick'em exporter, generated Preview artifact, and documentation.

**Changes:**

- Export from the exact private run artifact.
- Fetch and reconcile the authenticated contest slate when a token is available.
- Generate the final spread-only payload and dry-run report.

**Acceptance criteria:**

- Every submitted candidate maps to the intended CFBD game ID.
- Totals are excluded.
- No POST occurs without explicit approval of the exact final slate.

**Validation:**

- Run exporter tests and, when credentials are available, API validation and dry-run only.

### Task 5 — Establish release evidence

**Files:** Database migrations, Vercel configuration, docs, plan, and implementation session log.

**Changes:**

- Verify migrations 0002–0005 against Preview and document the production sequence.
- Reconcile the dirty worktree and identify reviewable launch commits without staging or committing.
- Record the remaining user-controlled production gates.

**Acceptance criteria:**

- Preview health, public-boundary, data, run, and Pick'em evidence is recorded.
- Production migration, committed deployment, canonical alias, and final POST remain explicit approval gates.

**Validation:**

- Run the complete repository and documentation checks plus `git diff --check`.

## Testing Strategy

- Python unit/integration suite and focused data/Pick'em tests.
- Ruff, contract synchronization, and migration validation.
- Web tests for publication configuration, query projection, and market-only rendering.
- Web lint, typecheck, and production build.
- Preview catalog/run queries and application health checks.
- Pick'em reconciliation and dry-run with no submission.

## Risks and Edge Cases

- 2026 talent data may remain unavailable and authentic historical market quote timestamps may remain insufficient for automatic promotion.
- Market lines can change after a run; final Pick'em approval must identify the exact run and slate.
- Preview and production credentials must never be interchanged or printed.
- Production currently lacks run-aware migrations and cannot receive the new release until migration approval.
- The dirty worktree contains user-owned work and must not be broadly formatted, staged, discarded, or committed.
- A missing prediction token blocks Pick'em API reconciliation/submission, but not public market-only launch.

## Definition of Done

- [x] Preview catalog dataset versions and immutable refs validate.
- [x] A complete private Week 0 run exists with no high-confidence claims.
- [x] Market-only publication is implemented and verified not to expose model output.
- [x] Pick'em export exists; the missing prediction token is recorded as the sole external reconciliation blocker.
- [x] Required code, data, web, documentation, and diff validation passes.
- [x] Production approval gates and exact next commands are documented.
- [x] Implementation session log is complete.
- [x] Plan status is updated to `Implemented` only when every item above passes.

## Amendments

### Amendment 1 — Re-register existing immutable refs on recovery

**Reason:** The first `import-history-silver` run proved that builders returned immediately when their output ref already existed. They printed the immutable R2 ref but never re-registered its manifest in an empty Neon catalog, leaving `catalog.dataset_versions` empty and causing the structural audit to fail.

**Original approach:** Use the existing skip-imports operation to register already-built Silver/Gold artifacts.

**Revised approach:** Preserve immutable data and the same operation, but make every affected builder verify the existing ref against its manifest, recursively register immutable parent manifests, and atomically register each version and its dependency edges before returning.

**Impact:** Mechanical idempotency repair only. Architecture, public interfaces, scope, lineage requirements, and acceptance criteria are unchanged.

### Amendment 2 — Refresh final-score truth and tolerate index visibility lag

**Reason:** Structural audit identified a canceled 2024 game and a completed 2025 Army–Navy game whose legacy snapshot still said incomplete. After that immutable correction, Preview publication also observed a brief R2 listing delay between the schedule write and the market ingester's games-index read.

**Original approach:** Refresh launch inputs, audit them, and publish through the existing weekly state machine.

**Revised approach:** Capture current CFBD final-score truth as a new immutable Silver parent, rebuild downstream Gold refs, and retry the market ingester's read-only games-index lookup for a bounded interval with caching disabled.

**Impact:** Data truth and transient-read hardening only. The historical artifacts remain immutable, the failed operations remain recorded, and publication still stops on a genuinely missing games index.

### Amendment 3 — Reconcile canonical Week 0 with CFBD provider Week 1

**Reason:** CFBD labels the August 29 opening slate as provider Week 1, while the versioned repository policy assigns the same eight game IDs to canonical Week 0. The market ingester originally queried provider Week 0 and could not find the slate.

**Original approach:** Refresh market lines through the existing Week 0 publish step and select an existing canonical market dataset from the catalog.

**Revised approach:** Select game IDs by canonical week, query the corresponding provider week, retain both week values, bind the Bronze capture to the pipeline run, and build run-specific immutable `market_quotes` and `market_snapshots` before freezing inputs.

**Impact:** This preserves the existing canonical-week policy, immutable lineage, public contracts, scope, and acceptance criteria. It makes the intended weekly operation executable and auditable.

### Amendment 4 — Remove impossible current-season team-game input

**Reason:** Input freezing required a 2026 `reconciled_team_game` dataset before Week 0 even though no 2026 games have been played. The frozen point-in-time Gold dataset already contains the prior-state features used by the ten-route bundle.

**Original approach:** Freeze games, market snapshots, current-season reconciled team-game rows, and point-in-time matchups.

**Revised approach:** Freeze canonical games, the run-specific market snapshot, and point-in-time matchups. Prediction coverage now uses the frozen canonical games dataset rather than mutable compatibility indexes.

**Impact:** This removes an unused and unsatisfiable input while strengthening reproducibility. Model design, features, public interfaces, scope, and acceptance criteria are unchanged.
