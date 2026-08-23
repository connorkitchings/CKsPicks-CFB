# Modernization Phases 1–5 Fidelity and Refactoring

- **Status:** Implemented
- **Created:** 2026-08-22
- **Planner:** Sol
- **Approval source:** User explicitly requested implementation in this task on 2026-08-22.
- **Implementation log:** `session_logs/2026-08-22/02-modernization-phases-1-5-fidelity-and-refactor.md`
- **Commit policy:** Separate plan commit recommended; implementation commits remain user-controlled.

## Goal

Complete the unfinished fidelity work from modernization Phases 1–3, then perform
behavior-preserving Phase 4–5 refactors. Preserve the sealed V4 model, artifact
contracts, CLI behavior, public imports, and production data boundaries.

## Current State

- Phase 2–3 storage, Silver, aggregation, and byplay decomposition is present but
  uncommitted. It is authoritative and must be preserved.
- The V4 production design and locked-2025 result are sealed. New model families
  and retuning are deferred research, not part of this refactor.
- EWMA/regime helpers now live in focused modules with `v2_recency` compatibility
  re-exports; point-in-time no longer imports legacy loading code.
- Maintained operational documents use current commands; historical references are
  explicitly marked as archived.

## Proposed Approach

Extract pure feature helpers while leaving backwards-compatible re-exports,
decompose preseason and weekly inference behind compatibility facades, and add an
optional, best-effort webhook notifier to failed production operations. No live
R2/Neon I/O, training, bundle publication, or model-selection activity occurs.

## Scope

### Included

- Phase 1–3 fidelity closure, documentation repair, and regression tests.
- Structural preseason and weekly-inference refactors.
- Generic optional webhook failure notifications for publish/freeze/close steps.

### Excluded

- LightGBM, ElasticNet, Optuna, any redesign of V4, or reuse of 2025 for model
  selection.
- Changes to production data, artifacts, database state, and published results.

## Affected Components and Contracts

- `cks_picks_cfb.features`: rolling EWMA and regime helpers gain focused modules;
  `v2_recency` continues to export its existing public symbols.
- `cks_picks_cfb.preseason`: remains the public facade while focused modules own
  snapshots/features, matchup assembly, and model/blend behavior.
- `cks_picks_cfb.inference.weekly`: is the testable implementation behind the
  existing `scripts/pipeline/generate_weekly_bets.py` CLI.
- Ops receives optional `CFB_OPS_ALERT_WEBHOOK_URL` and
  `CFB_OPS_ALERT_TIMEOUT_SECONDS` configuration. Missing configuration is a no-op.

## Implementation Tasks

### Task 1 — Close Phase 1–3 fidelity gaps

**Changes:**

- Add `features/rolling_ewma.py` and `features/regimes.py`; use them from
  point-in-time and production callers while retaining `v2_recency` re-exports.
- Add facade/API parity and zero-record CFBD adapter regression tests.
- Repair operational docs to use `make prepare-week`, current Silver/Gold builders,
  `make publish-week`, `publish_review.py`, and `python -m cks_picks_cfb.train`.
  Mark historical command references as archived and link the current runbook.
- Correct modernization status text to distinguish pre-existing ingestion hardening
  from the completed decomposition.

**Acceptance criteria:** Existing imports remain valid; point-in-time no longer
imports `v2_recency`; empty CFBD responses fail closed; no feature calculations
change.

### Task 2 — Phase 4 structural preseason refactor

**Changes:**

- Split `preseason.py` into `preseason_features.py`, `preseason_matchups.py`, and
  `preseason_blends.py`.
- Retain `preseason.py` as a facade exporting every existing public symbol.
- Document candidate-family/tuning work as deferred research.

**Acceptance criteria:** Preseason snapshots, matchup frames, serialized bundles,
predictions, and blend weights are equivalent under existing synthetic fixtures.

### Task 3 — Phase 5 weekly inference refactor

**Changes:**

- Create `cks_picks_cfb.inference.weekly` with prepared-input and model-context
  dataclasses plus feature preparation, model loading, regime routing, edge/lean,
  and publication-manifest functions.
- Reduce `generate_weekly_bets.py` to CLI parsing and orchestration.
- Preserve V2/V3 and compatibility paths, every CLI flag, output CSV column/order,
  coverage gate, threshold behavior, durable feature snapshot, and immutable
  artifact behavior.

**Acceptance criteria:** Synthetic golden tests cover routing, missing lines,
threshold boundaries, coverage failures, manifests, collisions, and a mocked CLI
smoke path.

### Task 4 — Optional webhook failure notifications

**Changes:**

- Add an injectable notifier to `StateMachine`.
- On failed steps in `publish-week`, `freeze-week`, and `close-week`, POST a JSON
  payload containing event, run IDs, command/environment/season/week, step,
  category, truncated detail, and timestamp.
- Notification failures only log structured diagnostics and never replace the
  original pipeline exception.

**Acceptance criteria:** Tests cover no-op configuration, success, delivery failure,
payload redaction/truncation, command scoping, and original-error preservation.

## Testing Strategy

- Focused unit, facade compatibility, and synthetic golden tests.
- `uv run pytest -q`, Ruff check/format-check, contracts validation, MkDocs build,
  `git diff --check`, and `npm run build` in `web/`.

## Risks and Edge Cases

- Keep all existing uncommitted modularization work intact.
- Treat webhook delivery as observability only; pipeline state remains fail-closed.
- Do not alter V4 chronology, 2020 exclusion, model design SHA, model bundle, or
  market feature policy.

## Definition of Done

- [x] Tasks and acceptance criteria are complete.
- [x] Required validation passes.
- [x] Documentation and implementation session log are updated.
- [x] Plan status is updated to `Implemented`.

## Amendments

### Amendment 1 — Compatibility-first inference boundary

**Reason:** The CLI retains configuration parsing, legacy data loading, and legacy
model-loading branches so its public flags and fail-closed paths remain unchanged.

**Revised approach:** The canonical inference module owns reusable prepared-input,
model-context, routing, edge/lean, and publication-manifest behavior. The CLI now
delegates its public-output and manifest construction to that module while acting
as the compatibility orchestrator.

**Impact:** No output schema, artifact, bundle, or CLI behavior changes; synthetic
tests exercise the new reusable boundary.
