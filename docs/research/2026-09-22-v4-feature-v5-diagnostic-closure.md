# V4 Feature-v5 Diagnostic Closure: Pooled Week 1+2 Verdict and Causal Interpretation

> **Date:** 2026-09-22
> **Contracts:** [`docs/plans/2026-09-13/01-v4-feature-v5-diagnostic-closure.md`](../plans/2026-09-13/01-v4-feature-v5-diagnostic-closure.md) (closure authority) executing Task 5 of [`docs/plans/2026-09-10/2026-v5-shadow-rebuild-diagnostic.md`](../plans/2026-09-10/2026-v5-shadow-rebuild-diagnostic.md) (Amendments 1–3 preserved)
> **Scope:** V4 inference diagnostic on feature schema v5. Independent of the V5 ratings-successor program; not prospective evidence for it.
> **Production impact:** None. V4 production runs, serving tables, and the official record are unchanged (verified before/after).

## Executive summary

The pre-registered kill criterion resolves to **cause not confirmed**: the pooled
Week 1+2 shadow spread win rate is **38.46% (35-56-1 on 91 graded decisions)**,
below the 45% branch of the pre-registered threshold (≥50% confirmed, <45% not
confirmed, 45–50% inconclusive).

The causal interpretation is stronger than the threshold label alone: the v5
shadow predictions are **value-identical to the official V4 predictions on all
100/100 games (Weeks 0–2)** — maximum absolute drift 0.0 on every spread and
total prediction, bet direction, and line. Value-identical predictions cannot
produce different forecast performance. **The v4/v5 feature-serving mismatch is
refuted as the cause of the 2026 V4 spread underperformance.** The
underperformance is a property of the frozen model + 2026 market/game
environment, not of which feature schema served inference.

## Background

V4 production 2026 runs bound `point_in_time_matchups` (no preseason track)
while the champion bundle `week0-2026-v4-strict-20260818-r2` was trained on
`point_in_time_matchups_v5` (strict track with preseason features). The
diagnostic rebuilt artifact-level v5 Gold for Weeks 0–2 in Preview only, with
the two-tier parity gate (lineage confinement + exact prediction control)
proving zero code-drift confounding, then generated shadow predictions
(`shadow-2026-v5-w{0,1,2}`) at the original publish cutoffs with the exact
frozen production market references. Weeks 0/1 were scored in the 2026-09-10
session; Week 2 awaited finals. This closure scores Week 2 against the Week 2
close outcomes and renders the pooled verdict.

## Grading inputs (reverified before scoring)

| Week | Shadow predictions (Preview R2) | Official run | Final outcomes ref (immutable prod pipeline run) |
| --- | --- | --- | --- |
| 0 | `artifacts/preview/predictions/year=2026/week=0/run_id=shadow-2026-v5-w0/predictions.csv` (8 rows; as-of 2026-08-20T13:19:14Z) | `2026w0-55de0317120d` (scored) | `…/pipeline-runs/8d2e78ab92634bd0abfa76f9f169cb6f/game_outcomes_ref.json` → `game_outcomes@` … (completed, full 8/8 coverage) |
| 1 | `…/run_id=shadow-2026-v5-w1/predictions.csv` (43 rows; as-of 2026-09-03T05:00:00Z) | `2026w1-b2c739321e5d` (scored) | `…/pipeline-runs/edb91b1594534ff987793f0e2657dc03/game_outcomes_ref.json` (43/43) |
| 2 | `…/run_id=shadow-2026-v5-w2/predictions.csv` (49 rows; as-of 2026-09-08T17:50:00Z; manifest SHA `c66240a3…`; parents: games `5dabf61a`, market snapshot `459c80d0`, quotes `ede4a9a7`, v5 matchups `4d89b391`, bundle `72429375…`) | `2026w2-43b25511a100` (frozen) | `…/pipeline-runs/cb75ca881f3a49d5bd115c4fdeaa7dcb/game_outcomes_ref.json` → `game_outcomes@e35fc53701a235148f0bd306` (completed rows deduplicated; full 49/49 coverage, verified before scoring and enforced fail-closed by the scorer) |

All Week 2 shadow cutoffs precede the first Week 2 kickoff (Fri 2026-09-11
23:30 UTC). The W2 shadow was scored via the artifact-only path
(`score_weekly_bets.py --from-artifact … --upload-artifact`); the rerun was
idempotent (byte-identical, no collision). `score_to_db.py`, publish, freeze,
and serving upserts were never invoked; `prediction_runs`/`predictions`/
`prediction_grades` counts and `current_week` pointers were identical
before/after in both databases (prod 52/2492/4657, (2026, 4, `2026w4-da5d98761831`);
preview 19/821/1524, (2025, 16, `v4replay-2025-w16`)).

## Paired prediction identity (independently recomputed)

Inner join on `game_id`, shadow vs official, per week — 8/43/49 games, all
1:1, full outcome coverage:

- `Spread Prediction` and `Total Prediction` parsed-float max |diff| = **0.0** (every game, both targets).
- `Spread Bet` / `Total Bet` directions equal; `home_team_spread_line` / `total_line` equal.

This independently reproduces the 2026-09-10 interim and Week 2
prediction-equivalence findings and extends them through final grading.

## Results

