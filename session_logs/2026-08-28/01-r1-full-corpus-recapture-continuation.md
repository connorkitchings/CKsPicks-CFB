# Session: R1 Full-Corpus Recapture Continuation

## TL;DR

- **Worked On:** Continued the approved capture-only R1 successor-v2 recapture.
- **Outcome:** Active immutable run `r1-full-corpus-20260828-929f331` is healthy
  and had reached 2015 plays at close. The R1 parent contract remains In Progress.
- **Plan Contract:** `docs/plans/2026-08-27/r1-full-corpus-recapture-and-certification.md`
- **Approval / Status:** User approved continued implementation and session
  closeout on 2026-08-28.
- **Blockers:** R2 remains blocked until R1 certification passes.
- **Next:** Monitor and resume this same pipeline ID only if abandoned; verify
  Silver, reconciliation, certification, and audit outputs before closing R1.

## Context and Decisions

- Restored legacy 2019 refs are exact Preview-only comparison evidence at
  `artifacts/preview/legacy-comparison/2019/legacy-comparison-2019-55f6968/manifest.json`.
- R1 venues, game statistics, and plays are planned solely from same-run games
  captures, never from `raw/*` projections.
- Code identity is one-run-only. Earlier artifacts remain immutable diagnostics
  and are never mixed into active lineage.

## Work Completed

- Added Preview ledger grants, canonical source transforms, and manifest-only
  planning for venues, statistics, and plays.
- Added numeric coercion for venue elevation before situational arithmetic.
- Restored comparison evidence and started the clean run bound to `929f331`.

## Validation

- [x] Focused R1 capture tests: 16 passed.
- [x] Focused situational/R1 tests: 6 passed.
- [x] Prior full Python suite checkpoint: 571 passed, 2 skipped.
- [x] Scoped Ruff and `git diff --check` at each repair.
- [ ] Full R1 closeout validation awaits terminal run completion.

## Amendments and Blockers

- Legacy comparison restoration is implemented and comparison-only.
- Same-ID recovery was used once after an abandoned outer process, with no
  duplicate source request registration.
- A reconciliation elevation type defect required a fresh code-bound run;
  `r1-full-corpus-20260828-929f331` is that run.

## Handoff Notes

- **Resume at:** Inspect Preview ledger for `r1-full-corpus-20260828-929f331`.
- **Watch out for:** Preserve all artifacts; exclude 2020/2026; never write raw
  projections or begin R2 before `tournaments_permitted` is true.

**tags:** ["r1", "historical-data", "immutable-lake", "preview", "session-closeout"]
