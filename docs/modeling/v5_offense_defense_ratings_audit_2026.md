# V5 offensive and defensive ratings audit

**Audit date:** 2026-11-08. **Computation and serving-projection checks completed; original forecast-artifact verification remains incomplete.**

Florida’s small offensive lead over Georgia reproduces from the accepted estimator. Georgia leads raw PPP, but Florida receives a larger opponent adjustment. Georgia’s stronger prior offsets most of that advantage. No arithmetic defect or matchup snapshot mismatch was found in the checked generations. The narrow offensive ordering is sensitive to the treatment of partially quarantined games, which is a methodological concern rather than authorization to change V5.

[Machine-readable evidence](evidence/v5_offense_defense_ratings_audit_2026.json) | [Approved implementation contract](../plans/2026-11-08/v5-offense-defense-ratings-audit.md) | [Current operational state](../status.md)

## Scope and verification

The historical comparison is Georgia–Florida, `game_id=401856734`, at Pre-Week 9 / Post-Week 8. It uses `conf/season/2026/revision_manifest_w9_v2.json` and `conf/season/2026/model_manifest_v1.json`: ten pregame generations (Weeks 0–9, including preseason) and nine post-week generations (Weeks 0–8). Completed Week 9 observations are excluded. Post-Week 8 is frozen at `2026-10-25T15:00:00Z`; the baseline pre-Week 9 forecast cutoff is `2026-10-25T20:52:00Z`. Those generations have identical values for these teams.

A separate active-Production capture uses one read-only, repeatable-read transaction. Its own revision is verified by SHA-256 and its Weeks 0–8 source observations are independently rebuilt. Later completed observations never enter this historical audit. The model, forecasts, records, schemas, UI, publication and rollover were not modified.

| Check | Historical baseline | Captured active release |
| --- | --- | --- |
| Rating components, including contribution evidence and period/source metadata | 19 generations agree | 19 generations agree |
| Adjusted PPP projections | 9 post-week generations agree | 9 post-week generations agree |
| Original source PPP versus active projected measurements | Baseline reconstructed from pinned inputs | 1,776 rows agree; zero differences |
| Page-selected current/preseason ratings versus projected pregame ratings | 500 games agree, all four fields | 500 games agree, all four fields |
| Original prepared Ridge features and rating parquet files | Unavailable | Unavailable |

Adjusted PPP has one post-week projection per as-of week; ten pregame-generation adjusted-table checks are intentionally unavailable rather than comparisons against a differently timed table. Historical prior reconstruction reports 274 agreements, zero discrepancies and two unavailable predecessor checks per generation. All four Georgia/Florida role priors reproduce. Provider source truth is not independently certified merely by rebuilding its ledger.

## Offensive audit

| Measure | Georgia | Florida |
| --- | ---: | ---: |
| Usable games | 6 | 6 |
| Offensive points / possessions | 192 / 59 | 210 / 65 |
| Raw PPP, national rank | 3.254237, #6 | 3.230769, #7 |
| Adjusted PPP | 3.601164 | 3.712190 |
| PPP adjustment (adjusted minus raw) | +0.346927 | +0.481421 |
| Offensive rating, national rank | 1.839377, #5 | 1.856944, #4 |

Florida’s adjusted-PPP advantage is 0.111025 despite a raw-PPP deficit of 0.023468. The final rating advantage is only 0.017567. These are scoring-efficiency ratings; the other displayed raw statistical rankings are diagnostic measurements, not weighted ingredients of the offensive rating.

### Population difference

For both teams and both roles, the full usable population and the FBS-vs-FBS population are identical at the case cutoff: no games, points or possessions are added or removed, and raw PPP and ranks are unchanged. Therefore direct FCS inclusion does not explain this comparison. The implementation permits a broader opponent graph; its presence must be established from the input population rather than assumed. All available case-team raw-stat projection comparisons across the frozen periods agree (30 rows; early periods without team evidence have no comparison row).

The game-level populations are: Georgia versus Western Kentucky, Arkansas, Oklahoma, Vanderbilt, Alabama and Auburn; Florida versus Florida Atlantic, Auburn, Ole Miss, Missouri, South Carolina and Texas. Per-generation populations and the opponent-edge ledgers are retained in the JSON.

### Four-pass adjustment trace

| Pass | Georgia offense PPP | Florida offense PPP | Georgia defense PPP allowed | Florida defense PPP allowed |
| --- | ---: | ---: | ---: | ---: |
| 0 | 3.254237288 | 3.230769231 | 1.263157895 | 2.784615385 |
| 1 | 3.250260413 | 3.270469704 | 1.556142525 | 2.326627111 |
| 2 | 3.440485003 | 3.553363551 | 1.311639326 | 2.370966203 |
| 3 | 3.504540414 | 3.581913160 | 1.316775071 | 2.207880210 |
| 4 | 3.601164452 | 3.712189770 | 1.228178445 | 2.196606591 |

