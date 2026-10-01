# Session: Advanced Stats Matchup Breakdown Planning

## TL;DR
- **Worked On:** Planned the Phase 2 Advanced Stats Matchup Breakdown inspired by Parker Fleming's (@statsowar) college football unit-vs-unit preview cards.
- **Outcome:** Created decision-complete implementation plan [`docs/plans/2026-10-01/03-advanced-stats-matchup-breakdown.md`](file:///Users/connorkitchings/Desktop/Repositories/ckspicks-cfb/docs/plans/2026-10-01/03-advanced-stats-matchup-breakdown.md).
- **Plan Contract:** `docs/plans/2026-10-01/03-advanced-stats-matchup-breakdown.md` (Status: `Approved`)
- **Approval / Status:** Explicit user approval in chat ("Yes").
- **Blockers:** None.
- **Next:** Execute implementation under the repository-local contract.

## Context and Decisions
- **Visual Design:** Replicate the high-utility structure of Parker Fleming's advanced stats preview graphic:
  - Top win probability & projected points cards.
  - Flanking team statistical profile pillars (EPA margin, Offense/Defense success rate, Net points/drive, Net field position, Eckel ratio).
  - Center symmetrical unit-vs-unit matchup tables (`Away Off vs Home Def` and `Away Def vs Home Off`) with color-coded national rank badges.
  - Automated analytical takeaways highlighting primary matchup edges.
- **Route Architecture:** Implement a dedicated Next.js server route at `/matchup/[gameId]` with deep-linkable URLs, breadcrumbs, and responsive desktop 3-column / mobile stacked layouts.
- **Data Engine:** Calculate win probabilities, projected scores, and unit efficiency metrics from active certified V5 ratings, prediction records, and calibrated national distributions in `web/src/lib/matchup.ts`.

## Validation
- [x] Documentation validation: Plan template adhered to, paths verified
- [x] Worktree review: `git diff --check` passed

## Handoff Notes
- **Resume at:** Begin Task 1: implement `web/src/lib/matchup.ts` and test suite.

**tags:** ["web", "matchup", "advanced-stats", "statsowar", "planning", "sol-contract"]
