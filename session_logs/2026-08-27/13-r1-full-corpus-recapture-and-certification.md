# Session: R1 Full-Corpus Recapture and Certification

## TL;DR

- **Worked On:** Implementing the approved capture-only R1 successor-v2 contract.
- **Outcome:** In progress.
- **Plan Contract:**
  `docs/plans/2026-08-27/r1-full-corpus-recapture-and-certification.md`
- **Approval / Status:** User explicitly authorized implementation in Codex on
  2026-08-27; contract is `In Progress`.
- **Blockers:** Live work is intentionally blocked until the R1 implementation
  is committed. Preview access is available through the repository's
  Keychain-backed wrapper and resolves to a database URL distinct from
  production.
- **Next:** Implement capture-only source sets, manifest-scoped Silver/derived
  refs, and successor-v2 measurement/state/certification interfaces.

## Context and Decisions

- R1 recaptures 2015–2019 and 2021–2025 under one Preview-only run identity.
- Standard ingesters cannot be used because their final compatibility write can
  alter legacy `raw/*` projections.
- Existing R1 weekly play capture remains a foundation but must stop rebuilding
  a compatibility projection and cover every permitted historical season.

## Work Completed

- Replaced reuse/import-based R1 planning with one full-corpus capture-only
  graph for all ten permitted seasons and five CFBD entities per season.
- Added identity-bound, sequential non-play capture workers and upgraded play
  capture to the v2 profile without compatibility projections or `raw/*` writes.
- Added run-scoped source and derived ref-set closure, manifest-only Silver
  inputs, successor true-PPSO/state configs, and an R1 foundation runner.
- Added direct immutable-ref coverage certification and the explicit two-step
  2019→2021 fixed-rho state transition.
- Added a fail-closed cross-lineage audit against an exact immutable 2019 and
  2021–2025 comparison ref set; legacy data cannot become an R1 parent.
- Amended R1 comparison evidence to resolve automatically from the Preview
  catalog and freeze a run-scoped manifest; the former URI argument is now an
  optional expert override.
- Added an explicit Preview R2/CFBD runtime gate and direct cross-lineage
  conflict coverage before the automatic evidence bootstrap.
- Bound the live R1 preflight to a clean committed implementation path list:
  any untracked or modified R1 code now fails before migration, catalog reads,
  or capture writes.
- Updated the R1 operational runbook and focused tests.

## Files Modified

- `docs/plans/2026-08-27/r1-full-corpus-recapture-and-certification.md`
- `session_logs/2026-08-27/13-r1-full-corpus-recapture-and-certification.md`
- `src/cks_picks_cfb/data/history_source_capture.py`
- `src/cks_picks_cfb/data/history_play_capture.py`
- `src/cks_picks_cfb/ops/__main__.py`
- `src/cks_picks_cfb/ratings/`
- `scripts/pipeline/build_successor_history_ref_set.py`
- `scripts/pipeline/build_successor_r1_foundation.py`
- `scripts/pipeline/certify_successor_history.py`

## Validation

- [x] Focused data/catalog/ops/ratings tests (52 passed after automatic
  comparison-evidence bootstrap wiring).
- [x] Full Python suite: `561 passed, 2 skipped`.
- [x] Repository-wide Ruff, contract validation, strict MkDocs, and CLI smoke
  checks.
- [x] Full pytest: `561 passed, 2 skipped`.
- [x] `git diff --check`.

## Amendments and Blockers

- No amendment. Preview data operations remain deferred only by the required
  committed-code identity. The existing `scripts/ops/with_preview_env.sh`
  wrapper provides isolated Preview database credentials, Preview R2
  credentials, and CFBD access; the resolved Preview database URL differs from
  the production URL. No migration or capture was attempted against an
  uncommitted implementation.

## Handoff Notes

- **Resume at:** Commit the implementation, then invoke the R1 command through
  `scripts/ops/with_preview_env.sh`; it will resolve and freeze legacy
  comparison evidence automatically, so an explicit URI is unnecessary.
- **Watch out for:** Never call compatibility writes for recaptured sources;
  never treat previous source refs as successor-v2 parents.

**tags:** ["r1", "historical-data", "immutable-lake", "preview"]
