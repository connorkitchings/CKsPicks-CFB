# Session: Phase 1 Bounded-Memory Materialization Fix

## TL;DR

- **Worked On:** Replaced the Phase 1 Preview measurement builder's
  all-history raw-frame load with a season-scoped observation build after the
  materialization terminated as a raw-data resource failure.
- **Outcome:** Phase 1 v2 now materializes with bounded memory from committed
  code (`48c0f11`); the authoritative bounded build passed every audit check
  and reproduced byte-for-byte on rerun. Phase 2 remains unchanged and is
  unblocked for its own Task 4 run.
- **Plan Contract:** `docs/plans/2026-08-24/phase1-phase2-completion.md`
  (Task 3 completed via Amendment 1)
- **Approval / Status:** User authorized the bounded-materialization fix on
  2026-08-25, including committing the builder and tests before the next
  Preview write.
- **Blockers:** None.
- **Next:** Run Phase 2 `build_rating_team_states.py` in Preview against the
  bounded Phase 1 refs (completion-contract Task 4), then close records.

## Context and Decisions

- The termination was treated as raw-data materialization fragility: the CLI
  previously concatenated all five seasons of byplay (~627k rows) and drives
  (~128k rows) before any aggregation.
- Raw parents are now mapped from their manifest `partitions.seasons`;
  exactly one byplay and one drives parent is required per historical
  development season, duplicates/missing/protected-season parents fail before
  any raw parquet read, and each loaded frame must agree with its manifest
  season.
- Dataset identity still uses the full 14-ref recovered parent set and the
  original `2026-08-24T18:30:00Z` cutoff; parent order was recovered from the
  superseded build's observations manifest (drives refs were not
  season-ordered).
- The audit report gained an `execution` section (materialization mode, raw
  rows by dataset/season, observation rows per season, stage timings).
  Wall-clock timings are excluded from report identity so immutable rerun
  equality stays verifiable; report collisions on any other difference still
  fail loudly.
- v2 snapshot semantics confirmed: evidence is same-season only, so 2026
  targets are explicit `no_eligible_evidence` prior-free states (28,454
  missing snapshot rows) pending authentic in-season observations; prior
  carryover is Phase 2's terminal-state job.

## Work Completed

- Refactored `scripts/pipeline/build_rating_measurements.py`: `_manifest_seasons`,
  `_season_parent_maps`, `_concat_frames`, and
  `_build_observations_season_scoped` (progress-instrumented, per-season
  read→build→release, canonical global re-sort of concatenated outputs);
  timing-tolerant immutable report write.
- Tests: `tests/ratings/test_season_scoped.py` (equivalence with the
  all-at-once builder, one-season-at-a-time sequencing, missing/duplicate/
  protected-season parents failing before raw reads, CLI end-to-end 2026
  prior-only states, report identity timing exclusion); `helpers.py`
  `multi_season_league` + `stage_rating_parents`; `test_cli.py` moved to
  per-season staged parents (63 ratings tests total).
- Committed builder + tests + ratings formatting drift as `48c0f11` before
  the Preview write; worktree clean at run time (committed-code gate active).
- Preview build `runs/2026-08-24T2000Z-bounded/` from the recovered lineage:
  passing audit, then byte-identical same-stamp rerun.
- Docs: measurement catalog authoritative v2 disposition updated with the
  bounded-build refs; completion contract Amendment 1 recorded.

## Files Modified

- `scripts/pipeline/build_rating_measurements.py` — season-scoped bounded materialization, execution diagnostics, report identity handling.
- `src/cks_picks_cfb/ratings/`, `src/cks_picks_cfb/data/schema_contracts.py` — formatting drift only (two are committed-code-gated paths).
- `tests/ratings/{helpers,test_cli,test_season_scoped}.py` — fixtures and coverage for the bounded path.
- `docs/modeling/measurement_catalog.md`, `docs/plans/2026-08-24/phase1-phase2-completion.md` — authoritative refs and amendment.

## Validation

- [x] `tests/ratings/` — 63 passed
- [x] Full Python suite — 477 passed, 2 skipped
- [x] `uv run ruff format` + `ruff check` — clean
- [x] `uv run python contracts/validation.py` + `make contracts-check` — passed
- [x] Strict MkDocs build — passed
- [x] `git diff --check` — clean
- [x] Preview bounded build: all 13 audit checks pass; byte-identical rerun
- [x] Parity vs all-at-once build: 96,954 / 116,792 / 8,632 rows, coverage,
      redundancy, and historical exclusions identical

## Preview Artifacts (authoritative, bounded)

- Design `340091b61f45c272f02658b1d2ad670116c6d57d2c182792ce817546c8ca481b`,
  cutoff `2026-08-24T18:30:00Z`, code `48c0f113879787e0134555f58d709c7b7e98a45e`.
- Observations `2d167baa0be6f79eb3fad0ed`, snapshots
  `3163c5e6a18cc01a30542cb2`, terminal `8ccf480cb367e3124086cd69`; report
  identity SHA `a5441b37b65a4151907e8d7fbff5359e8b358cdafa003f942da80b590f248d25`.
- Diagnostics: per-season byplay 124,513–126,332 rows; drives 25,261–25,873;
  observations 19,032–19,786; stage timings read 1.9s / observation build
  5.3s / snapshot build 327.9s / terminal build 4.5s / audit 0.3s.

## Amendments and Blockers

- Completion-contract Amendment 1 (bounded materialization) recorded; no
  material deviation from the fix's scope.

## Handoff Notes

- **Resume at:** Completion-contract Task 4 — Phase 2 state build in Preview
  consuming exactly the bounded Phase 1 refs above.
- **Watch out for:** Phase 2 must not consume superseded v1 or all-at-once
  1830Z refs; Week 0 production operations take precedence over any research
  run; no production, Neon, V4, market, or public change is authorized.

**tags:** ["ratings", "phase1", "materialization", "preview", "bounded-memory"]
