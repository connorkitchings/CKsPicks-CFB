# Session: Window 1 completion and release receipt (pre-commit)

## TL;DR
- **Worked On:** Closed the remaining Window 1 gaps from the code review: verifier tie/sort rule, publisher null labels, accuracy-only dashboard, tests.
- **Outcome:** Local code and tests pass. Window 1 is **not released**: nothing is committed, Preview was not touched, and the receipt fields marked PENDING need user-run steps.
- **Plan Contract:** `docs/plans/2026-10-03/04-data-integrity-two-window-implementation.md` (Tasks 1–4)
- **Next:** User commits, runs the Preview rehearsal below, fills the PENDING fields, then decides on production.

## Changes
- `scripts/pipeline/verify_v5_intended_update_serving.py`: exact ties now go Away/Under (`>` not `>=`). The independent verifier also sorted spread quotes highest-first for **every** side; Away now selects the lowest home-signed line, matching `models/market_grading.py`.
- `scripts/pipeline/publish_to_db.py`: a bet-label column that exists but is empty/NaN stays a null lean (no synthesized lean). A missing column (legacy artifact) still falls back to the numbers, with ties Away/Under.
- `web/src/components/PerformanceDashboard.tsx`: restored the styled KPI cards, calibration strip, filters, mobile cards and desktop tables from `1459322`; money figures replaced by W-L-P, win rate (pushes excluded), MAE, 95% interval coverage, and graded-pick audit with price provenance.
- `web/src/lib/v5.ts`, test fixture, `performance.test.ts`: removed `units`/`roi` and the `profit_units` reads. Stored DB fields untouched. `slate.ts` comment reworded (52.4% is a reference threshold).
- Tests added: `tests/test_window1_selection_rules.py`, `tests/test_frozen_grading.py`, plus accuracy tests in `web/src/lib/performance.test.ts`.
- `tests/test_weekly_inference.py`: two assertions updated (see decisions below).

## Decisions resolved (user, 2026-10-04)
- Total-bet threshold: keep `edge >= threshold`.
- Verifier: if the corrected sort rejects a signed run, report it in the receipt and decide per run (no legacy path).
- Performance Playwright spec added now: `web/e2e/performance.spec.ts` (written, typechecked and linted; **not yet run** — user runs Playwright).
- Full Python suite re-run after the last edits: 1644 passed, 9 skipped.

## Decisions for the user to confirm (superseded by the above where noted)
1. **Total-bet threshold (pre-existing worktree change in `inference/weekly.py`):** totals now bet when `edge >= threshold`, matching spreads and the committed verifier (`edge >= 1.0`). The old strict `>` meant a total exactly at the threshold was "No Bet". I updated the test that pinned the old behaviour. Revert both if you want strict `>`.
2. **Policy version:** the manifest test now expects `model_side_best_quote_v2` (the worktree already bumped `SELECTION_POLICY_VERSION`).
3. **Verifier sort fix may reject historical artifacts:** if any already-signed run selected the highest line for an Away spread, the corrected verifier will flag it. Run it on the served and rollback runs before relying on it, and reproduce original stored grades before any replay (contract requirement). Not yet done.
4. `models/historical_model_context.py:211` (`>= 0` on the 2025 V4 context) was left unchanged: it feeds signed historical context and is outside Window 1 selection. Revisit in 5A.

