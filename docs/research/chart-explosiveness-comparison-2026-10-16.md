# Explosiveness measures: pinned 2026 Week 7 revision comparison

**Date:** 2026-10-16. **Decision:** owner selection pending. This report describes two candidates; it does not select a public metric or establish predictive superiority. Public charts retain Efficiency and PPA/play. The [approved chart contract](../plans/2026-10-16/02-chart-purpose-and-explosiveness.md) defines the initial delivery and separate publication gate.

## Population and definitions

The comparison uses the exact immutable Silver schedule, finals, byplay and teams references in `conf/season/2026/revision_manifest_w7_v1.json`, read from Preview R2. All four SHA-256 checks passed before Parquet decoding. The revision manifest SHA-256 is `208a4a5b7b070360e78909c78f3d6ed2efcf255ce8b5d8628110e939612040f6`. No fresh ingestion, database query, model change, migration, serving publication or activation occurred.

Game eligibility comes directly from `build_team_game_stats`: completed regular-season FBS-vs-FBS games before active Week 7, using the pinned roster and final-score presence. Plays use the shared `scrimmage_play_mask`: regulation, no garbage time, penalties, two-point tries, dead plays or special teams (including kicking play types missed by older special-teams flags). This is the same population as existing charts. Weeks 0–6 contain 329 eligible games, 658 team-game observations and 40,461 eligible plays. No Week 7 outcome enters any window. Historical windows are reconstructions from this revision and may reflect later source corrections; they are not frozen historical publications.

- **20+ yard play rate:** number of eligible finite-yardage plays gaining at least 20 yards divided by all eligible finite-yardage plays. Valid yardage counts even when success or PPA is missing.
- **Yards per successful play:** yardage sum on eligible plays with `success == 1` and finite yardage divided by the count of those same plays. Unsuccessful-play yardage never enters this numerator. This is not IsoPPP, which concerns points per successful play.
- **Success rate:** success sum/count with its own finite-success exposure. **PPA/play:** CFBD Predicted Points Added sum/count with finite PPA, respecting `ppa_missing`. Neither denominator is reused for a candidate metric.
- **Defense allowed:** identical observations attributed to the opponent. Smaller is better for defensive national competition ranks; larger is better for offense. Ties share the minimum occupied rank. No combined rank is constructed.
- Zero exposure remains null, while observed zero explosive plays means a rate of zero. Each cumulative window pools counts and sums, rather than averaging game means. Distribution summaries below give equal weight to observed teams; pooled values weight the appropriate plays.

The known non-monotonic score limitations and source-repair caveats in [known issues](../data/known_issues.md) still apply. This report inherits the chart eligibility flags without treating source correctness as newly certified.

## Coverage

| Through week | Games | Observed teams per side | Eligible/valid-yardage plays | Successful valid-yardage plays | Valid PPA plays | Team play exposure range |
|---|---:|---:|---:|---:|---:|---|
| 2 | 100 | 137/138 | 11,974 | 4,941 | 11,928 | 21–226 |
| 3 | 157 | 138/138 | 19,001 | 7,922 | 18,888 | 55–268 |
| 4 | 215 | 138/138 | 26,260 | 10,990 | 26,105 | 106–343 |
| 5 | 271 | 138/138 | 33,176 | 13,919 | 32,981 | 148–412 |
| 6 | 329 | 138/138 | 40,461 | 17,012 | 40,233 | 199–475 |

Both candidates have identical team coverage in this sample. Northwestern has no eligible FBS game through Week 2 and remains null on both sides; all 138 teams have observations from Through Week 3 onward. By Through Week 6, yardage exposure is 40,461, success exposure is 40,410 and PPA exposure is 40,233 on each side: 51 missing/nonfinite success observations and 228 missing/nonfinite or explicitly missing PPA observations do not reduce valid-yardage exposure. No yardage observation is missing/nonfinite in this pinned population. Missing-yardage and zero-success behavior is covered by direct edge-case tests, not claimed as an observed real-data subgroup.

## Distributions and pooled levels

Rate values below are percentages. Yards values are yards per successful play. The central range is the 10th–90th team percentile. Full min/max, team means and all independent counts/sums are retained in the artifact tables.

