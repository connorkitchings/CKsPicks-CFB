# Window 2 Step 5A: sizing report

- **Status:** **Closed.** The user accepted the gate result (44.4% against the 25% threshold), declined a secondary gamebook source and approved evidence retention on 2026-10-04 (committed `f7c3a47`). This is still not a signed release receipt: signing and any R2 publication of it are user-run steps.
- **Authority:** [contract 04, Amendment 2](../04-data-integrity-two-window-implementation.md), [Appendix A, 5A](data-contracts-and-certification.md), [frozen definitions](5a-frozen-definitions.md) (frozen before any of these numbers existed).
- **Produced:** 2026-10-04. CFBD: 162 requests after approval; no R2 write, no database write. The numbers in sections 1-3, 5 and 6 were computed by me from the pinned Silver inputs (section 6 from the latest validated 2026 Silver). Section 4 quotes the October 2026 investigation's CFBD result, labelled there as not re-derived by me. Raw outputs are in [`5a-data/`](5a-data/). Scripts: `scripts/analysis/size_r1_vs_baseline.py`, `size_null_ppa_exposure.py`, `size_r1_2026.py`.
- **Gate:** evaluated in section 4 after the user approved fetching all 162 CFBD bundles (made 2026-10-04, retained with request URL, capture time and SHA-256). **Result: pass at 44.4%, with the caveats in section 4.**

## 1. Baseline reproduction (verified by me, read-only)

| Served artifact | Method | Result |
|---|---|---|
| Historical measurement run `possession-v1-measurements-20260921-r9` (2015-2019, 2021-2025) | The runner's dry run at current HEAD recomputes every output from the pinned inputs | All 8 datasets' canonical record hashes and row counts equal the served manifest; certification SHA equals `fc26a3d03416e688dc437ad863653dfac7df6faad51b478a7b94f466c0d870c3` |
| 2026 measurement run `possession-v1-measurements-20260927-w4` (215 games) | Same dry run with the sealed 2026 config and the 2026 repair manifest | All 8 datasets' record hashes and row counts equal the served manifest; certification SHA equal |
| Served ratings `v5-intended-update-2026-ratings-v1` | `build_v5_intended_update_2026.py` in local mode with the served code SHA `1683876d…` and the source lock | **Byte-identical**: manifest SHA, all five output files (current roles 1,380 rows, current teams 690, pregame roles 1,084, pregame teams 542, priors 276), generation hashes, parents and identity |

