# Session: Blitzkrieg name, banner fix, frozen market lines

## TL;DR

- **Worked On:** The three post-deploy site issues: V5 public name, empty homepage banner card, and missing market lines on replay weeks.
- **Outcome:** Site shows "Blitzkrieg" for V5; homepage banner hides the empty live card; all 215 replay games render frozen pre-kickoff lines with derived leans/edges. No database mutation; manifests untouched.
- **Plan Contract:** N/A (fast path: localized web changes; replay-cutover plan governs the data, unchanged).
- **Approval / Status:** User chose the name (Blitzkrieg), the render-lines approach, and confirmed the banner location. No production writes.
- **Blockers:** None.
- **Next:** Commit; push to deploy; verify the live site shows the name, one replay card, and lines.

## Context and Decisions

- The "0-0 scoreboard" was the homepage banner's live-classification card (0 games, 0–0–0) — the query layer was already correct (replay 72-82-3, MAE 15.6). Fix is presentational: hide zero-game classifications on the homepage banner; the detailed performance page still lists all three.
- Market lines: replay serving rows carry no lines by design (built without a market feed). Rather than mutating published rows or rebuilding artifacts (which would break authorization SHAs), the site now fills display lines at query time from each week's closed V4 run snapshots — the exact quotes the grades use — and derives leans/edges with tested twins of the pipeline rules. Stored values are never overwritten; live weeks with own lines are untouched.
- "Blitzkrieg" is display-only (`displaySystemName`); manifests keep `Trench Warfare V5`, V4 keeps `Trench Warfare V4`, and no re-release was needed.

## Work Completed

- `web/src/lib/publication.ts`: `displaySystemName` + `deriveSpreadView`/`deriveTotalView` pure helpers.
- `web/src/components/Header.tsx`: renders the display name.
- `web/src/components/V5PerformanceBanner.tsx`: filters zero-game classifications.
- `web/src/lib/queries.ts`: `withFrozenLines` enrichment in `getGamesForWeek` (closed V4 run snapshots, scored-first ordering).
- `web/src/lib/publication.test.ts`: 3 new tests (naming, spread/total derivation incl. boundary/null cases).
- Verified end to end: Preview W0 fills 8/8; production fills 215/215 with leans; grades and scores unchanged.

## Files Modified

- `web/src/lib/publication.ts`, `web/src/lib/publication.test.ts`, `web/src/lib/queries.ts`, `web/src/components/Header.tsx`, `web/src/components/V5PerformanceBanner.tsx`.

## Validation

- [x] Web unit tests 11/11; lint; typecheck; production build.
- [x] Page-layer checks vs Preview (W0) and production (W0–4): lines, leans, edges present; stored values intact.
- [x] `git diff --check`; docs unaffected.

## Amendments and Blockers

None. One known gap: Preview weeks 1–3 have no closed V4 run (rehearsal published-only), so the fill finds nothing there — production (closed runs every week) is complete. Acceptable rehearsal divergence.

## Handoff Notes

- **Resume at:** Commit below, push, verify the live homepage (Blitzkrieg name, single replay card 72-82-3, lines on game rows).
- **Watch out for:** `highConfidence` stays null on replay rows (no stars) — conservative and intentional. Do not backfill prediction rows to "fix" display; the query layer owns it.

**Suggested commit message:** `Show Blitzkrieg, hide empty live card, render frozen lines`

**tags:** ["web", "v5", "display"]
