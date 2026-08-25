# Session: Phase 3 V4 Benchmark Recovery Materialization

## TL;DR

- **Worked On:** Materialized the committed V4 historical benchmark recovery in
  Preview and certified its immutable rerun.
- **Outcome:** The recovery contract is Implemented. Phase 3's V4-comparison
  prerequisite is satisfied; the Phase 3 foundation review is next.
- **Plan Contract:** `docs/plans/2026-08-25/phase3-v4-benchmark-recovery.md`
- **Approval / Status:** The user explicitly requested the commit and Preview
  recovery on 2026-08-25.
- **Blockers:** None for the Phase 3 foundation review. Phase 3 remains In
  Progress and has not begun prediction construction.
- **Next:** Implement the separately approved Phase 3 foundation review and
  structured prediction baseline contract.

## Context and Decisions

- The first materialization attempt exposed two compatibility differences with
  the pinned V4 engine: the established replay imported a module absent at
  `33432e8`, and recovery rejected null candidate placeholders that V4's frozen
  evaluator drops before scoring.
- Corrections were committed as `12cc6e9` and `a8827bf` before the successful
  Preview write. The recovery engine still runs from pinned commit
  `33432e81465aea67206df938cf48182b3684add9`.
- Both corrections preserve the frozen routing and metrics; they do not tune,
  reselect, or otherwise alter V4.

## Work Completed

- Committed `a8827bf` (`fix(ratings): replay V4 candidate null semantics`).
- Ran Preview recovery at cutoff `2026-08-25T13:23:26Z`, run
  `2026-08-25T1323Z-v4-recovery`.
- Materialized `rating_v4_historical_predictions_v1` version
  `f4ec062c7f931f125ce6be99`, content SHA
  `6bdbe75ce83554c5828ac1a807056e26844db44c77defb6607d2ec7386efca2d`.
- Verified the passing audit SHA
  `f601ba9d24becc07019d0bfb97e6d8ed74801eaae3da89f2148e52dbfd821538` and
  manifest SHA
  `4c20a1deab68a5994575c84cdedc00a418e12a3b364a66feae2151810b2a9f2b`.
- Repeated the exact run; it returned the same ref, content SHA, and audit SHA.

## Validation

- [x] `uv run pytest tests/ratings -q` -- 74 passed.
- [x] Focused Ruff format/check -- passed.
- [x] Preview audit -- all six checks pass, including temporal integrity,
  complete paired coverage, frozen early-route parity, and derived established
  labeling.
- [x] Preview rerun -- byte-identical immutable ref and audit.
- [x] `git diff --check` -- to be rerun with the documentation record.

## Handoff Notes

- **Resume at:** Phase 3 foundation review using only pregame team states
  `1fdcb1ca6d235bf2ecf87414` and the certified V4 comparison ref above.
- **Watch out for:** Preserve `source_kind`; established V4 rows remain
  `derived_compatibility_replay`. No market, production, Neon, or public work
  is authorized.

**tags:** ["ratings", "phase3", "v4", "preview", "research-isolation"]