| Through week | Side | Rate median [p10, p90] | Yards median [p10, p90] | Pooled rate | Pooled yards |
|---|---|---|---|---|---|
| 2 | offense | 6.06% [2.32, 11.00] | 12.10 [9.25, 15.79] | 6.52% | 12.28 |
| 2 | defense | 6.40% [3.09, 10.34] | 12.00 [9.77, 14.93] | 6.52% | 12.28 |
| 3 | offense | 6.63% [3.56, 10.73] | 12.16 [10.12, 14.47] | 6.74% | 12.27 |
| 3 | defense | 6.67% [3.71, 9.68] | 12.14 [10.51, 14.19] | 6.74% | 12.27 |
| 4 | offense | 6.87% [3.97, 9.61] | 12.18 [10.49, 14.01] | 6.80% | 12.26 |
| 4 | defense | 6.54% [4.37, 9.74] | 12.22 [10.62, 14.22] | 6.80% | 12.26 |
| 5 | offense | 6.74% [4.24, 9.38] | 12.18 [10.66, 13.94] | 6.77% | 12.28 |
| 5 | defense | 6.62% [4.34, 9.08] | 12.25 [10.63, 14.10] | 6.77% | 12.28 |
| 6 | offense | 6.58% [4.69, 9.13] | 12.22 [10.81, 13.55] | 6.74% | 12.24 |
| 6 | defense | 6.60% [4.54, 8.66] | 12.21 [10.78, 13.81] | 6.74% | 12.24 |

Pooled offense and defense levels match by construction because every eligible play has one offensive and one defensive observation. Through Week 2, offense rate spans 0.00–17.65% and yards/success spans 6.50–22.25; by Through Week 6 these ranges are 2.42–11.65% and 9.40–15.68. The narrower later sample range is descriptive accumulation, not proof of future stability.

## Relationships and rank disagreements

Pearson correlation on team values is shown first; Spearman rank correlation is in parentheses. Defense correlations use raw allowed values, not inverted values.

| Through week | Offense candidate correlation | Defense candidate correlation |
|---|---|---|
| 2 | 0.721 (0.753) | 0.702 (0.775) |
| 3 | 0.715 (0.730) | 0.736 (0.741) |
| 4 | 0.703 (0.730) | 0.766 (0.787) |
| 5 | 0.701 (0.713) | 0.796 (0.796) |
| 6 | 0.696 (0.712) | 0.796 (0.761) |

| Through Week 6 side | Candidate | Success-rate correlation | PPA/play correlation |
|---|---|---|---|
| offense | 20+ yard rate | 0.507 (0.477) | 0.623 (0.608) |
| offense | Yards/success | 0.006 (0.036) | 0.309 (0.319) |
| defense | 20+ yard rate | 0.428 (0.419) | 0.564 (0.567) |
| defense | Yards/success | 0.070 (0.054) | 0.325 (0.319) |

The yardage threshold and successful-play conditional average produce related but materially different orderings. Through Week 6, median absolute candidate-rank disagreement is 18 offense places and 14 defense places; maximum gaps are 105 and 90 places. A weaker association with success rate is not itself a reason to select a metric, and a stronger association with PPA is not a predictive validation. The candidates share underlying plays and are schedule-, field-position- and sample-dependent; this report performs no opponent adjustment or prospective test.

### Representative disagreements

These examples explain the observed arithmetic, not causal team quality. Game IDs below identify pinned schedule games and are not release IDs.

| Window / team-side | 20+ plays / valid yards | Rate / national rank | Successful yards / successful plays | Yards/success / national rank |
|---|---|---|---|---|
| Through 2, Louisiana Tech offense | 2/48 | 4.17% / 111 | 98/5 | 19.60 / 2 |
| Through 2, Air Force offense | 6/66 | 9.09% / 28 | 332/33 | 10.06 / 114 |
| Through 6, Charlotte offense | 9/215 | 4.19% / 132 | 834/64 | 13.03 / 27 |
| Through 6, Buffalo defense | 13/243 | 5.35% / 27 | 1370/102 | 13.43 / 117 |
| Through 6, San Diego State defense | 27/355 | 7.61% / 100 | 1935/173 | 11.18 / 23 |

