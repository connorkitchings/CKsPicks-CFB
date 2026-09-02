# 2026 Record & Weekly Context Redesign

- **Status:** Implemented
- **Created:** 2026-09-02
- **Planner:** Sol
- **Approval source:** User message on 2026-09-02: “PLEASE IMPLEMENT THIS PLAN”
- **Implementation log:** `session_logs/2026-09-02/04-web-record-context-redesign.md`
- **Commit policy:** Commit with implementation

## Goal

Make the public 2026 Vercel experience clearer at a glance: expose an
accurate record for the selected point in the season and make the recently
adopted comparison table readable on phones.

## Current State

- Publication remains environment-scoped, defaults to 2026, and fails closed
  to market-only output without the exact prediction opt-in.
- `system_stats` is a latest-season aggregate, so it cannot faithfully render
  a historic weekly page after later weeks are scored.
- The current record banner prioritizes ROI; the early-season panel repeats
  lengthy route descriptions and metric cards.
- The desktop Market / Model / Model Bet / Bet Result table is correct, but
  its five columns are too narrow on a 375px viewport.

## Proposed Approach

Read record snapshots from immutable `prediction_grades`, using the latest
scored run for each included week. Keep `system_stats` unchanged for pipeline
operations. Replace the overview panels with compact semantic tables and
provide a dedicated mobile comparison table while retaining the established
desktop design.

## Scope

### Included

- Selected-week 2026 records in prediction mode.
- Record banner, game-card responsive layout, and web tests.
- Documentation and implementation session log.

### Excluded

- Database migrations, pipeline changes, production-data mutation, and a
  non-2026 publication-policy change.

## Affected Components and Contracts

- `web/src/lib/queries.ts`: selected-week record query and `Stats` cutoff
  contract.
- `web/src/app/page.tsx` and `web/src/components/RecordBanner.tsx`: record
  placement and display.
- `web/src/components/GameRow.tsx`: responsive comparison views.
- Web fixtures and Playwright coverage.

## Implementation Tasks

### Task 1 — Derive selected-week records

**Changes:**

- Select the latest `scored` run per 2026 week at or before the selected week;
  aggregate its immutable spread and total grades.
- Return a zeroed snapshot with `asOfWeek: null` when no result has been
  graded. Keep `system_stats` and its producer unchanged.

**Acceptance criteria:**

- Week 0 never includes Week 1 grades; a pregame Week 1 view displays the
  Week 0 cutoff.
- Market mode reads no record or other model-derived data.

### Task 2 — Simplify the page overview

**Changes:**

- Render a prominent “2026 Season Record” immediately below the header, with
  Spread and Total W-L-P and hit rate, explicit graded cutoff, and a no-results
  state. Do not show ROI or vig copy.
- Remove the weekly model-context panel for now. Historical market lines are
  unavailable, so the app must not imply a prior-season W-L record.

**Acceptance criteria:**

- Record appears before week navigation.
- No weekly model-context panel is rendered.

### Task 3 — Make comparison cards responsive

**Changes:**

- Preserve the current five-column desktop table and all calculation,
  fail-closed, and result behavior.
- Color the parenthetical model-versus-market edge by its absolute size: total
  under 2 red, 2 through 7 yellow, and over 7 green; spread under 3 red, 3
  through 8 yellow, and over 8 green. Preserve the signed number itself.
- At phone widths, render a three-column Market / Model / Bet table; attach a
  settled result chip to the Bet value instead of retaining a fourth result
  column.

**Acceptance criteria:**

- Long team names remain contained without page-width overflow at 375px and
  420px.
- Market mode remains devoid of model values.
- Edge colors remain legible in light and dark themes and do not change the
  underlying edge calculation or its direction.

## Testing Strategy

- Update UI fixtures for selected-week cutoffs and pre-score records.
- Replace stale Playwright assertions for removed card labels; verify record,
  prediction/market publication boundaries, and
  responsive width at 375px and 420px.
- Run `npm run lint`, `npm run typecheck`, `npm run test:publication`,
  `npm run test:ui`, `npm run build`, and `git diff --check` from `web/` as
  appropriate. Visually inspect both breakpoints and the deployed Week 1 page.

## Risks and Edge Cases

- Do not include a published or frozen replacement run in the historical
  record; only the latest scored run for each completed week is authoritative.
- A selected week may have no scored results. Its banner must stay visible and
  say so rather than imply a 0-0 record.
- Do not present historical W-L data without immutable historical market lines
  and corresponding graded model leans.

## Definition of Done

- [x] Selected-week grade aggregation and UI contracts are complete.
- [x] Record and responsive comparison designs meet acceptance
  criteria.
- [x] Required local validation passes.
- [x] The live Week 1 presentation was checked after deployment.
- [x] This plan and the implementation session log are updated.

## Amendments

The weekly model-context panel was removed at the user's request because the
historic artifacts lack immutable market lines and model grades for a truthful
historical W-L display. Production deployment `dpl_CaEcLCU4SYRGAy8PEXgstcYup5KS`
became Ready on 2026-09-02, and the live Week 1 page was checked at desktop
and phone widths.
