# G2 findings (read-only, 2026-10-03)

## Weeks 0-4 grades: clean
- 429 graded rows (215 spread, 214 total), all `completion_state='completed'`.
- Independent recompute from `game_results` + selected quote point + stored side:
  spread 100-112-3, total 112-102-0. Matches the scoreboard. 0 diffs vs `prediction_grades`.
- 0 rows where `prediction_grades.side` != `prediction_market_selections.side`;
  0 rows where `market_quote_id` differs; 0 rows where stored side disagrees with the side
  implied by its own quote.

## Selection (L5/L6), weeks 0-5
- CORRECTED LATER THE SAME DAY: the first version of this section said "selected `point` == consensus line on every row => the away
  best-quote sort never changed a pick". That compared `prediction_market_selections.point` with `predictions.home_team_spread_line`,
  which are two copies of the same selected quote, not the consensus. Tested properly (see `delta-findings.md`, section "L5"):
  in all 70 games where the books disagree, the stored line is the HIGHEST home line, which is the best line for the 37 home picks and the
  WORST for all 33 away picks (0.82 points given up on average). The side never changed (0 flips under the median line), and the weeks 0-4 spread
  record changes by one result (loss -> push) under the best line for each side. L5 is real and active; it affects the line, not the side.
- No exact ties (`>` vs `>=`, D7a) and no null prices in weeks 0-5.

## NEW: Week 5 null-lean rows carry a defaulted side (Preview and production identical)
- Run `2026w5-v5repair-20260929-p2`: 7 spread + 8 total predictions have null lean (no edge).
- `scripts/pipeline/publish_to_db.py:928` / `:982` still write a `prediction_market_selections` row for them with
  `side = lean or "home"/"over"`, `edge = 0.0`. For spreads the price is chosen with `lean == "home"`, which is False for null,
  so the price comes from the away side while the side says home (all -110 today, so benign now).
- `web/src/lib/queries.ts:713-720` overrides `spreadLean`/`totalLean` with the selection side, so the site shows the defaulted side.
- 5 of the 15 contradict the model-vs-consensus side:
  - spread: Virginia Tech v Pittsburgh (401858245), Rice v UTSA (401862788), Hawai'i v San Jose State (401864513)
  - total: UNLV v California (401858247), Rice v UTSA (401862788)
- No Week 5 grade exists yet. The grade backfill re-derives the side from the math, so graded side != displayed side for those 5.
