# Session: Phase 1 Correction and Phase 2 Implementation

## TL;DR

- **Worked On:** Corrected the Phase 1 evidence audit under Phase 2 Amendment 2,
  validated and committed the standing Phase 2 tooling, executed the corrected
  audit v3, and completed Phase 2a deterministic catalog repair.
- **Outcome:** Corrected audit sealed (`complete_with_blockers`, 70 issues);
  all 53 registration-gap dataset versions registered in the Preview catalog
  with zero quarantines. Phase 2b (bounded capture) is next.
- **Plan Contract:** `docs/plans/2026-09-05/02-data-repair-and-recertification.md`
- **Approval / Status:** User approved the replacement plan and directed
  implementation on 2026-09-05; contract is In Progress (Phase 2a done).
- **Blockers:** None. Two visible audit blockers remain by design (see below).
- **Next:** Phase 2b bounded capture in a fresh task (historical dry-run first,
  then pregame rehearsal per `docs/ops/data_first_capture.md`).

## Context and Decisions

- Preserve V4 production behavior and all pre-existing worktree content.
- The unrelated untracked `.opencode/` directory is outside scope (excluded
  from every commit, per user direction).
- Amendment 2 supersedes Amendment 1; the sealed v2 audit is historical
  evidence, not repair authority.
- **Schema-registry root cause:** 43 of 53 registration gaps were sealed under
  schema versions the executable registry never learned. The lake write path
  tolerates unknown versions and records `schema_sha: null`, leaving objects
  writable but unregistrable. The fix registers 12 historical
  (dataset, version) combos — 7 derived from existing sealed column contracts,
  4 new datasets derived from writer constants and the sealed objects' parquet
  columns — and makes `register_dataset_version` tolerate `schema_sha: null`
  for historical manifests (recorded shas still drift-check; regression test
  proves mismatched shas still raise). Research-scoped; no V4 dataset touched.
- Never treat catalog absence as proof that an immutable R2 object is missing;
  never collapse distinct `as_of` observations.

## Work Completed

- Validated the standing uncommitted implementation: ruff format/check,
  focused tests (46), full suite with coverage gate, `make contracts-check`,
  mkdocs build, `git diff --check`. All green.
- Commits (user-executed): `8d0c1ad` (Amendment 2 authority docs),
  `f77dd21` (corrected audit + Phase 2 tooling), `052486c`
  (historical rating schema registration + null-sha tolerance).
- Corrected Phase 1 audit v3 resolve stage sealed:
  `artifacts/research/data-first-football-v1/phase1/2026-09-06T0055Z-phase1-evidence-audit-v3/resolved-evidence-manifest.json`
  (`resolved_with_blockers`; 208 datasets, 5,152 captures, 534 lineage edges;
  53 registration gaps with checksum-verified objects; 2 blockers are
  non-canonical research parquet URIs that can never register and remain
  visible unresolved-lineage issues).
- Corrected Phase 1 audit v3 audit stage sealed (12 outputs, same prefix):
  `complete_with_blockers`, 70 issues (2 critical: postseason-capture-gap →
  2b, silver-fbs-fcs-exclusion 1,144 games → 2c; 53
  catalog-registration-missing; 10 dataset-correctness; 3
  downstream-game-outside-denominator; 2 unresolved-lineage), 5 result
  dispositions with exact reasons.
- Phase 2a catalog repair executed and sealed:
  `artifacts/research/data-first-football-v1/phase2/catalog-repair/2026-09-06T0055Z-catalog-repair/repair-report.json`
  — 53 registered, 0 quarantined, independently confirmed in Preview Neon
  `catalog.dataset_versions`. First apply attempt surfaced the schema-registry
  defect (fixed in `052486c`); registration is idempotent
  (`ON CONFLICT DO NOTHING`), so the re-run after the fix converged cleanly.
- Empirical verification: all 53 sealed gap objects pass `validate_frame`
  against the newly registered schemas.

## Files Modified

- `src/cks_picks_cfb/data/schema_contracts.py` - version-aware rating schema
  registry; 12 historical combos; 4 new dataset schemas
- `src/cks_picks_cfb/data/catalog.py` - null-`schema_sha` historical manifest
  tolerance in `register_dataset_version`
- `tests/test_schema_contracts.py` - historical version resolution + unknown
  version error contract
- `tests/test_catalog_offline.py` - null-sha registration succeeds; sha drift
  still rejected
- `docs/plans/2026-09-05/02-data-repair-and-recertification.md` - Phase 2a
  completion record
- `session_logs/2026-09-05/05-phase1-correction-and-phase2-implementation.md`

## Validation

- [x] Focused tests: `tests/test_schema_contracts.py`,
  `tests/test_catalog_offline.py` (17 passed)
- [x] Full test and coverage gate: 702 passed, 2 skipped, 66.00% (gate 60%)
- [x] `uv run ruff format --check` / `uv run ruff check` on changed files
- [x] `make contracts-check`, `uv run mkdocs build --quiet` (pre-change run;
  re-verified after doc edits)
- [x] V4 compatibility: schema additions are research-only dataset names;
  production dataset contracts untouched; full suite green
- [x] `git diff --check`
- [x] Post-repair Neon confirmation: 53/53 version_ids present

## Amendments and Blockers

- Amendment 2 executed as written; no further amendment needed. The
  null-`schema_sha` tolerance was implemented as part of Phase 2a
  deterministic repair (research-scoped, drift checks preserved).
- Remaining visible blockers (by design, never weakened): 2 unresolved-lineage
  issues for non-canonical research parquet URIs; postseason-capture-gap and
  silver-fbs-fcs-exclusion criticals await 2b/2c.
- Cosmetic: pandas FutureWarnings during audit stage
  (`audit_data_first_evidence.py:1020`, `:1249`) — non-blocking; address in a
  later maintenance pass (fixing them now would change the audit code SHA).

## Handoff Notes

- **Resume at:** Phase 2b bounded capture in a fresh Terra task. Start with
  the historical dry-run against the v3 schedule denominator
  (`artifacts/.../2026-09-06T0055Z-phase1-evidence-audit-v3/schedule-denominator.parquet`),
  then the one-shot pregame rehearsal (7 requests) per
  `docs/ops/data_first_capture.md`; the runbook's `<corrected-run>` placeholder
  can now be pinned to the v3 audit prefix.
- **Watch out for:** apply-mode CLIs pin `--expected-code-sha` to committed
  HEAD — commit before executing. CFBD quota check runs before captures; keep
  `--max-requests` bounds explicit. 2020 remains forbidden everywhere.

**tags:** ["data-first", "phase1", "phase2", "repair", "recertification"]
