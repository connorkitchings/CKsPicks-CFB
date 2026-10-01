# Session: Historical expansion and ratings methodology reset

## TL;DR

- **Worked On:** Implemented the governing R1–R4 research contracts and
  rewired active documentation from an ambiguous phase sequence to research
  (R1–R4) and operations (O1–O3) tracks.
- **Outcome:** V4 remains unchanged O1 production. Candidate v1 at `ac1fba1`
  is explicitly O2 diagnostic-only. Successor-v2 has centralized season
  lineage, Preview-only historical preparation/certification interfaces,
  sealed tournament contracts, and a fresh v2 prospective policy/manifest.
- **Plan Contract:**
  `docs/plans/2026-08-26/historical-expansion-ratings-methodology-reset.md`
- **Approval / Status:** User authorized the exact plan on 2026-08-26;
  governing plan/log were committed separately as `6d09543`. Implementation
  remains In Progress.
- **Blockers:** Historical capture and measurement/state rebuild have not yet
  been run. The final non-secret configuration check found
  `PREVIEW_DATABASE_URL`, `DATABASE_URL`, `CFB_STORAGE_BACKEND`, and all R2
  credential variables absent from this shell; no data operation was attempted.
  A configured Preview environment must certify the new corpus before R2
  metrics can be materialized.
- **Next:** Run the R1 Preview-only history preparation, construct true-PPSO
  measurements/states under successor-v2 identities, then certify the exact
  ref set and coverage report before executing R2.

## Context and Decisions

- Historical development is exactly 2015–2019 and 2021–2025. 2020 is rejected
  at source scope, lineage policy, coverage certification, and tournament
  boundaries. 2026 remains protected from development inputs.
- 2015 is the terminal-state seed. Normal transitions exclude 2019→2021;
  that transition is explicitly a two-application annual-decay gap and is not
  a normal-transition fitting example.
- The shared R2 bucket is intentional. Immutable artifact namespaces and
  distinct Preview/production Neon branches are the isolation boundary. The
  Week 1 failed run was caused by unavailable Week 0 plays, not R2 isolation.
- Preseason context is admitted only with semantic preseason meaning,
  reconstructibility without outcome leakage, 90% coverage in every required
  fold, authenticated pre-kickoff 2026 capture, and football-only columns.
  Market-like columns remain diagnostic-only.

## Work Completed

- Added `conf/ratings/successor_v2_season_lineage.yaml` and the central
  `SeasonLineagePolicy` contract.
- Extended historical scope to support 2015–2019 research while retaining V4's
  sealed 2021–2025 production lineage and universal 2020 rejection.
- Added Preview-only `prepare-rating-history` operations: 2015–2018 CFBD
  capture, 2019 archive import, isolated successor-v2 Silver outputs, and
  reconciled team-game outputs.
- Added checksummed R1 history-ref-set and coverage-report construction,
  including the stop condition of three qualifying 2015–2019 seasons.
- Added sealed R2/R3/R4 candidate rosters, exact temporal folds, tie/fallback
  rules, context admission boundary, Games 1–3 paired-bootstrap gate (2,000
  samples, seed 42), locked-2025 condition, and immutable tournament report
  runner.
- Added a v2-only prospective policy and candidate manifest that blocks v1
  evidence transfer and retrospective freezes.
- Reworked roadmap, index, root docs, context, AGENTS, evaluation,
  measurement/early-season docs, and runbooks to make the new tracks current.

## Files Modified

- `conf/ratings/successor_v2_*.yaml` — lineage, sealed tournaments, and v2
  prospective policy.
- `src/cks_picks_cfb/data/season_lineage.py` — fail-closed historical policy.
- `src/cks_picks_cfb/ratings/successor_*.py` — R1 certification, context
  admission, R2–R4 mechanics, and candidate-v2 manifest contracts.
- `src/cks_picks_cfb/ops/__main__.py` — Preview-only historical preparation
  operation.
- `scripts/pipeline/certify_successor_history.py` and
  `scripts/pipeline/run_successor_tournament.py` — immutable contract CLIs.
- `docs/ops/rating_successor_research.md` — operator procedure.

## Validation

- [x] `uv run pytest -q tests/ratings/test_season_lineage.py tests/ratings/test_successor_history.py tests/ratings/test_successor_tournaments.py tests/ratings/test_successor_manifest.py tests/test_history_bootstrap.py tests/test_ops_state_machine.py` — 33 passed.
- [x] CLI help smoke tests for `prepare-rating-history`, R1 certification, and
  R2–R4 tournament report runner.
- [x] Scoped Ruff check/format for the changed Python modules and tests.
- [x] `uv run mkdocs build --strict --quiet`.
- [x] `uv run pytest -q` — 547 passed, 2 skipped.
- [x] `uv run python contracts/validation.py`.
- [x] `git diff --check`.

## Amendments and Blockers

- No plan amendment. The active work has intentionally not run a historical
  backfill or any 2026 evidence operation: the Preview/R2 configuration check
  failed closed because required variables are absent from this shell.

## Handoff Notes

- **Resume at:** Validate the full worktree, commit this implementation slice,
  then run R1 from `docs/ops/rating_successor_research.md` only after verifying
  Preview connectivity and credentials.
- **Watch out for:** Do not use `import-history` as a substitute for
  `prepare-rating-history`; do not write successor artifacts under existing
  Phase 1–5 prefixes; do not use 2020, market data, or protected 2026 outcomes
  in research.

**tags:** ["ratings", "history", "lineage", "research", "operations"]