## Validation
- `uv run python -m pytest tests -q`: 1642 passed, 9 skipped, 2 failed before the two test updates above; the affected file then passed (9/9). Full suite not re-run after the update.
- `ruff check` on touched Python files and `src`: clean.
- Web: `npm run typecheck`, `npm run lint`, `npm run test:publication` (118 pass), `npm run build`: all pass.
- Not run: Playwright (user-run; do not use the user's dev server), real Preview checks, publish-time venue gate test (only `require_venue_cities` itself is unit-tested; the wiring in `publish_to_db.py` needs a DB and is covered by the Preview rehearsal).

## Verifier run on served Preview artifacts (verified 2026-10-04, read-only)
- Command: `verify_v5_intended_update_serving` with `docs/plans/2026-09-29/v5-repair-2026-source-lock.json`, `--release-tag 20260929-p1`, reading Preview R2; no `--apply`, nothing written.
- **Committed (old) rule: 0 failures. Corrected rule: 32 spread failures, every one an `Away` pick** ("selected quote differs from original eligible best quote"). No total failures under either rule.
- Reading: the served `v5repair-20260929-p1` artifacts selected the highest home-signed line for Away spreads, which is the worst line for the bettor. The old verifier encoded the same ordering, so it could not catch it. This is the defect Task 1 fixes; it is now confirmed in served data, not only in code.
- Sizing (below) answers the earlier open questions.

### Away-spread sizing, Weeks 0–5 (verified: my own computation from read-only Preview R2 reads; user-approved read-only; no database or R2 writes; scratch scripts in the session scratchpad)
Definitions: "Away" = model direction Away (`prediction + canonical <= 0`, ties Away). "Diverged" = more than one distinct eligible spread among the linked quotes captured before kickoff. "Conceded" = served home-signed line minus the lowest eligible line (points the Away side lost versus the best line). Weeks 0–4 are `v5repair-20260929-p1`; Week 5 is the selected frozen run `v5repair-20260929-p2`.

| Week | Away-direction games | Served bet = Away | Books diverged = wrong line | Points conceded | Max |
|---|---|---|---|---|---|
| 0 | 4 | 4 | 4 | 9.5 | 3.0 |
| 1 | 27 | 24 | 14 | 7.5 | 1.0 |
| 2 | 30 | 26 | 14 | 9.5 | 2.5 |
| 3 | 28 | 26 | 0 | 0 | 0 |
| 4 | 26 | 24 | 0 | 0 | 0 |
| **0–4** | **115** | **104** | **32** | **26.5** | 3.0 |
| 5 (p2) | 16 | 13 | 2 | 1.0 | 0.5 |

- The 32 Weeks 0–4 wrong-line games equal the 32 verifier failures. Every wrong-line row is an Away direction. Home-direction rows: 0 wrong-line in Weeks 0–5 (100 rows in Weeks 0–4, plus Week 5). Weeks 3 and 4 had no divergence, so the defect was inactive there.
- Week 5 (frozen, immutable): 2 wrong-line Away games (401856819, 401864513), 1.0 point conceded in total. Its p1 candidate run, not selected, shows none. Week 5 grading impact was not assessed: the week is ungraded. Nothing was changed.
- **Grading impact, Weeks 0–4:** of 29 wrong-line games with an Away bet, re-scoring at the best line changes **one** result: Week 1 loss → push. 18 losses and 10 wins are unchanged; 3 wrong-line games carried No Bet. Net effect on the record is one loss becoming a push.
- **Stored grades:** for all 199 Home/Away bets in Weeks 0–4, the artifact's stored `Spread Bet Result` equals a recomputation from the frozen selected side and served line against certified finals (199/199). Limit: this compares the serving artifact's column; I did not query Neon `prediction_grades`.
- Wrong-line Weeks 0–4 game IDs: 401856634, 401856665, 401856670, 401856677, 401856682, 401856778, 401856780, 401856781, 401858201, 401858207, 401858221, 401858423, 401858425, 401858426, 401858429, 401858430, 401858432, 401858434, 401858437, 401858438, 401858440, 401858441, 401858443, 401858445, 401860881, 401860883, 401862703, 401864494, 401864570, 401864577, 401866414, 401867796.
- Interpretation: the defect is small in effect (26.5 points over 32 games, at most 3 per game; one grade flips) but real. Weeks 0–4 are retrospective replays, so republishing them is a Window 2 replay concern, not a mutation of frozen evidence. The Week 5 frozen run stays as is; it is not prospective evidence of the corrected rule.
- Consequence: Window 1 must republish the corrected selections (and re-grade where a frozen Away spread line changes). Frozen Week 5 records are immutable; their handling needs its own decision.
- Scratch diagnostics are in the session scratchpad, not the repo.

## Release receipt (Task 4) — PENDING fields need user-run steps
| Item | Value |
|---|---|
| Code SHA | PENDING (after the user commits) |
| Preview venue coverage (all published games have city) | PENDING: `publish_game_venues.py --require-city` dry run, then publish |
| Preview verifier output | PENDING: run `verify_v5_intended_update_serving.py` on served and rollback runs |
| Original stored grades reproduced | PENDING |
| Input/output identities | PENDING: snapshot identities from the Preview publish |
| Known limitation | Window 1 changes presentation, selection and team stats only; the V5 rating lineage is unchanged until Window 2. Window 1 masks missing PPA in display; stored zeros remain. |
| Rollback | Re-select the prior run via the existing selection tools; no ratings, forecasts or frozen records change. |
| Production decision | Not requested until the above are filled |

## Handoff Notes
- Proposed code commit (stage by filename, not directories): the modified Window 1 code and test files in `git status` (not the docs already in the first commit), plus `scripts/pipeline/verify_v5_intended_update_serving.py`, `src/cks_picks_cfb/data/market_integrity.py`, `tests/test_market_integrity.py`, `tests/test_window1_selection_rules.py`, `tests/test_frozen_grading.py`, `tests/test_weekly_inference.py`, `web/src/lib/performance-accuracy.ts`, `web/src/lib/performance.test.ts`, `web/src/test/fixtures/publication.ts`, `web/src/lib/slate.ts`, and this log. Do not stage `__pycache__`.
- Proposed message: `fix: window 1 selection tie rules, null-lean handling and accuracy-only performance`

**tags:** ["data-integrity", "window1", "release-receipt"]