Independent grading from raw artifacts (no scorer import), reproducing all
three uploaded scorer artifacts exactly (counts per target per week).
Convention (frozen from the existing scorer): win rate = wins/(wins+losses);
pushes and explicit sub-threshold `No Bet` rows are excluded from the
denominator; spreads are always directional (Home/Away); totals carry explicit
`No Bet` below the edge threshold.

### Shadow (= official, predictions identical) per week

| Week | n | Spread W-L-P | Spread graded / No Bet | Spread win rate | Total W-L-P | Total graded / No Bet | Total win rate | Spread MAE / bias | Total MAE / bias |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 8 | 2-6-0 | 8 / 0 | 25.0% | 5-3-0 | 8 / 0 | 62.5% | 16.54 / +1.13 | 8.94 / +1.39 |
| 1 | 43 | 16-26-1 | 42 / 0 | 38.1% | 13-28-0 | 41 / 2 | 31.7% | 21.95 / −5.42 | 16.42 / +1.31 |
| 2 | 49 | 19-30-0 | 49 / 0 | 38.8% | 21-20-0 | 41 / 8 | 51.2% | 16.57 / +0.28 | 15.06 / −2.20 |
| **Pooled W1+W2** | **92** | **35-56-1** | **91 / 0** | **38.46%** | 34-48-0 | 82 / 10 | 41.5% | 19.09 / −2.38 | 15.70 / −0.56 |

Week 0 (n=8) is reported separately with its small-sample caveat and excluded
from the verdict, as pre-registered. MAE/bias are computed on all n predictions
per week against final margins/totals; shadow and official are identical by
construction.

### Official graded record (production `prediction_grades`, read-only)

- W0: identical to shadow (2-6 / 5-3).
- W1 spread: identical (16-26-1). W1 totals: official **14-29** (43 graded — the close graded the two sub-threshold Unders directionally) vs shadow 13-28 with 2 No-Bet (41 graded). This is the known grading-convention difference recorded 2026-09-10, not a prediction difference.
- W2: identical (19-30 spread; 21-20 total — the close also left the 8 sub-threshold totals ungraded).
- Consistency check: official YTD through W2 (spread 37-62-1, total 40-52) equals the sum of the official weekly grades.

## Threshold outcome and causal interpretation

**Pre-registered threshold (historical label):** pooled W1+W2 shadow spread win
rate **38.46% < 45% → "cause not confirmed"** — report overfit/season-effect/
inference-bug as open hypotheses with the evidence.

**Causal assessment (approved interpretation amendment):** an absolute win rate
alone cannot establish that the feature mismatch caused underperformance. Under
identical bundle, cutoffs, markets, game population, and code (two-tier parity
gate), changing the served features from v4 to v5 changed **zero** predictions
across 100/100 games. Therefore:

1. The feature-serving mismatch is **refuted** as the cause of the 2026 spread
   underperformance. Restoring the training-time feature schema moves nothing.
2. The 2025→2026 spread drop (~51% → ~38%) must arise from the frozen model's
   predictions relative to the 2026 game/market environment — consistent with
   mean reversion of a modest 2025 edge, sharper or differently-distributed
   early-season lines, or genuine degradation in the model's early-season
   regimes (Weeks 1–2 skew heavily to `game_1`/`game_2` routes), not from
   serving-time features.
3. No inference bug is indicated: the v4control prediction controls reproduced
   the original production predictions exactly on all weeks, and shadow vs
   official outputs are bit-identical end to end.

**Open hypotheses (evidence-bounded):** (a) 2025 overperformance / mean
reversion — binomial context: 35 wins in 91 decisions is ~2.2 SD below a fair
50% coin, i.e. clearly below break-even but also compatible with a true 2026
ability modestly below 50%; (b) early-season regime weakness — W1 spread bias
−5.42 (home margins overpredicted) and W1 MAE 21.95 vs W2 16.57; (c) market
environment (2026 lines vs 2025); (d) sample variance across only three weeks.
No replacement significance threshold is introduced.

## Boundary statement

This diagnostic closes a V4 question only. It does not select the V5 ratings
model, create prospective evidence for Contract 06, authorize any production
change, or modify the official 2026 record. Any production response (if
pursued) is a separate future contract. The 8 sub-threshold Week 2 totals and
2 sub-threshold Week 1 totals remain No-Bet/ungraded under the scorer
convention; the official record keeps its own close-time conventions as
recorded above.

## Reproduction

Scored artifacts: `artifacts/preview/scored/year=2026/week={0,1,2}/run_id=shadow-2026-v5-w{0,1,2}/scored.csv`
(+ signed manifests, immutable, idempotent rerun verified). Scoring command
(Week 2; Weeks 0/1 identical pattern with their outcome refs):

```bash
zsh scripts/ops/with_preview_env.sh uv run python scripts/pipeline/score_weekly_bets.py \
  --year 2026 --week 2 --run-id shadow-2026-v5-w2 --from-artifact \
  --prediction-artifact-path artifacts/preview/predictions/year=2026/week=2/run_id=shadow-2026-v5-w2/predictions.csv \
  --outcomes-ref-uri artifacts/production/pipeline-runs/cb75ca881f3a49d5bd115c4fdeaa7dcb/game_outcomes_ref.json \
  --upload-artifact
```

All counts, metrics, identity assertions, and threshold labels in this report
were recomputed independently from the raw prediction + outcomes artifacts and
cross-checked against the uploaded scorer artifacts and the production grades.
