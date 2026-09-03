# Session: Context Corpus and Early-Week Research Execution

## TL;DR

- **Worked On:** Preview-only offseason-context materialization and admission.
- **Outcome:** Immutable source family refs and admission diagnostics were
  written. The returning-production rejection was traced to a CFBD wire-schema
  mismatch and repaired locally; read-only validation now clears the 90%
  coverage gate for every required season. A new immutable materialization
  remains pending a committed code SHA.
- **Plan Contract:** `docs/plans/2026-09-02/early-week-strength-prior-research.md`
- **Approval / Status:** User explicitly authorized the continuation plan on
  2026-09-03. Contract remains `In Progress`.
- **Blockers:** No source-scope amendment is needed. The next materialization
  must be bound to the repair's committed code SHA before direct or R2
  experiments run.
- **Next:** Commit the approved implementation, rematerialize a fresh Preview
  context prefix, and rerun admission before direct/R2 research.

## Context and Decisions

- The certified R1 coverage report at
  `artifacts/research/rating-successor-v2/r1/r1-full-corpus-20260831-5f2a384/coverage.json`
  has `tournaments_permitted: true`; it is no longer the R2 blocker.
- Historical provider responses are captured with their actual current capture
  timestamps and are therefore reconstructed. The authentic 2026 snapshots
  are reused rather than re-fetched.
- Interrupted immutable materialization prefixes were preserved. The completed
  source manifest is
  `artifacts/research/rating-successor-v2/early-week-context-20260903-0455595-r2/source-manifest.json`.
- The corrected admission report is
  `artifacts/research/rating-successor-v2/early-week-context-20260903-0455595-r2/admission-v2-report.json`.

## Work Completed

- Added explicit unavailable-family reasons to the admission contract and CLI.
- Added the Preview-only context materializer with immutable Bronze capture,
  source-catalog registration, authentic 2026 snapshot reuse, team-universe
  construction, and idempotent family-ref recovery.
- Corrected R2 foundation lineage handling so downstream code does not need to
  share its parent’s code SHA, and restricted fold fitting to prior seasons.
- Corrected the admission guard so football `return_total_ppa` is not mistaken
  for a market field and incomplete rows flow to the explicit coverage gate.
- Repaired the CFBD returning-production adapter to accept generated-client
  camelCase wire fields (`totalPPA`, `percentPPA`, and `*Usage`) alongside the
  existing snake_case snapshot form.
- Read the already captured Preview source responses without mutation: the
  repaired features cover 91.9%–93.8% of each team universe season, clearing
  the 90% family threshold without imputation.

## Validation

- [x] Focused ratings tests: 39 passed.
- [x] Scoped Ruff.
- [x] `git diff --check`.
- [x] Focused preseason/context tests after the CFBD adapter repair: 17 passed.
- [ ] Full suite, MkDocs, direct research report, Alabama scorer, and R2 run
  are deferred by the material three-family coverage conflict.

## Amendments and Blockers

- Resolved local data mismatch: CFBD's generated Python client emits camelCase
  returning-production keys while the feature adapter accepted only snake_case.
  The prior immutable admission remains an accurate record of that old code's
  failure and cannot be overwritten. A new prefix must be materialized after
  committing the repair.

## Handoff Notes

- **Resume at:** With a committed repair SHA, materialize a fresh Preview
  context prefix and verify the expected three-family admission report before
  writing any direct/R2 research artifact.
- **Watch out for:** V4 and every production/publication surface remain
  untouched. The current context report is reconstructed and cannot support
  promotion or any strict workflow.

**tags:** ["modeling", "ratings", "preseason", "research"]
