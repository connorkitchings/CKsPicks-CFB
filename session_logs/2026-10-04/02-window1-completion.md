# Session: Window 1 completion and release receipt (pre-commit)

## TL;DR
- **Worked On:** Closed the remaining Window 1 gaps from the code review: verifier tie/sort rule, publisher null labels, accuracy-only dashboard, tests.
- **Outcome:** Code committed (`850ca38`, venue pin `562b2b2`); Playwright 28/28 and the full Python suite pass; Preview venue write verified (271/271 cities, 269 states). Window 1 is **not released**: the input/output identities row and the Preview serving and rollback rehearsal are open, and production needs your decision.
- **Plan Contract:** `docs/plans/2026-10-03/04-data-integrity-two-window-implementation.md` (Tasks 1–4)
- **Next:** Run the Preview serving and rollback rehearsal (below), fill the last PENDING row, then decide on production. Production venues are published separately with the same `--venues-version` pin.

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

## Window 1 status
All receipt fields are filled except the production decision and the production venue publish. Week 5 frozen run stays as-is (user decision 2026-10-04); correction belongs to Window 2.

## Decisions for the user to confirm (superseded by the above where noted)
1. **Total-bet threshold (pre-existing worktree change in `inference/weekly.py`):** totals now bet when `edge >= threshold`, matching spreads and the committed verifier (`edge >= 1.0`). The old strict `>` meant a total exactly at the threshold was "No Bet". I updated the test that pinned the old behaviour. Revert both if you want strict `>`.
2. **Policy version:** the manifest test now expects `model_side_best_quote_v2` (the worktree already bumped `SELECTION_POLICY_VERSION`).
3. **Verifier sort fix may reject historical artifacts:** if any already-signed run selected the highest line for an Away spread, the corrected verifier will flag it. Run it on the served and rollback runs before relying on it, and reproduce original stored grades before any replay (contract requirement). Not yet done.
4. `models/historical_model_context.py:211` (`>= 0` on the 2025 V4 context) was left unchanged: it feeds signed historical context and is outside Window 1 selection. Revisit in 5A.