Pass 0 is raw efficiency. Each later pass subtracts the exposure-weighted deviation of opposing units from their opposite-role league center. The JSON records the pass-by-pass centers, opponent estimates and game-specific adjustments for both teams and their played opponents. With complete context, `sum(exposure * game_adjusted_ppp) / sum(exposure)` agrees with pass-4 cumulative adjusted PPP for each case role. No second schedule-strength adjustment enters the posterior.

## Defensive audit

| Measure | Georgia | Florida |
| --- | ---: | ---: |
| Opposing offensive points / possessions | 72 / 57 | 181 / 65 |
| Raw PPP allowed, national rank | 1.263158, #10 | 2.784615, #116 |
| Adjusted PPP allowed | 1.228178 | 2.196607 |
| Defensive rating, national rank | 1.139748, #15 | 0.443996, #70 |

The defense calculation reverses the standardized PPP sign: less adjusted PPP allowed produces a stronger, higher defensive rating. The website sorts higher defensive ratings first. Georgia leads in raw and adjusted defensive efficiency and in the posterior rating. Its stronger preseason prior also contributes more positively. No sign reversal, double opponent adjustment or component/projection discrepancy was found in this scope.

## Historical scales and prior decomposition

| Role | 2025 team-equal center | Spread | Sign | Teams | Exposure-weighted center |
| --- | ---: | ---: | ---: | ---: | ---: |
| offense | 1.678657062126892 | 0.955107215027087 | +1 | 230 | 2.109796932382802 |
| defense | 2.722266740359860 | 1.223498069193981 | -1 | 227 | 2.109796932382806 |

The two role populations have the same total exposure (18,516 possessions) and equal exposure-weighted centers to floating-point precision. Their team-equal centers differ substantially. Restricting both roles to their 227 common teams still gives different centers (offense 1.688428; defense 2.722267), so the difference is not explained solely by the three extra offensive teams. Unequal per-team role exposure and cohort composition matter.

| Terminal cohort, using 2026 catalogue labels | Offense teams / mean / median exposure | Defense teams / mean / median exposure |
| --- | --- | --- |
| fbs | 137 / 2.182752 / 127 | 137 / 2.041593 / 127 |
| non_fbs | 93 / 0.936066 / 10 | 90 / 3.758404 / 10 |

These labels apply the pinned **2026** catalogue to 2025 terminal teams; exact 2025 FBS membership was not established. Sparse teams receive the same weight as full-season teams in the historical center. The supplied approximate centers 1.623 and 2.647 were not reproduced from the pinned terminal and remain unverified alternate-provenance values. Neither those values nor a new normalization was substituted.

The one-year prior uses `m0 = 0.60 * terminal_z` and `P0 = 0.36 / (1 + terminal_exposure / 8) + 0.64`. The posterior uses `P = 1 / (1/P0 + usable_exposure/8)` and `m = P*m0/P0 + sum(P*exposure*adjusted_z/8)`. The 0.60 carryover coefficient is not a 60% late-season rating weight.

| Team / role | 2025 terminal PPP / exposure | Prior mean | Prior variance | Posterior prior weight | Prior contribution | Rating |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Georgia offense | 3.265513473 / 148 | 0.996865935 | 0.658461538 | 0.170760541 | 0.170225367 | 1.839377229 |
| Georgia defense | 1.178659852 / 137 | 0.756980461 | 0.659862069 | 0.175391910 | 0.132768249 | 1.139747603 |
| Florida offense | 2.297225399 / 112 | 0.388585696 | 0.664000000 | 0.156372166 | 0.060763987 | 1.856944319 |
| Florida defense | 1.659589731 / 128 | 0.521133806 | 0.661176471 | 0.156935149 | 0.081784211 | 0.443996140 |

### Per-game contributions

Each listed game contributes once. Contributions plus the prior contribution equal the role rating; source weeks and availability timestamps are retained in JSON. Defense rows measure the opposing offense.

