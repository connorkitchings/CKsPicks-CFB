# Session: Repaired V5 2026 ratings and forecast counterfactual

## TL;DR

- **Worked On:** Applied the intended one-game-one-observation repair to the certified 2026 Week 0–5 rating inputs, reconstructed paired forecasts, and scored completed games.
- **Outcome:** On 215 retrospectively reconstructed completed games, margin MAE is `15.909` for certified V5, `15.376` for repaired live ratings with the frozen bridge, and `14.512` with a through-2025 repaired bridge refit. Total changes are small. Concrete 2026 ratings and three-arm forecasts are saved under `docs/research/`.
- **Plan Contract:** [V5 estimator review amendment](../../docs/plans/2026-09-28/v5-estimator-three-way-review.md) (research-only 2026 follow-up).
- **Approval / Status:** User explicitly requested that 2026 ratings and resulting predictions be tried. No production or publication change was authorized or made.
- **Blockers:** None for local research. Dedicated V6 R2 research bucket remains unprovisioned.
- **Next:** Collect Week 5 outcomes prospectively and review paired performance before any separate production decision.

## Context and Decisions

- Held the accepted 2026 priors, prior-season scales, PPP measurement, `k=8`, opponent-adjustment passes, six-hour/earlier-week rule, offsets, schedule, and forecast feature set fixed.
- Used three arms to distinguish 2026 rating replacement from historical bridge retraining: certified V5 control, rating-only repair, and full repair with an alpha-10 Ridge refit on repaired historical states.
- Classified Weeks 0–4 as retrospective because their earlier states were rebuilt from the certified Week 4 capture. Week 5 has 56 unscored paired forecasts.

## Work Completed

- Added read-only pinned Preview R2 source importer, 2026 additional-scale support in the research adjustment provider, and local counterfactual runner.
- Reproduced all 112 frozen Week 5 control forecast means and all 430 exported-bridge completed-game control means within `7.11e-15`.
- Built 1,084 repaired pregame team-role states, complete predictions for 271 game keys in all three arms, paired completed-game scores, weekly diagnostics, and a 2,000-replicate paired game bootstrap stratified by week.
- Published the [research report](../../docs/research/2026-09-28-v5-2026-counterfactual.md), [rating CSV](../../docs/research/2026-09-28-v5-repaired-2026-pregame-ratings.csv), [prediction CSV](../../docs/research/2026-09-28-v5-repaired-2026-predictions.csv), and [result JSON](../../docs/research/2026-09-28-v5-repaired-2026-results.json).

## Files Modified

- `src/cks_picks_cfb/ratings_lab/adjusted_game.py` — optional post-2025 scale computation using certified prior-season terminal values.
- `scripts/research/v5_2026_source_import.py` — pinned, read-only 2026 import and exact control prediction reconstruction.
- `scripts/research/v5_2026_counterfactual.py` — 2026 rating replay, fixed/refit forecast arms, full-population parity gates and paired evaluation.
- `tests/ratings_lab/test_v5_intended_update.py` — preceding-season scale gate.
- `docs/research/2026-09-28-v5-2026-counterfactual.md` and companion CSV/JSON — results and concrete ratings/predictions.
- `docs/plans/2026-09-28/v5-estimator-three-way-review.md`, `docs/index.md`, `docs/modeling/v5_status.md` — authorized follow-up scope and current research status.

## Validation

- [x] Source importer rerun against pinned read-only Preview R2 parents.
- [x] Control parity gates: 430 completed target rows and 112 frozen Week 5 target rows.
- [x] 46 scoped ratings-lab, live-forecast, and V5 replay tests passed.
- [x] Ruff format check and lint on touched Python files.
- [x] `mkdocs build --clean` passed (existing cross-root link warnings only).
- [x] `git diff --check` passed.

## Amendments and Blockers

- The user's follow-up was added to the existing research contract. The full repaired arm includes historical bridge retraining; the rating-only arm isolates the 2026 rating replacement.
- The external local drive was not mounted, so read-only Preview R2 supplied the certified inputs and full local Parquet traces are under `/private/tmp/cfb-v5-2026-counterfactual-results/`. Versioned CSVs and JSON preserve the concrete outputs in the repository without creating `./data/`.

## Handoff Notes

- **Resume at:** Score the frozen Week 5 paired slate after certified finals, then assess stage-wise and prospective behavior before a promotion contract.
- **Watch out for:** The 215 completed-game forecasts were reconstructed retrospectively and are not prospective picks. The total MAE differences have bootstrap intervals spanning zero. No git commit was made; proposed commit message: `research: replay repaired V5 ratings on 2026 forecasts`.

**tags:** ["ratings", "v5", "2026", "research", "forecast"]
