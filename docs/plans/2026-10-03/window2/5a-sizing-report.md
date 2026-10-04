# Window 2 Step 5A: sizing report (draft for user review)

- **Status:** Draft. Not a signed receipt. The signing and any R2 publication of the receipt are user-run steps.
- **Authority:** [contract 04, Amendment 2](../04-data-integrity-two-window-implementation.md), [Appendix A, 5A](data-contracts-and-certification.md), [frozen definitions](5a-frozen-definitions.md) (frozen before any of these numbers existed).
- **Produced:** 2026-10-04, read-only. No CFBD request, no R2 write, no database write. The numbers in sections 1-3, 5 and 6 were computed by me from the pinned Silver inputs (section 6 from the latest validated 2026 Silver). Section 4 quotes the October 2026 investigation's CFBD result, labelled there as not re-derived by me. Raw outputs are in [`5a-data/`](5a-data/). Scripts: `scripts/analysis/size_r1_vs_baseline.py`, `size_null_ppa_exposure.py`, `size_r1_2026.py`.
- **What this report does not contain:** any CFBD drive evidence, so **the 25% gate has not been evaluated**. The sizing is the denominator and the evidence burden, not the gate result.

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

## 3. CFBD request count (no request has been made)

- 2,324 changed games (2,236 regular season, 88 postseason).
- The user confirmed CFBD's `/drives` endpoint is queried by year, week and season type. Requests needed for the changed games: **153** distinct (season, season type, week) bundles. For the whole corpus (8,936 games, 8,521 regular and 415 postseason): **162** bundles. Fetching everything costs 9 more requests than fetching only changed games' weeks, because changed games spread across nearly every week.
- Basis: the repair-pinned `fbs_involved_games` of each season; all 8,936 population games matched. The retained responses must keep the request, capture timestamp and SHA-256.
- Decision for you: fetch the 153 bundles (changed games only, as decided) or all 162. Nothing is fetched until you say so.

## 4. Gate arithmetic

The gate needs at least 25% of 3,193 groups corroborated by clean CFBD drives: **799 groups**. A group is corroborated only if its game's drives pass all four frozen checks and CFBD's per-drive points equal R1's allocation for every drive the group touches. Groups where CFBD matches the baseline, or where the drives are unusable, do not count. The 2026 weeks 0-4 evidence (decision packet items 21 and 26, not re-derived by me) is that CFBD drives were clean in about 9 of 30 affected team-games and favoured the baseline over R1, so this gate may well fail; that is evidence about 2026 weeks 0-4, not a forecast for this corpus.

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

1. Your decision on the CFBD fetch (section 3).
2. The fetch with retained evidence, the four drive checks, the corroboration share by season, cause and channel, and the gate result.
3. Expected benefit and remaining evidence burden if the gate fails (the contract forbids building a gamebook pipeline automatically).
4. Optional: individual reproduction of the 2026 weekly manifests `2026w0` to `2026w3` (the baseline requirement is otherwise met, section 1).
5. Signing and publishing the exit receipt (user-run).
