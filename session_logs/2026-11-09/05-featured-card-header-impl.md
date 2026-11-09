# Session: Featured card header and wording (implementation)

## TL;DR

- **Worked On:** Implemented `docs/plans/2026-11-09/featured-card-header.md`: the Biggest edges / Underdog picks control moves to the card header's right side, the Underdog intro line changes, and "straight up, all picks" leaves the season record text.
- **Outcome:** Implemented; validation below.
- **Plan Contract:** `docs/plans/2026-11-09/featured-card-header.md`
- **Approval / Status:** Contract approved by the owner; Implemented.
- **Blockers:** None.
- **Next:** None.

**tags:** ["web", "games-page", "featured-card"]

## Context and Decisions

- `ResponsiveDisclosure` gains an optional `action` slot. With it, the header is a wrapping flex row: heading (from `sm:`) on the left, action on the right. On phones the heading is hidden, so the row holds only the action at full width, inside the opened card; the collapsed summary is untouched, so collapsed height is unchanged. When the width is too small for both, the action wraps under the title.
- `FeaturedGames` passes the `SegmentedControl` (unchanged, 44px phone targets) as `action`.
- Underdog intro line is now "The model says the wrong team is favored". Record text is `2026: 23–57`; the phone footer suffix reads `Straight-up record: picks won outright (2026: 23–57)`.

## Work Completed

- `web/src/components/ui/ResponsiveDisclosure.tsx`, `web/src/components/slate/FeaturedGames.tsx`, `UnderdogPicks.tsx`.
- e2e: `desktop-layout.spec.ts` (new copy, absent old phrase, new 640px same-row check), `publication.spec.ts`, `mobile-slate.spec.ts` (320px: the opened card's control stays inside the viewport in both views).
- Docs: `docs/modeling/record_methodology.md`, `docs/decisions/decision_log.md`.

## Files Modified

- Files listed above, plus this log.

## Validation

- [x] `cd web && npm run test:publication`: 475 tests, 474 passed, 1 skipped
- [x] `make check`: passed
- [x] `make web-e2e`: 449 passed, 10 skipped, plus the known expected-failure market board test
- [x] `git diff --check`: clean