## Validation
- `uv run python -m pytest tests -q`: 1642 passed, 9 skipped, 2 failed before the two test updates above; the affected file then passed (9/9). Full suite not re-run after the update.
- `ruff check` on touched Python files and `src`: clean.
- Web: `npm run typecheck`, `npm run lint`, `npm run test:publication` (118 pass), `npm run build`: all pass.
- Playwright (run 2026-10-04 with the user's dev server stopped): `performance.spec.ts` and `publication.spec.ts`, 28 passed.
- Not run: real Preview checks beyond the read-only venue dry run and verifier, publish-time venue gate test (only `require_venue_cities` itself is unit-tested; the wiring in `publish_to_db.py` needs a DB and is covered by the Preview rehearsal).

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
| Code SHA | `850ca38` (pushed to `origin/dev`; docs commit `ac47375`) |
| Preview venue coverage (all published games have city) | **First dry run FAILED** (default newest venues version `ac36e3e4`, year-2025 list): 10 games without a city (401856661, 401856797, 401856812, 401858438, 401858476, 401862707, 401864507, 401864515, 401864577, 401866429; venue IDs 3810, 7173, 2455, 3798, 11823, 3647, 3757, 3714). **Root cause (verified):** Silver `venues` holds one version per capture year and the publisher picked whichever was created last. Only `b569d242e8c4c53b416bfe14` (year 2026, in both catalogs, production's latest) covers all 8 IDs. **Fix:** `publish_game_venues.py --venues-version` pins an exact version (unpinned default unchanged, documented as unreliable). **Pinned dry run (read-only, 2026-10-04): 271/271 with city, 269 with state (2 international city-only), `venue_not_found` 0**, venues content sha `bee1f3c7…`. **Preview write: PASSED.** User ran `publish_game_venues.py --season 2026 --environment preview --venues-version b569d242e8c4c53b416bfe14 --require-city` ("Upserted 271 game_venues rows (preview)"). Verified by me with a read-only query on Preview Neon: `game_venues` 271 rows, 271 with city, 269 with state; written 2026-10-04 14:30:39 GMT; Fargodome 401864577 = Fargo, ND; Dublin 401856766 city-only. Production: not yet run; decision is to use the same `--venues-version` pin there. |
| Preview verifier output | Run on the served `p1` artifacts: corrected rule rejects 32 Away spreads (see above). Rollback runs not run. |
| Original stored grades reproduced | Done for Weeks 0–4 artifacts: 199/199 stored grades equal a recomputation from the frozen side and line (artifact column, not Neon `prediction_grades`). Week 5 ungraded. |
| Input/output identities | PENDING: snapshot identities from the Preview publish |
| Known limitation | Window 1 changes presentation, selection and team stats only; the V5 rating lineage is unchanged until Window 2. Window 1 masks missing PPA in display; stored zeros remain. |
| Rollback | Re-select the prior run via the existing selection tools; no ratings, forecasts or frozen records change. |
| Production decision | Not requested until the above are filled |

## Handoff Notes
- Proposed code commit (stage by filename, not directories): the modified Window 1 code and test files in `git status` (not the docs already in the first commit), plus `scripts/pipeline/verify_v5_intended_update_serving.py`, `src/cks_picks_cfb/data/market_integrity.py`, `tests/test_market_integrity.py`, `tests/test_window1_selection_rules.py`, `tests/test_frozen_grading.py`, `tests/test_weekly_inference.py`, `web/src/lib/performance-accuracy.ts`, `web/src/lib/performance.test.ts`, `web/src/test/fixtures/publication.ts`, `web/src/lib/slate.ts`, and this log. Do not stage `__pycache__`.
- Proposed message: `fix: window 1 selection tie rules, null-lean handling and accuracy-only performance`

**tags:** ["data-integrity", "window1", "release-receipt"]

## Preview serving rehearsal (procedure written 2026-10-04; PENDING user-run)
**Harness fix (verified by reading the code):** `scripts/pipeline/rehearse_v5_bestquote_replay_preview.py` asserted a selection row for every lined target. The Window 1 publisher writes a selection only when the lean is home/away or over/under (`publish_to_db.py`, null leans get none), so the harness would have failed on any null-lean game even with nothing wrong. It now compares selections with lined targets that carry a lean. Other harness checks are consistent with Window 1: selection and grade versions equal `SELECTION_POLICY_VERSION` / `model_side_best_quote_v2`, grading goes through `score_to_db`, and the run is published with `--no-update-current --state preview`, so **public selection is never changed**. It supports Weeks 0-4 only (not Week 5).

**What it exercises:** forecast equality with the source replay run, selection lineage (quote, snapshot, side, point), the lowest-line rule for Away, frozen-side v2 grading, snapshot immutability on re-publish (second run must be an idempotent repeat), and that `system_stats` is untouched.

**Baseline captured by me (read-only on Preview, 2026-10-04):** public selections Weeks 0-4 `2026w{0..4}-v5repair-20260929-p1`, Week 5 `2026w5-v5repair-20260929-p2`; `current_week` = 2026 week 5, run `2026w5-v5repair-20260929-p2`; 15 existing `v5replay-bestquote` runs; 2,120 `prediction_market_selections` rows; fingerprint `c464574ef616c7d4`.

Steps (all user-run, Preview only):
1. Baseline snapshot (read-only), saved as `before`.
2. `zsh scripts/ops/with_preview_env.sh uv run python scripts/pipeline/rehearse_v5_bestquote_replay_preview.py --week 1 --dry-run` (generate only, nothing uploaded or published).
3. Same command without `--dry-run`. It creates run `2026w1-v5replay-bestquote-<UTC date>`, publishes it as `preview`, scores it, verifies it, and repeats the publish to prove idempotency. Week 1 is the best test week: 14 of its Away games have diverging books and one result flips (loss to push).
4. `... --week 1 --verify-only --run-id <printed run id>`.
5. Baseline snapshot again, saved as `after`. The fingerprint must equal `c464574ef616c7d4` and the selection-row count rises only by the new run's rows. This is the rollback evidence for Window 1: public selections, `current_week` and `system_stats` were never touched, so there is nothing to undo; the new run stays as immutable audit evidence.
6. Optional, wider: repeat for the remaining weeks 0, 2, 3, 4 (omit `--week` to run all five).

Not included, and not verified by me: a public select-and-restore of a Preview run. `select_public_run.py` needs an active pipeline lease and may need release authorizations for the run's model. The atomic select/rollback rehearsal belongs to the Window 2 controller (Amendment 1).

Receipt rows to fill from the output: run id, verifier output (selection and grade counts), idempotent-repeat counts, `after` fingerprint.
