# Session: Phase 1 Correction and Phase 2 Implementation (through 2b)

## TL;DR

- **Worked On:** Corrected the Phase 1 evidence audit under Phase 2 Amendment 2,
  validated and committed the standing Phase 2 tooling, executed the corrected
  audit v3, completed Phase 2a deterministic catalog repair, and executed
  Phase 2b bounded capture (pregame rehearsal + historical postseason capture).
- **Outcome:** Corrected audit sealed (`complete_with_blockers`, 70 issues);
  all 53 registration-gap dataset versions registered in the Preview catalog
  with zero quarantines; 10 postseason capture requests executed; pregame
  rehearsal (7/7) successful. Phase 2c Silver rebuild is next.
- **Plan Contract:** `docs/plans/2026-09-05/02-data-repair-and-recertification.md`
- **Approval / Status:** User approved the replacement plan and directed
  implementation on 2026-09-05; contract is In Progress (2a + 2b done).
- **Blockers:** None. Two visible audit blockers remain by design.
- **Next:** Phase 2c Silver rebuild — `fbs_involved_games` + expanded datasets
  for all 10 seasons.

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
- **Mixed column conventions:** Production ingestion stores snake_case
  (`start_date`, `home_classification`); isolated research captures keep
  raw provider camelCase (`startDate`, `homeClassification`). Concatenating
  both in Silver builds produced twin columns with per-row NaNs. Fix:
  `_rename_common` now coalesces camelCase aliases into snake_case twins —
  no-op for single-convention builds.
- Never treat catalog absence as proof that an immutable R2 object is missing;
  never collapse distinct `as_of` observations.

## Work Completed

- Validated the standing uncommitted implementation: ruff format/check,
  focused tests (46), full suite with coverage gate, `make contracts-check`,
  mkdocs build, `git diff --check`. All green.
- Commits (user-executed): `8d0c1ad` (Amendment 2 authority docs),
  `f77dd21` (corrected audit + Phase 2 tooling), `052486c`
  (historical rating schema registration + null-sha tolerance),
  `718e78a` (session closeout), `86ec84d` (runbook v3 audit pin),
  `64879e2` (camel/snake coalesce fix).
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
- **Phase 2b pregame rehearsal** — 7/7 requests captured (games, returning
  production, coaching, 4 recruiting years), all first-attempt, registered in
  Preview Neon with authentic pregame timestamps. GHA cron variable
  `CFB_DATA_FIRST_CAPTURE_SCHEDULE_ENABLED=true` can now be enabled.
- **Phase 2b historical capture** — 10/10 postseason `/games` requests
  captured across 10 seasons (2015–2019, 2021–2025), ~415 games, all
  first-attempt, registered in Preview Neon under entity `data_first_games`.
- **Phase 2c start** — Identified and fixed the mixed camelCase/snake_case
  column convention bug in `_rename_common` that blocked `fbs_involved_games`
  builds when concatenating production (snake_case) and research (camelCase)
  captures. Added coalescing logic + regression tests.

## Files Modified

- `src/cks_picks_cfb/data/schema_contracts.py` - version-aware rating schema
  registry; 12 historical combos; 4 new dataset schemas
- `src/cks_picks_cfb/data/catalog.py` - null-`schema_sha` historical manifest
  tolerance in `register_dataset_version`
- `src/cks_picks_cfb/data/silver/builders.py` - `_coalesce_camel_aliases`
  helper in `_rename_common` to merge camelCase aliases into snake_case twins
- `src/cks_picks_cfb/data/silver/builders.py` - added `_snake_case` helper
- `tests/test_schema_contracts.py` - historical version resolution + unknown
  version error contract
- `tests/test_catalog_offline.py` - null-sha registration succeeds; sha drift
  still rejected
- `tests/test_silver_reconciliation.py` - regression tests for mixed
  camelCase/snake_case provenance in `normalize_fbs_involved_games` and
  `normalize_games`
- `docs/ops/data_first_capture.md` - pinned `<corrected-run>` placeholder to
  v3 audit prefix
- `docs/plans/2026-09-05/02-data-repair-and-recertification.md` - Phase 2a/2b
  completion record
- `session_logs/2026-09-05/05-phase1-correction-and-phase2-implementation.md`

## Validation

- [x] Focused tests: `tests/test_schema_contracts.py`,
  `tests/test_catalog_offline.py`, `tests/test_silver_reconciliation.py`
  (17 + 24 = 41 passed)
- [x] Full test and coverage gate: 704 passed, 2 skipped, 66.03% (gate 60%)
- [x] `uv run ruff format --check` / `uv run ruff check` on changed files
- [x] `make contracts-check`, `uv run mkdocs build --quiet`
- [x] V4 compatibility: all schema additions are research-only dataset names;
  production dataset contracts untouched; full suite green
- [x] `git diff --check`
- [x] Post-repair Neon confirmation: 53/53 version_ids present
- [x] Phase 2b: 17/17 capture requests successful; all registered in Preview
  Neon

## Amendments and Blockers

- Amendment 2 executed as written; no further amendment needed. The
  null-`schema_sha` tolerance and camel/snake coalesce were implemented as
  part of Phase 2a/2c deterministic repair (research-scoped, drift checks
  preserved).
- Remaining visible blockers (by design, never weakened): 2 unresolved-lineage
  issues for non-canonical research parquet URIs; postseason-capture-gap
  resolved (2b); silver-fbs-fcs-exclusion critical awaits 2c.
- Cosmetic: pandas FutureWarnings during audit stage
  (`audit_data_first_evidence.py:1020`, `:1249`) — non-blocking; address in a
  later maintenance pass (fixing them now would change the audit code SHA).

## Handoff Notes

- **Resume at:** Phase 2c Silver rebuild — build `fbs_involved_games` for all
  10 seasons (2015–2019, 2021–2025) using paired regular + postseason Bronze
  captures, then expanded `game_outcomes`, `plays`, `team_game_stats`,
  `reconciled_team_game`. Regular-season Bronze captures exist for all
  target years; postseason captures are the 10 newly registered captures
  under entity `data_first_games`.
- **Watch out for:** apply-mode CLIs pin `--expected-code-sha` to committed
  HEAD — commit before executing. CFBD quota check runs before captures; keep
  `--max-requests` bounds explicit. 2020 remains forbidden everywhere.
- **Build-silver mechanism:** use `python -m cks_picks_cfb.ops build-silver`
  with multiple `--capture-id` (regular + postseason per year), `--environment
  preview`, `--as-of` pinned.

**tags:** ["data-first", "phase1", "phase2", "repair", "recertification"]