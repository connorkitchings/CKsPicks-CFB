# Phase 1 and Phase 2 Completion Contract

- **Status:** In Progress
- **Created:** 2026-08-24
- **Planner:** Sol
- **Approval source:** User explicitly authorized this exact contract on 2026-08-24.
- **Implementation log:** `session_logs/2026-08-24/04-phase1-phase2-completion.md`
- **Commit policy:** A separate code commit is required before Preview artifact materialization; documentation closure follows successful audits.

## Goal

Complete the two in-progress rating phases before Phase 3 by hardening their
evidence gates, materializing immutable Preview artifacts from committed code,
and recording authoritative refs and checksums.

## Current State

Phase 1 remediation and Phase 2 estimator code are committed at `cba1577`, but
their artifacts are not materialized. The existing audits do not yet fully
express the approved exit gates, and terminal identities omit the team suffix.
V4, production, Neon, public publication, markets, and predictions are out of
scope.

## Proposed Approach

Harden and test audit gates first, commit the relevant source, recover the
exact v1 parent lineage and cutoff, and then run Phase 1 followed by Phase 2
only in Preview R2. Reuse the v1 parents to isolate remediation effects. Zero
authentic 2026 completed-game observations are acceptable when none exist at
the recovered cutoff; authentic timing enforcement remains mandatory.

## Scope

### Included

- Phase 1 audit lineage, evidence, identity, adjustment, temporal, and
  fail-closed checks.
- Phase 2 terminal IDs, audit gates, attribution, coverage, uncertainty, and
  fail-closed checks.
- Preview-only immutable Phase 1 v2 and Phase 2 artifact materialization,
  idempotency verification, and documentation closure.

### Excluded

- Predictions, markets, V4 changes, public or database interfaces, catalog
  registration, Neon activation, publication, and Phase 3 work.

## Implementation Tasks

### Task 1 — Harden audit contracts

- Make Phase 1 audit inspect all three output frames; record full parents,
  cutoff, code/config lineage; verify remediation invariants and reject v1
  versions.
- Make Phase 2 use `terminal:{season}:{team}` and emit a pass/fail audit for
  complete team coverage, component attribution, prior carryover,
  standardization, uncertainty behavior, missing evidence, forbidden inputs,
  stable identity, and lineage.
- Add descriptive distributions, ordinal weights, contraction, movements,
  missingness/flags, and EPA/success correlation.
- Write successful ref files only after the relevant audit passes.

### Task 2 — Validate and commit audit code

- Add focused tests for every new gate and failure mode.
- Run ratings tests, full Python tests, Ruff, contract validation, strict
  MkDocs, and diff checks.
- Commit the relevant source/configuration paths before any Preview write.

### Task 3 — Materialize Phase 1 v2

- Recover the parent refs and cutoff from the immutable manifest for superseded
  observation version `b1da5e85a0438fab109937bf`.
- Use design ID `340091b61f45c272f02658b1d2ad670116c6d57d2c182792ce817546c8ca481b`
  and run-stamped measurement paths. Do not register catalog metadata.
- Verify a passing audit and byte-identical rerun.

### Task 4 — Materialize Phase 2

- Consume only the passing Phase 1 refs/audit, with state design ID
  `ddd6033824909620aa381527dba202a06c65155de53403849b59ffcaaae7092d`.
- Verify a passing audit and byte-identical rerun under the isolated state
  prefix. Do not register catalog metadata.

### Task 5 — Close records

- Update the Phase 1 remediation and Phase 2 baseline contracts to
  `Implemented` only after their audits pass; retain the original foundation as
  `Superseded`.
- Record refs, checksums, cutoff, code/config IDs, row counts, coverage,
  missingness, and limitations in active modeling docs and roadmap.
- Create the implementation session log.

## Validation

- Focused audit, state, and CLI failure-mode tests; full `uv run pytest -q`.
- `uv run ruff format --check` and `uv run ruff check` on changed Python.
- `uv run python contracts/validation.py`, `make contracts-check`, strict
  MkDocs, and `git diff --check`.
- Confirm Preview credentials without exposing values, committed-code identity,
  Preview research prefixes, audit pass status, and immutable rerun equality.

## Definition of Done

- [ ] Hardened audits and terminal identity pass all tests.
- [ ] Phase 1 v2 artifacts reproduce from the recovered parent lineage and pass.
- [ ] Phase 2 artifacts reproduce from exactly those Phase 1 refs and pass.
- [ ] Reruns are byte-identical; no production, Neon, V4, market, or public change occurred.
- [ ] Docs, session log, and phase statuses are updated; Phase 3 has not begun.

## Amendments

1. **Task 3 bounded materialization (2026-08-25).** The Phase 1 Preview
   materialization terminated as a raw-data resource failure under the
   all-history byplay/drives load. Task 3 was completed with a season-scoped
   builder (commit `48c0f11`, committed before any Preview write per policy):
   raw parents are mapped from manifest season partitions with exactly one
   byplay and one drives parent per historical season, missing/duplicate/
   protected-season parents fail closed before any raw read, only compact
   per-season observation outputs persist across seasons, and the audit
   report records execution diagnostics (raw rows by dataset/season,
   observation rows per season, stage timings excluded from report
   identity). The authoritative passing build is
   `runs/2026-08-24T2000Z-bounded/` at cutoff `2026-08-24T18:30:00Z` from
   the recovered 14-ref parent lineage staged under
   `runs/2026-08-24T1830Z/inputs/`: observations `2d167baa0be6f79eb3fad0ed`,
   snapshots `3163c5e6a18cc01a30542cb2`, terminal `8ccf480cb367e3124086cd69`,
   report identity SHA
   `a5441b37b65a4151907e8d7fbff5359e8b358cdafa003f942da80b590f248d25`; a
   same-stamp rerun reproduced every version and the identity byte-for-byte.
   Totals, coverage, redundancy, and historical exclusions match the prior
   all-at-once builds; Phase 2 (Task 4) is unblocked but unchanged.