- **Louisiana Tech offense, Through Week 2:** its only eligible game is a 14–45 loss at LSU (`401867796`). Five successes out of 48 eligible plays give a 10.42% success rate and −0.695 PPA/play. A single 67-yard successful gain supplies 67 of the 98 successful yards. Removing it changes yards/success from 19.60 to 7.75 (31/4), while 20+ rate changes from 2/48 (4.17%) to 1/47 (2.13%). A high conditional successful-play average can coexist with very few successes and poor overall efficiency. LSU's defensive exposure mirrors those same Louisiana Tech plays.
- **Air Force offense, Through Week 2:** the sole eligible game is a 32–38 loss against North Dakota State (`401864502`), with 33 successes in 66 plays, six 20+ plays and 332 successful yards. A larger pool of moderate successful gains yields the 28th-ranked threshold rate but 114th-ranked yards/success. Its longest gain is 35 yards; this differs from Louisiana Tech's tiny successful-play denominator.
- **Charlotte offense, Through Week 6:** nine 20+ gains among 215 plays across five eligible games rank 132nd, while 834 successful yards / 64 successes rank 27th at 13.03 yards/success. Success rate is 29.77%, PPA/play −0.205. Against Louisiana in Week 4 (`401862780`, 7–34), there are zero 20+ plays among 44 plays but 75 yards on nine successes. Against Memphis in Week 5 (`401862787`, 8–59), two 20+ plays occur among 31 eligible plays while nine successes yield 195 yards. The counts show how a limited successful subset can carry long gains despite sparse success overall. Garbage-time exclusion also limits this to the chart's selected plays, not full box-score output.
- **Buffalo defense, Through Week 6:** 13/243 20+ gains allowed ranks 27th but 1,370 yards / 102 opponent successes ranks 117th at 13.43 yards/success. In the 13–55 Penn State game (`401858456`, Week 3), 40 eligible opponent plays include six 20+ gains and 393 yards on 19 successes; in the 23–8 Toledo game (`401866437`, Week 6), 62 opponent plays include only one 20+ gain and 223 yards on 21 successes. Pooling retains their unequal exposures.
- **San Diego State defense, Through Week 6:** 27/355 20+ gains allowed ranks 100th but 1,935/173 successful yards ranks 23rd at 11.18 yards/success. Opponents succeed on 48.87% of plays with valid success. Against Texas State (`401860900`, Week 5, 31–29), 102 eligible opponent plays yield eight 20+ gains and 537 yards on 48 successes. Against Oregon State (`401860902`, Week 6, 14–66), 50 eligible opponent plays yield six 20+ gains and 329 yards on 32 successes. The successful-play average answers a different question from frequency per all plays.

## Longest-gain and week-to-week sensitivity

Remove exactly one finite longest-yardage play from every team-side-window, then recompute both candidate numerators and denominators independently. Ties use the first retained pinned row. A longest gain that is unsuccessful does not enter yards/success either before or after removal. National sensitivity ranks are recomputed after **all teams** lose their own longest play; another team's change can move a team's rank even when its own metric is unchanged. This is a stress test, not a sampling confidence interval.

The rate change column is mean absolute percentage-point change. The yards column is mean absolute yard change. Rank shifts are absolute national competition-rank changes, shown as median / maximum.

| Through week | Side | Rate value change | Yards value change | Rate rank shift | Yards rank shift |
|---|---|---|---|---|---|
| 2 | offense | 1.196 pp | 1.238 yd | 4 / 29 | 7 / 125 |
| 2 | defense | 1.245 pp | 1.193 yd | 4 / 22 | 7 / 92 |
| 3 | offense | 0.746 pp | 0.830 yd | 2 / 17 | 4 / 46 |
| 3 | defense | 0.739 pp | 0.787 yd | 2 / 18 | 6 / 65 |
| 4 | offense | 0.517 pp | 0.599 yd | 1 / 10 | 4 / 33 |
| 4 | defense | 0.513 pp | 0.592 yd | 1 / 8 | 4 / 26 |
| 5 | offense | 0.403 pp | 0.480 yd | 1 / 7 | 3 / 29 |
| 5 | defense | 0.401 pp | 0.483 yd | 1 / 7 | 3 / 30 |
| 6 | offense | 0.328 pp | 0.407 yd | 1 / 5 | 3 / 29 |
| 6 | defense | 0.327 pp | 0.405 yd | 1 / 5 | 3 / 30 |

Through Week 2 Louisiana Tech's yards/success rank falls from 2nd to 127th; LSU's defensive yards/success rank improves by 92 places. Through Week 6 the largest individual yards/success value drops are 1.011 offensive yards (Buffalo) and 0.836 defensive yards; largest rate changes are about half a percentage point. In this sample the threshold rate has smaller longest-play rank changes, while yards/success retains greater leverage from a single long successful play. That observation does not establish which metric best serves the intended public chart or how either predicts future games.

Adding each subsequent week also changes opponents, eligible-play exposures and the national cohort (137 to 138 teams in the first transition). Median / maximum absolute rank changes from the immediately preceding window:

| New through week | Side | Rate rank movement | Yards/success rank movement |
|---|---|---|---|
| 3 | offense | 12 / 116 | 11 / 78 |
| 3 | defense | 16 / 97 | 12 / 85 |
| 4 | offense | 10 / 64 | 9 / 70 |
| 4 | defense | 9.5 / 75 | 12 / 83 |
| 5 | offense | 9 / 56 | 9 / 72 |
| 5 | defense | 8 / 73 | 8 / 73 |
| 6 | offense | 7 / 55 | 7 / 69 |
| 6 | defense | 8 / 53 | 7.5 / 64 |

There is no preceding comparison window for Through Week 2, so those differences remain null. The movements above are not a controlled test of reliability and do not justify declaring either candidate stable.

## Reproduction and retained evidence