Limits: the measurement runs were compared at canonical-record-hash level (the contract's fallback), not byte level, and ran at current HEAD, not the served code SHA, so a match shows the current builder reproduces them. The rating rebuild reads the served measurement manifests from R2 as parents rather than rebuilding them (they are reproduced separately above). The 2026 weekly manifests `2026w0` to `2026w3` were not individually reproduced; the w4 run covers all 215 games. Byte equality of the measurement outputs was not compared.

## 2. Full R1 versus baseline, 2015-2019 and 2021-2025

Inputs: 1,521,061 plays, 8,936 population games, 10 seasons (2020 excluded). The baseline scoring ledger has 86,937 events (equal to the served run); the R1 candidate ledger has 82,416. R1 leaves 126 team-games unresolved (envelope does not reach the certified final) and 333 team-games carry a restoration of more than eight points after a dip. 17,870 team-games have a certified final.

**Changed allocation groups (frozen definition): 3,193, in 2,845 team-games and 2,324 of 8,936 games (26.0%).**

| Season | Groups | Changed games | Points recovered | Points reduced |
|---|---|---|---|---|
| 2015 | 124 | 103 | 122 | -1 |
| 2016 | 150 | 117 | 247 | 0 |
| 2017 | 185 | 150 | 107 | 0 |
| 2018 | 110 | 101 | 255 | 0 |
| 2019 | 93 | 78 | 76 | -1 |
| 2021 | 555 | 361 | 1667 | -28 |
| 2022 | 486 | 331 | 2025 | -22 |
| 2023 | 455 | 339 | 575 | -106 |
| 2024 | 414 | 323 | 553 | -8 |
| 2025 | 621 | 421 | 1571 | -83 |
| **Total** | 3193 | 2324 | 7198 | -249 |

By channel:

| Channel | Groups | Share |
|---|---|---|
| attribution_only | 2727 | 85.4% |
| points_recovery | 414 | 13.0% |
| points_reduction | 52 | 1.6% |

By primary cause (precedence in the frozen definitions; all flags are in the CSV):

| Primary cause | Groups | Share |
|---|---|---|
| dip_restore | 2540 | 79.5% |
| incomplete_stream | 297 | 9.3% |
| category_possession_reassignment | 125 | 3.9% |
| final_cap | 90 | 2.8% |
| other | 71 | 2.2% |
| restoration_gt8 | 70 | 2.2% |

By season and primary cause:

| Season | category_possession_reassignment | dip_restore | final_cap | incomplete_stream | other | restoration_gt8 |
|---|---|---|---|---|---|---|
| 2015 | 2 | 104 | 2 | 6 | 6 | 4 |
| 2016 | 1 | 135 | 1 | 11 | 1 | 1 |
| 2017 | 6 | 170 | 2 | 2 | 4 | 1 |
| 2018 | 4 | 92 | 2 | 8 | 4 | 0 |
| 2019 | 0 | 85 | 1 | 2 | 4 | 1 |
| 2021 | 33 | 399 | 14 | 71 | 21 | 17 |
| 2022 | 4 | 354 | 11 | 100 | 10 | 7 |
| 2023 | 22 | 372 | 15 | 24 | 6 | 16 |
| 2024 | 12 | 355 | 18 | 21 | 3 | 5 |
| 2025 | 41 | 474 | 24 | 52 | 12 | 18 |

Reading: 85% of groups change attribution only, not points, which is the channel the 2026 investigation found quarter totals cannot validate. Recoveries are 414 groups worth 7,198 points; reductions (mostly final-cap clipping) are 52 groups. The 2015-2019 seasons change far fewer groups than 2021-2025 (93-185 versus 414-621 per season); I have not investigated why.

## 3. CFBD requests

- 2,324 changed games (2,236 regular season, 88 postseason).
- The user confirmed CFBD's `/drives` endpoint is queried by year, week and season type. Requests needed for the changed games: **153** distinct (season, season type, week) bundles. For the whole corpus (8,936 games, 8,521 regular and 415 postseason): **162** bundles. Fetching everything costs 9 more requests than fetching only changed games' weeks, because changed games spread across nearly every week.
- Basis: the repair-pinned `fbs_involved_games` of each season; all 8,936 population games matched. The retained responses must keep the request, capture timestamp and SHA-256.
- Decision (user, 2026-10-04): fetch all 162 bundles. Done: 162 responses, all HTTP 200, 282,062 drive rows, no empty bundle, hashes verified; raw responses retained locally under `artifacts/research/window2_5a_cfbd_drives/` (git-ignored, 149 MB) with the manifest committed as `5a-data/cfbd_drives_manifest.jsonl`. Moving the raw files to R2 for durable retention is not done and needs your approval.

## 4. Gate result

**The frozen 25% gate passes: 1,416 of 3,193 changed groups (44.4%) are corroborated by clean CFBD drives; the gate needed 799.** Corroborated means the game's drives pass all four frozen checks and CFBD's per-drive points equal R1's allocation on every drive the group touches while the baseline's do not.

| Season | Groups | Corroborated | Share |
|---|---|---|---|
| 2015 | 124 | 62 | 50.0% |
| 2016 | 150 | 73 | 48.7% |
| 2017 | 185 | 90 | 48.6% |
| 2018 | 110 | 51 | 46.4% |
| 2019 | 93 | 41 | 44.1% |
| 2021 | 555 | 241 | 43.4% |
| 2022 | 486 | 216 | 44.4% |
| 2023 | 455 | 212 | 46.6% |
| 2024 | 414 | 237 | 57.2% |
| 2025 | 621 | 193 | 31.1% |
| **Total** | 3193 | 1416 | 44.4% |

By channel:

| Channel | Groups | Corroborated | Share |
|---|---|---|---|
| attribution_only | 2727 | 1408 | 51.6% |
| points_recovery | 414 | 8 | 1.9% |
| points_reduction | 52 | 0 | 0.0% |

By primary cause:

| Primary cause | Groups | Corroborated | Share |
|---|---|---|---|
| dip_restore | 2540 | 1389 | 54.7% |
| incomplete_stream | 297 | 4 | 1.4% |
| category_possession_reassignment | 125 | 22 | 17.6% |
| final_cap | 90 | 0 | 0.0% |
| other | 71 | 0 | 0.0% |
| restoration_gt8 | 70 | 1 | 1.4% |

Status of every group:

| Status | Groups | Share |
|---|---|---|
| game_unusable | 1718 | 53.8% |
| corroborated | 1416 | 44.3% |
| indistinguishable_at_drive_level | 31 | 1.0% |
| cfbd_matches_neither | 20 | 0.6% |
| cfbd_supports_baseline | 8 | 0.3% |

### What the pass does and does not show

- **The pass rests on attribution-only groups.** 1,408 of the 1,416 corroborated groups change attribution without changing points; they are almost all dip-and-restore cases. Corroborated groups that recover points: **8 of 414**, covering **104 of 7,198 recovered points (1.4%)**.
- **Why recoveries do not corroborate.** 402 of the 414 recovery groups (97%) are in games whose CFBD drives fail the usability checks, which are the games with messy score streams. Even if those games were treated as usable, only 72 of 414 recovery groups would corroborate, 310 would match neither the baseline nor R1, and 31 would support the baseline.
- **Reductions and final-cap groups.** 0 of 52 point-reduction groups and 0 of 90 final-cap groups are corroborated; every one is in an unusable game.
- **Most of R1's changes have no CFBD evidence either way.** 1,718 groups (53.8%) are in games with unusable drives. Under the frozen rule those are not corroborated and, at admission (5C), revert to the baseline unless a secondary source corroborates them. The contract forbids building a gamebook pipeline automatically.
- **Within usable games CFBD overwhelmingly favours R1.** Where baseline and R1 differ on a drive in a usable game, CFBD agrees with R1 on 1,415 of 1,425 drives and with the baseline on 9. In games that are not usable, 1,467 favour R1 and 571 the baseline (258 neither).
- **The agreement is not stable over time.** Across all games with CFBD drives, the share of differing drives where CFBD agrees with R1 is 90% (2015), 90%, 92%, 86%, 88% (2019), 80% (2021), 75%, 78%, 85% (2024) and 62% (2025); the baseline's share rises to 28% in 2025. The October 2026 sample (weeks 0-4, CFBD-clean team-games) is 36 baseline, 28 R1 and 2 neither, which my pipeline reproduces exactly (`5a-data/reproduction_2026_perdrive.csv`). Corroboration share by season is lowest in 2025 (31.1%). 2026 is excluded from the gate, but it is the season being served.

### Usable games

6,830 of 8,936 games (76%) have usable CFBD drives; 1,222 of the 2,324 changed games do. 8,903 games have any CFBD drives (33 have none). Usable share by season: 2015 77.2%, 2016 76.6%, 2017 79.1%, 2018 78.4%, 2019 79.8%, 2021 72.5%, 2022 73.8%, 2023 77.8%, 2024 82.0%, 2025 67.5%. Games with explicit non-drive points: 3,061. Checks passed (of 8,936): c1 8,310, c2 7,881, c3 8,224, c4 7,853. Most frequent failure reasons:

| Reason | Games |
|---|---|
| c1:cumulative_through_period_1_differs_from_line_scores | 60 |
| c1:cumulative_through_period_2_differs_from_line_scores | 244 |
| c1:cumulative_through_period_3_differs_from_line_scores | 57 |
| c1:cumulative_through_period_4_differs_from_line_scores | 215 |
| c1:first_drive_not_0_0 | 168 |
| c1:last_drive_end_differs_from_certified_final | 229 |
| c2:cfbd_drive_missing_from_ledger | 877 |
| c2:eligible_ledger_possession_missing_from_cfbd | 230 |
| c3:drive_13_delta_0_1 | 5 |
| c3:drive_17_delta_7_1 | 4 |

### Sensitivity to the usability definition

Two checks were corrected after the first run (see the amendment in the [frozen definitions](5a-frozen-definitions.md)). The gate under each variant, so the dependence on those choices is visible:

| Variant | Corroborated | Share |
|---|---|---|
| c2_strict_equality (c1, strict c2, c3, c4) | 0 | 0.0% |
| frozen_as_clarified (c1 and c2 and c3 and c4) | 1416 | 44.4% |
| no_usability_filter (upper bound, not valid under the frozen rule) | 1924 | 60.3% |
| only_c3_and_c4 | 1559 | 48.8% |
| without_c2 | 1520 | 47.6% |

The gate passes under every variant that is not mechanically impossible. Strict equality of the CFBD and ledger drive sets gives zero because the ledger carries return-only possessions CFBD does not call drives; that is why the check was clarified. The "no usability filter" row is an upper bound and is not valid under the frozen rule, because a final-total match alone is not enough.

### First run (superseded)

The first run of the corroboration, with two checks implemented incorrectly, found 23 usable games and **0 corroborated groups**. It is kept in `5a-data/corroboration_first_attempt_superseded.json`. Its checks compared quarter totals at boundaries the drives cannot observe and demanded exact equality between CFBD drives and all ledger possessions. I changed both after seeing the zero, on stated principles rather than to reach a threshold, and report the sensitivity above so that choice can be judged.

## 5. Null-PPA exposure (original provider values; these are what a source-restored Silver would withhold)

Measured by joining the pinned original `plays` (provider PPA kept) to the pinned `byplay` (PPA zero-filled) on game, drive and play number, over the contract's population P (V5 filter minus kicking plays). 0 eligible plays failed to match.

| EPA population | Team-games with a null (withheld) | Null plays |
|---|---|---|
| eligible_epa (all eligible plays) | 1,203 of 17,805 (6.8%) | 1,953 of 1,123,065 (0.17%) |
| epa_pass | 537 of 17,805 (3.0%) | 837 of 546,152 (0.15%) |
| epa_rush | 727 of 17,805 (4.1%) | 1,060 of 575,310 (0.18%) |
| early_down_epa | 889 of 17,805 (5.0%) | 1,393 of 864,552 (0.16%) |

By season, for `eligible_epa`:

| Season | Withheld team-games | Share | Null-play rate |
|---|---|---|---|
| 2015 | 87 of 1726 | 5.0% | 0.10% |
| 2016 | 84 of 1714 | 4.9% | 0.08% |
| 2017 | 140 of 1738 | 8.1% | 0.15% |
| 2018 | 117 of 1762 | 6.6% | 0.11% |
| 2019 | 124 of 1774 | 7.0% | 0.12% |
| 2021 | 179 of 1774 | 10.1% | 0.24% |
| 2022 | 137 of 1792 | 7.6% | 0.19% |
| 2023 | 118 of 1820 | 6.5% | 0.15% |
| 2024 | 105 of 1837 | 5.7% | 0.45% |
| 2025 | 112 of 1868 | 6.0% | 0.13% |

The served rating path fits `ppp`, which does not use PPA; the effect on ratings of withholding these EPA values is not measured here (5B and 6A report it).

## 6. 2026, reported separately (excluded from the gate)

Latest validated Preview Silver for 2026 (byplay `443019a9a7b6a2454a4af4ac`, games `31a337df6cf49f1578457ec6`, game outcomes `0ad054089d8fd6883e935417`) covers weeks 0-4 only: Week 5 plays are not in this Silver yet. 215 completed games; baseline 2,034 events, candidate 1,870; **132 groups** in 119 team-games (98 games, 5 week bundles), 1 unresolved team-game. This reproduces the October investigation's 2026 numbers under the frozen group definition.

## 7. What remains for 5A

1. Your review of the gate result and its caveats (section 4). Under the contract a pass continues to 5B; this is not a decision to admit R1: admission is per allocation group at 5C, and groups without corroboration revert to the baseline.
2. Durable retention of the raw CFBD responses (R2), if you want them beyond the local ignored directory.
3. Whether to seek a secondary source (official gamebooks, subject to the contract's terms conditions) for the 402 points-recovery groups, which carry 7,038 of the 7,198 recovered points and have no CFBD corroboration. The contract does not build that pipeline automatically.
4. Signing and publishing the exit receipt (user-run).