| Team / role | Opponent | Week | Possessions | Raw PPP | Adjusted PPP | Rating contribution |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Georgia offense | Western Kentucky | 2 | 9 | 5.444444 | 4.869883 | 0.422645188 |
| Georgia offense | Arkansas | 3 | 8 | 3.875000 | 3.686883 | 0.236416871 |
| Georgia offense | Oklahoma | 4 | 11 | 2.727273 | 3.830315 | 0.348290619 |
| Georgia offense | Vanderbilt | 5 | 10 | 3.800000 | 3.854069 | 0.320123333 |
| Georgia offense | Alabama | 6 | 9 | 2.222222 | 3.075954 | 0.185057611 |
| Georgia offense | Auburn | 7 | 12 | 2.000000 | 2.565579 | 0.156618241 |
| Georgia defense | Western Kentucky | 2 | 8 | 0.750000 | 1.747072 | 0.092246668 |
| Georgia defense | Arkansas | 3 | 7 | 0.428571 | 0.504209 | 0.183586348 |
| Georgia defense | Oklahoma | 4 | 12 | 0.500000 | 0.556029 | 0.307366627 |
| Georgia defense | Vanderbilt | 5 | 9 | 1.444444 | 1.848296 | 0.093005549 |
| Georgia defense | Alabama | 6 | 9 | 1.888889 | 0.679799 | 0.217353811 |
| Georgia defense | Auburn | 7 | 12 | 2.250000 | 1.922911 | 0.113420351 |
| Florida offense | Florida Atlantic | 1 | 10 | 5.900000 | 4.706537 | 0.411456584 |
| Florida offense | Auburn | 3 | 11 | 3.909091 | 4.474670 | 0.417943164 |
| Florida offense | Ole Miss | 4 | 12 | 4.333333 | 4.851691 | 0.517417887 |
| Florida offense | Missouri | 5 | 8 | 1.250000 | 2.288382 | 0.066284117 |
| Florida offense | South Carolina | 6 | 12 | 1.583333 | 1.953156 | 0.044761845 |
| Florida offense | Texas | 7 | 12 | 2.250000 | 3.753364 | 0.338316735 |
| Florida defense | Florida Atlantic | 1 | 10 | 2.100000 | 1.693232 | 0.109087333 |
| Florida defense | Auburn | 3 | 11 | 3.545455 | 3.218365 | -0.057850203 |
| Florida defense | Ole Miss | 4 | 12 | 2.333333 | 1.122435 | 0.203516661 |
| Florida defense | Missouri | 5 | 9 | 4.222222 | 4.281205 | -0.148735877 |
| Florida defense | South Carolina | 6 | 12 | 3.166667 | 2.294224 | 0.054451802 |
| Florida defense | Texas | 7 | 11 | 1.545455 | 0.992212 | 0.201742213 |

## Score exceptions and asymmetric quarantine

The source trace identifies 98 unusable team-game-role observations across 44 games: 39 partially quarantined games and five whole-game quarantines. All 88 scoring-side offense/opponent-defense pairs agree in validity. The evidence records each excluded role, all four role statuses, original missing reason and quality flags, possession/scoring ledger, final score and pinned exception membership. A declared reconciliation exception permits the declared score mismatch; it does not make an unusable PPP observation valid.

For Ole Miss at Texas (`401856732`), the Ole Miss score stream sums to 3 against the recorded final 27. Ole Miss offense and Texas defense are excluded. Texas’s 34 points over 15 usable possessions remain in Texas offense and Ole Miss defense. This is scoring-side paired quarantine, not a whole-game exclusion. It matches the executable implementation; its methodological consequences remain relevant.

The partially quarantined SEC graph cases are `401856716` (Missouri–Texas A&M), `401856729` (Kentucky–Vanderbilt), and `401856732` (Ole Miss–Texas). The JSON includes directed one-hop and two-hop paths. For example, retained Missouri defensive evidence directly affects Florida offense; that context can also propagate through Ole Miss offense into Florida defense.

### Diagnostic graph sensitivity

Each experiment removes the remaining usable edges of the indicated partially quarantined game(s), without inventing replacement scores. These are sensitivity experiments, not corrected ratings or proposed production changes.

| Removed game(s) | Georgia offense | Florida offense | Georgia defense | Florida defense |
| --- | ---: | ---: | ---: | ---: |
| 401856716 | 1.851728 | 1.832296 | 1.141430 | 0.439048 |
| 401856729 | 1.836579 | 1.854707 | 1.133062 | 0.445032 |
| 401856732 | 1.841031 | 1.869613 | 1.141586 | 0.447656 |
| 401856716, 401856729, 401856732 | 1.850583 | 1.842040 | 1.136412 | 0.443976 |

Dropping all three retained game pairs reverses the offensive ordering (Georgia 1.850583; Florida 1.842040). Dropping the Missouri–Texas A&M pair alone also reverses it. The baseline gap is therefore too small to interpret as a robust football-quality distinction independent of quarantine policy. This is a methodological concern to document and evaluate separately, not evidence that the arithmetic or pair attribution is broken.

## Matchup and original-forecast lineage

