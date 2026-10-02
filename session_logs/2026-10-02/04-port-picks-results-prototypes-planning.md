# Session: Port Picks/Results Prototypes Planning

## TL;DR
- **Worked On:** Reviewed the gated `/test-picks` and `/test-results` prototypes against the production Picks/Results pages and drafted the port contract.
- **Outcome:** Port judged worth implementing; contract `docs/plans/2026-10-02/02-port-picks-results-prototypes.md` is Approved (single unified contract, both pages, five gap resolutions locked, plus the `EdgeNote`/`edgeTone` preservation note) and registered in `docs/plans/index.md`.
- **Plan Contract:** `docs/plans/2026-10-02/02-port-picks-results-prototypes.md` (`Approved`)
- **Approval / Status:** User approved the port framework and all five gap resolutions, with one implementation note (Amendment 1). Persisted after the session moved from plan to build mode.
- **Blockers:** None
- **Next:** Hand off to a fresh Terra task with the exact plan path for execution.

## Context and Decisions
- Start-session routing: read AGENTS.md, `docs/status.md`, `.codex/QUICKSTART.md`; reviewed 2026-10-01/02 session logs; confirmed branch `dev` at `c8664fb`, clean worktree. Another session is ongoing — this session stayed in planning and touched only the two new docs.
- The prototypes (built/iterated 2026-10-01) are the best-tested UI code in the repo (280 lines unit tests + 25+ Playwright checks). Their headline features depend on data already live in production: venues (271 games, migration 0019) and sportsbook sources (Neon selections), both already returned by `getGamesForWeek`.
- Five gap resolutions (approved): (1) port `/` + `/results` together in one contract; (2) rank badges stay out of cards; (3) per-game market-mode fail-closed card retained; (4) global Header + SiteNav retained, slim page-local status row only; (5) `ModelRecord` replaces `V5PerformanceBanner`.
- Amendment 1 (user note at approval): extract `EdgeNote`/`edgeTone` into `components/slate/` before deleting `BetComparisonTable.tsx` — verified they exist only there.

## Work Completed
- Full prototype-vs-production review (18 `picks-proto` components, `picks-proto.ts` lib, both `/test` pages, `GameRow`/`GamesList`/`WeeklySlateView`, gates, fixtures, e2e).
- Verified deprecation blast radius: `overallRanks` used only by `/test` pages (deletable); `StatCard`/`BetTable` survive; `loading.tsx` and a `ratings.test.ts` source assertion need updates.
- Wrote and registered the Approved implementation contract.
- No implementation files touched (Sol persist step only).

## Files Modified
- `docs/plans/2026-10-02/02-port-picks-results-prototypes.md` - Approved implementation contract (new)
- `docs/plans/index.md` - Registered the new contract row
- `session_logs/2026-10-02/04-port-picks-results-prototypes-planning.md` - this log

## Validation
- [x] Contract follows the implementation-contract-template structure
- [x] Facts verified against code (queries fields, component users, test coupling, docs references)
- [ ] `git diff --check` (run before proposing the commit)

## Amendments and Blockers
- Amendment 1 recorded in the contract (`EdgeNote`/`edgeTone` preservation).
- Watch out: another session is active on `dev` — Terra must coordinate to avoid concurrent edits in `web/src/app/page.tsx`, `web/src/app/results/page.tsx`, or the slate components.

## Handoff Notes
- **Resume at:** open a fresh Terra task with the exact plan path `docs/plans/2026-10-02/02-port-picks-results-prototypes.md` (Approved) via `.agent/skills/implement-plan/`.
- **Watch out for:** user's local web session (`make web-local`, Preview data) is available for real-data screenshots during implementation; do not run pipeline/ops steps (Week 5 frozen).

**tags:** ["web", "planning", "prototypes", "picks", "results", "contract"]