Run from the existing isolated worktree with its installed Python environment. This command makes only read-only Preview object requests; it needs no database credentials. If local credentials are not already exported, `--env-file` names the owner's local file without copying or logging its contents. The output directory must be new and under the narrowly ignored `artifacts/research/chart-explosiveness/` prefix.

```bash
CFB_STORAGE_BACKEND=r2 CFB_ARTIFACT_ENV=preview PYTHONPATH=src:. \
  UV_CACHE_DIR=/private/tmp/cks-chart-uv \
  uv run --offline --no-sync python scripts/research/compare_chart_explosiveness.py \
  --revision-manifest conf/season/2026/revision_manifest_w7_v1.json \
  --active-week 7 \
  --output artifacts/research/chart-explosiveness/<new-run-directory> \
  --env-file <owner-local-environment-file>
```

The implementation used the primary checkout's installed `.venv` via `UV_PROJECT_ENVIRONMENT`, without modifying that checkout. The Preview wrapper's database Keychain lookups were unavailable in the sandbox; no database was needed. The initial sandbox object request failed at DNS resolution. The same scoped read-only R2 request succeeded after automatic approval review allowed network access, with explicit Preview backend/environment and verified credential presence. No result was derived from the failed request.

Final evidence is retained locally at `artifacts/research/chart-explosiveness/2026-10-16-final/`:

| Artifact | Contents |
|---|---|
| `offense-paired-profiles.png` | Through Weeks 2–6: success rate against each candidate, colored by PPA/play |
| `defense-paired-profiles.png` | Same paired comparison for defense allowed |
| `candidate-agreement.png` | Candidate-versus-candidate plots for each side/window; largest rank disagreements labeled |
| `team-windows.csv`, `team-windows.parquet` | 1,380 roster team/side/windows; independent counts/sums, ranks, longest-game context and removal results |
| `team-games.csv` | 1,316 team/side/game observations, opponents, scores and independent metric counts/sums |
| `eligible-games.csv` | 658 chart team-game rows; exact completed-game population |
| `distributions.csv` | Coverage, quantiles, pooled values and sensitivity/movement summaries for all windows/sides |
| `relationships.csv` | Pearson/Spearman correlations and paired sample counts for all windows/sides |
| `evidence.json` | Source refs/hashes, output hashes and independent direct-reconciliation receipt |

All three plots were visually inspected; paired charts use the same eligible-team population and independent metric denominators. Generated files remain ignored rather than being copied into repository-local `data/` or committed documentation assets. The verified initial figures/data are preserved at `artifacts/research/chart-explosiveness/2026-10-16-verified/`; final images use separated label offsets and identical checksum-verified tables. The first successful exploratory artifact directory is retained separately at `artifacts/research/chart-explosiveness/2026-10-16/`.

### Source hashes

| Input | SHA-256 |
|---|---|
| `schedule` | `3a4c37b834fc725b51428fc6863fb7439633c422815fb0011b93899bf4d2c670` |
| `finals` | `16faab73e70f1196c549906bac4a4c6bac4866db82e519511f03b5361df2be8b` |
| `byplay` | `828c90a3432a8b37ed4e10942355a0428dfed4d85104d5394d3a591233c04fbe` |
| `teams` | `b02787de8cb46ddc42c9e008fd75a43b1174a95f79fd6a8b309d98d5381e12e1` |

Full immutable Silver URIs are recorded beside these hashes in the revision and `evidence.json`. The report intentionally does not duplicate live release identifiers; current serving authority remains [status](../status.md).

### Validation

The successful run independently re-counted eligible pinned rows for all 1,380 team-side-windows: **9,660 direct formula values checked**, including valid-yardage counts, 20+ counts, successful-yardage counts/sums and both ratios. It reconciled **658 offensive team-games** against their defensive opponent mirrors (all stored metrics), and checked every cumulative window against game-context counts with later games excluded. These checks run before final artifact output. The real sample's missing-success and missing-PPA observations remain separate from yardage exposure.

Focused tests additionally cover missing/nonfinite yardage/PPA, zero successes, observed zero explosives, zero pooled exposure, unequal team exposures, mirrored defense, missing finals, FCS exclusion, special teams, overtime/garbage exclusion, earlier-window exclusion and removal of an unsuccessful longest gain. Run `PYTHONPATH=src:. uv run --offline --no-sync pytest tests/test_chart_explosiveness_comparison.py -q`; scoped Ruff checks pass.

## Pending owner decision

Choose whether the public chart should emphasize 20+ gain frequency among all eligible yardage plays or yardage conditional on successful plays, and record the exact selected definition in an amendment to the chart contract. Neither is selected here. Only after that gate may the separate additive `charts_v2` serving projection, migration, reconciliation and Preview rehearsal work begin; Production promotion remains separately gated.