The audit executes the actual `periodBeforeKickoff` TypeScript helper and follows source-qualified current-class selection and preseason fallback. For each scope, all 500 forecast-bearing Weeks 0–9 games have both spread and total heads and the four selected offense/defense values match projected pregame values exactly. There are no games without forecasts in either captured scope.

For Georgia–Florida, the page selects post-Week 8 current ratings at `2026-10-25T15:00:00Z`; their four values equal the baseline pregame forecast snapshot at `2026-10-25T20:52:00Z` (and the active release’s pre-Week 9 snapshot). Timestamp equality was not assumed.

The original active run manifest was recovered and matches its database SHA-256. Its original feature, rating and prediction parquet files were not recovered. The historical baseline run manifest and original prepared parquet files are also unavailable. Searches covered local preparation directories/worktrees, relevant temporary files, the configured unmounted external data root, GitHub workflow receipts and operational R2 prepared-run prefixes. Weekly uploads retain receipt manifests and summaries, not the referenced parquet files.

**Consequently the audit cannot independently confirm the original Ridge feature bytes or original pregame parquet states for either forecast head.** Stored pregame agreement, source reconstruction and an original manifest are useful evidence, but do not substitute for those missing artifacts. The CLI supports their checksum-verified comparison if restored.

Production web commit `eb86f3f2229481839f6bd21edb9526d7b84c316a` was verified through the connected Vercel deployment metadata. Its `v5.ts`, `matchup.ts` and `rating-periods.ts` bytes match the audited checkout; file hashes are recorded in the JSON review provenance.

## Findings and follow-up explanation design

| Classification | Finding | Recommended action |
| --- | --- | --- |
| Expected implementation | Florida’s opponent adjustment offsets Georgia’s raw-PPP advantage; stronger Georgia priors narrow the gap. | Explain the rating’s actual inputs alongside raw diagnostic statistics. |
| Expected implementation | Defense sign, paired source roles and stored rating/adjusted projections agree. | Preserve the accepted calculations. |
| Methodological concern | Sparse historical role cohorts affect team-equal scales; partial-quarantine policy can reverse a tiny offensive gap. | Retain explicit limitations and evaluate separately under an approved research/correction contract. |
| Evidence/reliability gap | Original forecast artifacts are unavailable despite retained receipt manifests. | Restore originals if available; separately plan durable prepared-artifact retention. |
| Unverified provenance | Approximate historical centers 1.623/2.647 do not match the pinned terminal. | Require the source/filter definition before using those values. |

`projection_football.py` and `matchup_data.py` already stage `season_release_team_rating_components` and `season_release_team_possession_adjusted`. `web/src/lib/matchup.ts` currently reads neither. A subsequent explanation feature can use those verified tables without a new ratings estimator:

- Add concise copy: “Ratings use opponent-adjusted scoring per possession plus a shrinking preseason prior. The tables show raw statistics and are not combined to form the rating.”
- Anchor components to the selected snapshot’s `v5_snapshot_id`, captured `release_id`, canonical team and role, with the same rating-source hash. For a current post-week snapshot, component `as_of_week` is post-week plus one. Expose the selected snapshot identity in the server loader if needed.
- Join adjusted PPP by the same release, season, as-of week, team, role, measurement and exact stored cutoff/source provenance. Show raw PPP → adjusted PPP → prior/evidence contribution, with actual prior weight.
- Preserve the existing provenance guards and unavailable states. Do not join a newer generation merely because its week label looks similar. Explain quarantined/limited evidence and avoid portraying a tiny rank gap as decisive.

This is a follow-up design recommendation only; no web code, schema, model or production data changed.

## Reproduction and validation

Use the CLI in an isolated worktree with explicit `CFB_STORAGE_BACKEND=r2`, matching operational `CFB_R2_*` credentials and the restricted Production pipeline wrapper. Supply `--model-manifest`, `--revision-manifest`, `--score-exceptions-git-ref`, optional repeatable `--run-manifest`, `--environment production`, `--last-pregame-week 9`, `--report`, and `--evidence` as specified by the contract. Use the historical exception commit and verify every digest. Missing original artifacts must remain unavailable.

The final live run succeeded. Thirty focused tests passed (18 arithmetic/source tests, seven CLI tests, five existing intended-update tests); scoped Ruff lint and format checks passed. Documentation and final diff validation are recorded in the implementation session log. Review covered design, functionality/testing, security/reliability, performance and external boundaries.

The JSON contains CLI-computed evidence plus explicitly labeled review provenance. This narrative includes reviewed interpretation after CLI execution; rerunning the CLI replaces the files, so reattach deployment provenance and review the interpretation for the new capture.
