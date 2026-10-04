# Session: Window 2 Amendment 2 planning persistence

## TL;DR
- **Worked On:** Persisted and approved Amendment 2 (Window 2 measurement repair and prospective cutover) and its two appendices, and assessed the partial Window 1 code against the contract.
- **Outcome:** Amendment 2 approved by the user on 2026-10-04. No code, data, migration or release change in this step. Window 1 finishes first.
- **Plan Contract:** `docs/plans/2026-10-03/04-data-integrity-two-window-implementation.md`
- **Approval / Status:** User chose "Approve it now (Recommended)" for Amendment 2 and both appendices. This does not authorize any Preview/production write.
- **Blockers:** Window 1 gaps below. Window 2 starts only after Window 1 release receipts exist, at 5A, with its 25% go/no-go.
- **Next:** Finish Window 1 (Tasks 1–4), then a fresh session for 5A.

## Context and Decisions
- Amendment 2 text and the blocker replacements (CFBD-drive primary evidence with 25% gate, PPP-only served-path proof, authorization/revocation separation, migrations 0022/0023 and grants, web split, N fixed at the 7B packet, V5 Week 5+ prospective scope, issue #5 reconciliation) are in Appendices A and B under `docs/plans/2026-10-03/window2/`.
- Issue #5 closure comes from the local 10-03 investigation log (0/76 overtime plays, 0/20 OT drives, 24/24 hand-check), not a Window 1 code fix.
- User caution for Window 1 Task 3: keep the styled `PerformanceDashboard.tsx` design from `1459322`; replace financial figures with accuracy figures instead of leaving a stub.

## Window 1 review (agent-reported unless marked verified)
- Done: snapshot identity and conflict readback; away/under ties and lowest-away-line selection in grading, weekly and publisher; null lean writes no selection; v2 frozen grading; `ppa_missing` before `fillna(0)`; venue city gate.
- Verified by me: independent verifier `scripts/pipeline/verify_v5_intended_update_serving.py:60-62` still uses `>=` (exact ties go home/over).
- Open: publisher fallback lean at `publish_to_db.py:133-139`; `units`/`roi` still computed in `web/src/lib/v5.ts`; -110 break-even wording in `slate.ts`; dashboard stripped to a skeleton; missing tests (frozen grading, null lean, venue gate); no release receipt.

## Files Modified
- Contract 04, both appendices, plans index, decision log, known issues, status, and authority banners on contracts /01–/03: Draft → Approved 2026-10-04.

## Validation
- `git diff --check` and `uv run mkdocs build --quiet` passed before the status edits; re-run after.
- Window 1 scoped tests: 129 passed (before any new changes).
- Not run: full test suite, web checks.

## Handoff Notes
- `dev` was 3 commits ahead of `origin/dev`; the user runs git and must push and confirm the commit is reachable before any Terra handoff.
- Proposed commit message: `docs: persist Amendment 1 and approve Window 2 Amendment 2 with appendices`

**tags:** ["data-integrity", "planning", "window2", "amendment"]
