# Session: R1 Full-Corpus Recapture and Certification

## TL;DR

- **Worked On:** Implementing the approved capture-only R1 successor-v2 contract.
- **Outcome:** Terminally blocked before capture by missing required 2019
  comparison evidence; the immutable failure report is published.
- **Plan Contract:**
  `docs/plans/2026-08-27/r1-full-corpus-recapture-and-certification.md`
- **Approval / Status:** User explicitly authorized implementation in Codex on
  2026-08-27; contract is `In Progress`.
- **Blockers:** Preview catalog has zero validated legacy 2019 artifacts.
  Exact legacy `games`, `game_outcomes`, and `teams` comparison refs must be
  restored and catalog-validated; R1 may not substitute them.
- **Next:** After that restoration, start a new committed R1 run through the
  Preview wrapper; the automatic bootstrap will gate the full capture again.

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
- Applied Preview migration `0009` after proving Preview and migration URLs are
  distinct credentials on the isolated Preview branch.
- Passed the read-only 2015 Week 1 CFBD probe at exactly 15,369 plays.
- Started the full-corpus run `r1-full-corpus-20260827-1d57c10`; its comparison
  bootstrap stopped before capture because Preview contains no validated 2019
  legacy catalog artifacts. Added a terminal immutable failure diagnostic for
  this required pre-capture condition.
- Published and checksum-verified
  `artifacts/research/rating-successor-v2/r1/r1-full-corpus-20260827-95b0456/comparison-ref-set.failure.json`.
  Catalog verification confirmed that the blocked run created zero source
  capture child runs.
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
- [x] Focused failure-diagnostic regression: 29 passed.
- [x] `git diff --check`.

## Amendments and Blockers

- No amendment. Preview migration `0009` and the required compatibility probe
  completed. The catalog-bootstrap preflight found zero validated 2019 legacy
  artifacts, so R1 stopped before successor capture as required. The revised
  bootstrap now emits an immutable run-scoped failure diagnostic for this
  terminal evidence condition.
- A read-only source inventory confirmed that the exact legacy 2019 archives
  still exist outside the Preview catalog: `raw/games/year=2019/data.csv`
  (848 rows, SHA-256 `127b0a201b7793d25159a02ecfa29d83f46f40a6899106bb7f61438e660e3db5`),
  `raw/teams/year=2019/data.parquet` (130 rows, SHA-256
  `655b71a08c510f95db9e81cc6c21aca4052dac889cf8e17cbb00d130ce294c22`),
  and the associated venues and plays. Games include final scores. Restoring
  those exact archives as cataloged *legacy comparison* refs would be a new
  lineage operation and requires its own approval; it is not a substituted
  successor capture.

## Handoff Notes

- **Resume at:** Restore and catalog-validate exact legacy 2019 `games`,
  `game_outcomes`, and `teams` refs. Then start a fresh committed R1 run
  through `scripts/ops/with_preview_env.sh`; its auto-bootstrap remains the
  first gate.
- **Watch out for:** Never call compatibility writes for recaptured sources;
  never treat previous source refs as successor-v2 parents.

**tags:** ["r1", "historical-data", "immutable-lake", "preview"]
