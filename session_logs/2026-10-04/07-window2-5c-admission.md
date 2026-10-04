# Session: Window 2 Step 5C admission and independent certification

## TL;DR
- **Worked On:** per-group admission of R1, independent v1 verifier, local dry run over the historical corpus.
- **Outcome:** 1,416 groups admitted; 28 contradicted and 1,749 unverified groups reverted; verifier ok; v1 contract 0 problems. No R2/Neon writes.
- **Plan Contract:** `docs/plans/2026-10-03/04-data-integrity-two-window-implementation.md`, Appendix A Amendment 2
- **Status:** Closed by the user 2026-10-04 (`ea53c07`); Step 5 finalized in a docs-only follow-up. 6A authorized for Preview-lake writes but not started, at the user's instruction.
- **Blockers:** CFBD rights basis for the evidence table; R2 write approval for 6A.
- **Next:** 6A, only when the user says to start it; guardrails are in Appendix A Amendment 3.

## Errors made and fixed
My first materiality figures mixed FCS one-game team-seasons into the ranks (454 and 356 flagged); I restricted to team-seasons with at least 60 possessions and report both. A background-run notification looked like completion before the verifier finished; I checked the process before reading results.

**tags:** ["data-integrity", "window2", "5c", "admission"]
