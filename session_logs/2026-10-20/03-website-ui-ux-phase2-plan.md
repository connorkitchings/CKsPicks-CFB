# Session: Website UI/UX Phase 2 Implementation Contract

## TL;DR
- **Worked On:** Investigated and drafted the Phase 2 Sol-to-Terra implementation contract (`docs/plans/2026-10-20/02-website-ui-ux-phase2.md`) covering all remaining approved items from the October 20 UI/UX review.
- **Outcome:** Persisted decision-complete `Draft` contract for `BetCell` hierarchy condensation, conference filters on `/ratings`, `/`, and `/results`, rank-tier badges on `/ratings`, and synchronized collapsible secondary sections in `UnitMatchupTable.tsx`.
- **Plan Contract:** `docs/plans/2026-10-20/02-website-ui-ux-phase2.md`
- **Approval / Status:** `Draft` awaiting owner approval or explicit Terra execution authorization.
- **Blockers:** None
- **Next:** Owner review/approval of `docs/plans/2026-10-20/02-website-ui-ux-phase2.md`, followed by Terra execution.

## Context and Decisions
- **Scope (`After that` tier from owner's October 20 plan judgment):**
  1. **Task 1 (WS3 — `BetCell` hierarchy condensation):** Move `lean.source` (`DraftKings`, `Bovada`, `FanDuel`, etc.) into the top-right header row of `BetCell` on Picks (`results === false`) so Picks cards render at most 3 text rows per `BetCell` while Results cards retain `<ResultBadge>` in the top-right header row and `[lean.source, cover]` below.
  2. **Task 2 (WS3 & WS5 — Conference filter on `/ratings`, `/`, and `/results`):** Use `team_season_roster` (`getTeamSeasonRoster(season)`) and dedicated test fixtures (`ratingsRosterFixture`, `slateRosterFixture`) with CFBD alias resolution (`withGameNameAliases`) to offer `All FBS`, `Power Four + Notre Dame`, and individual conference filtering without altering national ranks on `/ratings` or overflowing mobile height on `/` and `/results`.
  3. **Task 3 (WS5 — Rank-tier badges on `/ratings`):** Reuse `getRankBadgeClass(rank, cohortSize)` from `web/src/lib/team-stats.ts` on `#`, `SOR`, `SOS Played`, `SOS Remaining`, and `SOS Full` rank cells while preserving exact cell text (`#2`, `—`) and `title` attributes (`"SOR 81.2"`) asserted by `web/e2e/ratings.spec.ts`.
  4. **Task 4 (WS4 — Collapsible secondary matchup sections):** Own `collapsedSections` state in `UnitMatchups.tsx` and pass it to both `UnitMatchupTable` instances so collapsing/expanding `"Situational / down and distance"` or `"Drive context"` synchronizes both side-by-side desktop tables (`expect(ra).toEqual(rb)`) and preserves centered `<th scope="rowgroup">` text geometry.

## Work Completed
- Inspected `PredictionGameCard.tsx`, `SlateToolbar.tsx`, `PicksSlate.tsx`, `ResultsSlate.tsx`, `RatingsView.tsx`, `UnitMatchups.tsx`, `UnitMatchupTable.tsx`, `chart-queries.ts`, and E2E test suites (`publication.spec.ts`, `mobile-slate.spec.ts`, `desktop-layout.spec.ts`, `ratings.spec.ts`, `matchup.spec.ts`).
- Created `docs/plans/2026-10-20/02-website-ui-ux-phase2.md` and indexed it in `docs/plans/index.md`.

## Files Modified
- `docs/plans/2026-10-20/02-website-ui-ux-phase2.md` - Phase 2 Sol-to-Terra implementation contract (`Status: Draft`)
- `docs/plans/index.md` - Indexed Phase 2 contract and updated Phase 1 status to committed (`ddb08414`)
- `session_logs/2026-10-20/03-website-ui-ux-phase2-plan.md` - Planning session log

## Validation
- [x] `uv run mkdocs build --quiet`
- [x] `git diff --check`

## Amendments and Blockers
- None

## Handoff Notes
- **Resume at:** Execute `docs/plans/2026-10-20/02-website-ui-ux-phase2.md` with `.agent/skills/implement-plan/` once approved/authorized.
- **Watch out for:** Preserve single-row `SlateToolbar` height on 390×844 phones so `#game-1` clears the 34px bottom safe-area inset in `mobile-slate.spec.ts`.

**tags:** ["planning", "web", "ui-ux", "ratings", "matchup", "slate"]
