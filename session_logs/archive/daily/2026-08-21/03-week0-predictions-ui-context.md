# Session: Week 0 predictions UI context

## TL;DR

- **Worked On:** Refined the public Week 0 prediction cards and early-season
  backtest context after user review.
- **Outcome:** Each card presents market lines once, keeps the model output in
  plain language, hides the empty high-confidence control, and explains the
  route-qualified backtest populations.
- **Plan Contract:** N/A (approved, localized public UI refinement)
- **Approval / Status:** User approved the redesign on 2026-08-21.
- **Blockers:** None.
- **Next:** Continue the manual snapshot/final-freeze procedure before
  kickoff.

## Context and Decisions

- The eight-game Week 0 slate has no high-confidence rows by design, so an
  empty high-confidence filter does not help users and is hidden until it has
  a result to filter.
- The 2025 `n=83` accuracy figure is the locked-test population for the
  first-game route, not the season-wide prediction count. It includes games
  where at least one team had not completed a game before kickoff.

## Work Completed

- Kept spread and total market lines only in the actionable lean rail.
- Replaced the duplicate market/model footer with a single plain-language
  projection such as `Model projection: TCU by 17.8 · 46.5 total`.
- Removed internal model-version identifiers from public cards.
- Added route eligibility copy plus separate 2025 locked-test and 2022–24
  out-of-sample qualifying-game counts to the accuracy panel.
- Deployed production successfully:
  `https://c-ks-picks-pq4duxoka-connorkitchings-projects.vercel.app`.
- Confirmed the production alias renders the new model-projection wording and
  the 83/243 route-qualified backtest context; health remains predictions mode
  with 8 expected / 8 predicted / 8 lined coverage.

## Files Modified

- `web/src/components/GameRow.tsx` - Deduplicated market lines and clarified
  model projection.
- `web/src/components/GamesList.tsx` - Suppressed an empty high-confidence
  filter.
- `web/src/components/ModelAccuracyPanel.tsx` - Added route and sample context
  to backtest metrics.

## Validation

- [x] `npm run lint`
- [x] `npm run typecheck`
- [x] `npm run test:publication`
- [x] `npm run build`
- [x] `git diff --check`

## Handoff Notes

- **Resume at:** Before each desired market observation, publish a new manual
  snapshot and record its run and line timestamps; review/freeze the final run
  before kickoff.
- **Watch out for:** Retain the manual-only snapshot policy; this UI change
  does not alter run lineage, published artifacts, or the final-freeze rule.

**tags:** ["week0", "predictions", "web", "ui", "backtest-context"]
