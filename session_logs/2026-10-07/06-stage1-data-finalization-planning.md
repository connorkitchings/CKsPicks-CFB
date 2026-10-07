# Session: Stage 1 corrected data finalization: planning

## TL;DR
- **Worked On:** Answered "what is left besides Docker", sized the effect of the corrected lineage on predictions, and wrote the Stage 1 contract.
- **Outcome:** Contract `docs/plans/2026-10-07/04-stage1-week5-corrected-data-finalization.md` (Approved, Preview only, no Production or controller change). The release path (cutover, interim replay release, or display-only Week 6) is deferred to a decision brief after Stage 1.
- **Plan Contract:** `docs/plans/2026-10-07/04-stage1-week5-corrected-data-finalization.md`
- **Approval / Status:** User approved the Stage 1 scope in session and rejected the interim-release amendment for now.
- **Blockers:** None for Task 0 (read-only). Tasks 1 and 4 write to Preview and need explicit go-ahead.
- **Next:** Task 0 verification, then Task 1 once the user says go.

## Context and Decisions
- Corrected foundation (6A/6B) is Preview-only. 6B comparison (Weeks 0-5, 271 games): mean margin change 3.1 pts, 27 spread and 13 total lean flips, 38 grade changes, spread record 128-139-4 to 130-136-5.
- Calendar: Week 6 ends Oct 11 02:30Z; Week 7 first kickoff Oct 13 23:00Z (freeze by 22:00Z), Week 8 Oct 20 23:00Z. Week 6 stays on the hold screen (earlier user decision).
- The corrected 2026 rebuild is Week-4-specific (`silver_2026.py`, `states_2026.py`, `recon_foundation.py:118`, `pin_6a_silver_parents.py`, the `w4` input set in `run_data_first_repair_v2.py:99`), so Stage 1 includes week-parameterizing it with byte-parity on Weeks 0-4.
- An external critique of the earlier plan was checked against the repo: it misattributed the Week 6 hold (the user chose it), called display-only "low churn" (three kickoff guards would need a recorded display-only mode) and treated Stage 1 as required for a display-only Week 6 (that path needs an old-lineage refresh instead). Only the Stage 1 recommendation was adopted.

## Work Completed
- Read-only discovery: known issues, Contract 04 release spec and checklist, the v2 batch controller, the 6A plan and 2026 Silver pins, the approved-inputs table, `prepare-week`, the 6B comparison summary in Preview R2.
- Wrote the contract and this log; no code, data or database change.

## Validation
- [ ] `git diff --check` and docs build (run at commit time).

## Handoff Notes
- **Resume at:** Task 0 of the contract (read-only), recording evidence in `session_logs/2026-10-07/07-stage1-implementation.md`.
- **Watch out for:** `prepare-week` stops at its readiness step until ratings are projected; Week 0-4 stability stop conditions; every Preview write needs a go-ahead.

**tags:** ["data", "pipeline", "stage1", "planning", "corrected-lineage"]
