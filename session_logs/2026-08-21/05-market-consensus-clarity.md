# Session: Market consensus clarity

## TL;DR

- **Worked On:** Clarified the source and meaning of non-standard decimal
  market lines in the public Week 0 prediction cards.
- **Outcome:** Production labels every card's reference as `Market Consensus`
  and explains that sportsbook lines can differ; no line, edge, or artifact
  was rounded or changed.
- **Plan Contract:** N/A (approved, localized public UI clarification)
- **Approval / Status:** User explicitly approved the recommendation on
  2026-08-21.
- **Blockers:** Selecting a named sportsbook for grading remains a future
  pipeline policy decision.
- **Next:** Draft the named-sportsbook/price reference contract before
  changing market selection or grading authority.

## Context and Decisions

- The durable market policy is `consensus_then_median_v1`: it uses the newest
  CFBD consensus quote per target when available, otherwise the median of the
  latest valid provider quotes. Aggregated values may legitimately be `-7.3`
  or `-36.8`, unlike a typical single-book `.0` or `.5` offering.
- Rounding the public number would make the stated model-market edge disagree
  with the immutable snapshot. The UI must disclose the aggregate rather than
  imply a directly bettable quote.

## Work Completed

- Added `Market Consensus` above each prediction card's lean rail and to the
  market-mode card label.
- Added a single page-level explanation: individual sportsbooks may differ;
  edge measures model-market disagreement, not confidence or profit.
- Deployed production successfully:
  `https://c-ks-picks-o2k0ewhbl-connorkitchings-projects.vercel.app`.

## Files Modified

- `web/src/components/GameRow.tsx` - Labels consensus lines at card level.
- `web/src/app/page.tsx` - Explains the snapshot caveat in prediction mode.

## Validation

- [x] `npm run lint`
- [x] `npm run typecheck`
- [x] `npm run test:publication`
- [x] `npm run build`
- [x] `git diff --check`
- [x] Production render check for consensus labels/copy.
- [x] Production health: predictions mode, active run
  `2026w0-55de0317120d`, 8 expected / 8 predicted / 8 lined.

## Handoff Notes

- **Resume at:** Use the planning workflow to decide the authoritative named
  sportsbook, timestamp policy, price capture, fallback behavior, and grading
  lineage before implementing a bettable-line reference.
- **Watch out for:** Preserve all current consensus/provider quotes and their
  immutable capture lineage; do not overwrite or round them.

**tags:** ["week0", "market-consensus", "web", "ui", "lineage"]
