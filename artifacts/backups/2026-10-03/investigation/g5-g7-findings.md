# G5 / G7 findings (read-only, 2026-10-03)

Scratch files in this folder: `silver_games_31a337.parquet` (2026 Silver games), `silver_games_c48874.parquet` (2021-2026),
`g5_neutral_errors.csv` (per-game errors, 2025+2026), `g7_terminal.parquet`, `g7_priors_2026.parquet`,
`g7_byplay2025_*.parquet`, `g7_obs2025_ppp_offense.csv`.
Sign convention (verified): Neon `predicted_spread` > 0 = home wins by that much; `home_team_spread_line` < 0 = home favoured, so
market home margin = `-home_team_spread_line`. Neon `games` row equals the site-selected run's prediction on all 271 games (0 diffs).

# G5. Neutral sites and the home-field intercept

## G5.1 2026 neutral-site games (Silver `neutral_site`, 11 total; Neon `game_venues` flags the 6 already played)

| wk | game (home v away) | venue | status | model spread | market (home margin) | actual margin | model - actual | model - market |
|---|---|---|---|---|---|---|---|---|
| 0 | TCU v North Carolina | Aviva (Dublin) | played | +14.62 | +6.5 | -5 | +19.6 | +8.1 |
| 1 | Auburn v Baylor | Mercedes-Benz | played | +7.35 | +7.0 | +1 | +6.3 | +0.3 |
| 1 | Ole Miss v Louisville | Nissan Stadium | played | +10.44 | +7.0 | +3 | +7.4 | +3.4 |
| 1 | Notre Dame v Wisconsin | Lambeau | played | +19.87 | +20.0 | +28 | -8.1 | -0.1 |
| 3 | Kansas v Arizona State | Wembley | played | +6.33 | -5.5 (ASU fav.) | -7 | +13.3 | +11.8 |
| 3 | Virginia v West Virginia | Bank of America | played | +18.30 | +9.5 | -11 | +29.3 | +8.8 |
| 6 | Oklahoma v Texas | Cotton Bowl | scheduled 10-10 | none yet | none yet | | | |
| 9 | Navy v Notre Dame | Gillette | scheduled 10-31 | none yet | | | | |
| 9 | Georgia v Florida | Mercedes-Benz | scheduled 10-31 | none yet | | | | |
| 10 | Eastern Michigan v Central Michigan | Ford Field | scheduled 11-04 | none yet | | | | |
| 15 | Army v Navy | MetLife | scheduled 12-12 | none yet | | | | |

- Week 5 has no neutral game. Neon `games` holds predictions only for weeks 0-5 (271 games), so the first scheduled neutral game with a
  forecast will be Oklahoma-Texas (Week 6). Week 6+ rows do not exist yet.
- Neutral flags for late-season games (conference title games, bowls) may not be in the schedule yet, so more neutral games will likely appear.
- Silver neutral counts by season (all games): 2021 20, 2022 19, 2023 22, 2024 35, 2025 23, 2026 11 so far.

## G5.2 Where the home edge lives in the served bundle

- Bundle: `artifacts/research/data-first-football-v1/forecasts/intended-update/runs/v5-intended-update-2026-v1/bundle.json`
  (sha256 starts 30c4f1eb0ef5, matches `v5_model_bundle_approvals.inference_bundle_sha256` for `preview-intended-update-30c4f1eb0ef5`).
- Margin target is fitted as `actual_margin - offset_margin`, Ridge alpha 10, 8,935 training rows (2015-2025 ex-2020), features standardized.
  `feature_names` holds only the four rating features: `home_host` and `venue_unknown` were dropped as non-varying
  (`forecast/live.py` ~240-255; set constant at `live.py:172-173`, `historical_features.py:121-122`, `possession_rating_materializer.py:1201-1202,1325-1326`).
- Margin intercept = **7.4368** (total intercept 51.17). Calibration variance 317.6 (sd 17.8).
  Standardized coefficients: home_off +6.74, home_def +7.94, away_off -8.63, away_def -9.44 (in raw rating units about +8.5, +9.8, -10.3, -11.0).
- `offset_margin` (`forecast/offsets.py:185`) is built from non-offense points only and carries no venue term, so nothing else encodes home field.
- The intercept is not a clean HFA. It is the mean of (actual - offset) at average ratings. Converting to raw ratings, the constant is 6.52 and
  two EQUAL-rated teams give a home edge of 5.35 pts at league-average ratings (5.44 at (0.5,0.2); 4.24 at (1,0.5); 7.71 at (-0.5,-0.3); 3.05 at (1.5,0.8)),
  before the offset. The edge shrinks as team quality rises (regression-to-the-mean pattern). It also absorbs training games with FCS opponents where
  the home team is much stronger. A precise "HFA in points" therefore cannot be read off the bundle; about 5 pts at average ratings is the model-implied figure.
  Verdict: **confirmed** that the home edge exists only in the intercept and applies to every game including neutral ones.
- External reference (not model): Silver 2021-2025 FBS-vs-FBS regular season (n=3,729), margin on CFBD pregame Elo difference:
  HFA (non-neutral intercept) = +3.42 pts; neutral-site games have 2.85 pts LESS home margin at equal Elo (SE 1.54, n=118 neutral),
  i.e. a neutral-site HFA of about +0.6 (+/-1.5). By season the neutral delta is -2.4, -5.8, +0.2, -4.5, -1.4 (SEs 2.9-3.8, all noisy).

## G5.3 Bias estimates (error = model minus benchmark; positive = model too far toward home)

| group | n | model - actual (mean, SE) | model - market (mean, SE) | market - actual |
|---|---|---|---|---|
| 2026 wk0-4 neutral | 6 | +11.3 (5.2) | +5.4 (2.0) | +5.9 (3.9) |
| 2026 wk0-4 non-neutral | 209 | -1.7 (1.2) | -1.25 (0.7) | -0.4 (1.0) |
| 2025 neutral (v4 replay) | 22 | +4.0 (3.6) | +4.2 (1.8) | -0.2 (2.6) |
| 2025 non-neutral (v4 replay) | 739 | -1.7 (0.7) | -1.0 (0.5) | -0.7 (0.6) |

Difference neutral minus non-neutral, model - market: 2026 +6.65 (SE 2.1, n=6); 2025 +5.2 (SE 1.9, n=22); pooled +5.5 (SE 1.5, n=28).
Model - actual difference: 2026 +13.0 (SE 5.4); 2025 +5.7 (SE 3.6); pooled +7.3 (SE 3.1) (actual margins are very noisy, sd ~19 per game).

Caveats:
- 2026 n=6 is very small; one game (Notre Dame) is -0.1 vs market and the mean is driven by 3 games above +8.
- The 2025 predictions in Neon are the **v4 replay** (`v4-locked-test-replay-20260909b`, legacy evidence), not V5. They show whether a
  home-edge-in-intercept pattern appears historically, not V5's own bias. No V5 holdout predictions for 2025 exist in Neon.
- 5 of 22 neutral 2025 games are Sam Houston "home" games at BBVA Stadium, flagged neutral in the data (market +9 to +11.5 dogs, model-market +3.5 to +14.9).
  Excluding them: 17 games, model-market +2.4 (SE 2.1) vs non-neutral -1.0, so difference about +3.4. The headline 5.2 is partly a Sam Houston artifact.
- Bowl and postseason games are absent from these datasets (all rows regular season).
- Median model-market error on neutral games: 2025 +3.1, 2026 +5.8.

## G5.4 Sized recommendation (no code)

Roughly **+3 to +3.5 points per neutral-site game toward the home team**, plausible range **2 to 5.5**.
- Evidence for the centre: empirical Elo HFA 3.4 (neutral games lose about 2.9 +/- 1.5 of it); the 2025 market comparison without Sam Houston (+3.4).
- Evidence for the upper end: pooled model-vs-market difference of +5.5 (SE 1.5); 2026 alone +6.6 (SE 2.1, n=6).
- The model's own non-neutral bias vs market is about -1.0 to -1.25 (slightly under-home), so against an unbiased baseline the neutral excess may be
  slightly larger than raw HFA. This is why the market-based figure sits above the Elo-based one.
- For the Week 6 Oklahoma-Texas game the home label probably carries about 3 pts of unearned edge, which is material against a typical spread-edge threshold.
- Verdict: neutral-site over-credit of the home team **confirmed** in mechanism (by construction) and **supported but small-sample** in the data
  (2026 n=6 inconclusive on its own; pooled n=28 direction consistent, magnitude 3-5.5).

# G7. 2025 -> 2026 carryover

## G7.1 2025 terminal table and 2026 priors

- Source: historical measurement manifest `PINS["measurement"]` = `.../possession-v1/measurements/runs/possession-v1-measurements-20260921-r9/measurement-manifest.json`
  (checksum verified), `output_refs["terminal"]` = Gold `possession_terminal` version dbec9dd68d63696320c36d7d (8,794 rows, all seasons).
  Read at `scripts/pipeline/build_v5_intended_update_2026.py:92`; used by `possession_live_replay.py:_priors` (~149-219) and `_historical_scale` (59-).
  Timing class of all 2025 rows is `historically_reconstructed`.
- 2025 `ppp` rows: offense 230 teams, defense 227 teams (the table includes FCS teams that played FBS opponents), 0 duplicate teams, 0 non-finite
  `adjusted_value`, 0 non-positive `primary_exposure`. ppp offense mean 1.62 (sd 0.95), defense mean 2.65 (sd 1.20) over the full population.
- 2026 universe (138 teams). 137 of 138 are present in both roles with no duplicates. **Missing: North Dakota State** (FCS; no 2025 row, rows exist in 2016/2022/2024),
  which gets `RatingPrior(0, 1.0, "neutral", None, "no_predecessor")` (`possession_live_replay.py:198`). Priors file
  (`.../intended-update-2026/runs/v5-intended-update-2026-ratings-v1/priors.parquet`): 276 rows = 138 x 2, 274 `rho_0_60`, 2 `neutral` (NDSU offense and defense).
  Prior variance for carried teams 0.657-0.800 (0.663 typical); neutral variance 1.0.
- A missing team, a duplicated team (`drop_duplicates("team", keep=False)` drops all copies, so it also becomes neutral), or a team with a
  non-finite value / exposure <= 0 (`invalid_predecessor`) would each get mean 0, variance 1.
- Name matching is a latent risk: the terminal uses CFBD names (Appalachian State, Hawai_i, UMass, Sam Houston State, San Jose State, Southern Mississippi,
  Connecticut, Louisiana Monroe, UT San Antonio); Neon site names differ (App State, Hawai'i, Massachusetts, ...) for 10 teams. The build maps them
  (`build_v5_intended_update_2026.py:100-109` via `TEAM_LOGO_MAP`) and the priors use CFBD names, so all 10 resolved. If a mapping failed, a team would silently get a neutral prior with no error.
- Distribution plausibility, 137 carried teams: 2025 adjusted ppp offense mean 2.13 (sd 0.69, range 0.62-3.88), defense mean 1.99 (sd 0.61, range 0.34-3.87);
  exposure median 127, min 10 (Sacramento State, first FBS year; its prior variance is 0.80). Plausible.
- Observation (not a defect): the standardization centre/spread (`_historical_scale`) is computed over ALL 230/227 teams including FCS (offense 1.62/0.95,
  defense 2.65/1.19), so FBS priors have mean z of about +0.32 (offense 0.318, defense 0.327) while NDSU's neutral prior is 0. Differences between two FBS teams cancel;
  only games involving an unseen team are affected, by roughly a third of one z unit.
- Verdict: integrity **confirmed** (137/138, no duplicates, finite, plausible); one expected neutral fallback (NDSU).

## G7.2 Do score dips and the quarantine affect 2025?

Method check: my implementation (per game/team, order by drive_number/play_number as stored, decrease between consecutive rows where the team is offense or defense)
reproduces the 2026 baseline exactly on `w4_byplay.parquet`: 133 of 430 team-games, 223 events.

| dataset | rows | games | team-games | with a decrease | events | to-zero events | null running scores |
|---|---|---|---|---|---|---|---|
| 2025 byplay 42945ece (8-31) | 126,300 | 762 | 1,524 | 492 (32.3%) | 884 | 199 | 0 |
| 2025 byplay de481576 (9-06, all games) | 154,632 | 934 | 1,868 | 597 (32.0%) | 1,113 | 254 | 0 |
| 2026 wk0-4 (reference) | 35,407 | 215 | 430 | 133 (30.9%) | 223 | 42 | 0 |

- Drop sizes in 2025: 7 (339), 3 (217), 6 (60), 1 (52), 10 (39), 14 (37) of 884, similar in kind to 2026. Weekly share 25-40%, falling to 11% / 0% in weeks 15-16 (few games).
- (a) Dips: **confirmed present in 2025 at the same rate (32%) as 2026 (31%)**. They are provider-side (see a1-findings), not new in 2026.
- (b) Null running scores: **refuted** for Silver byplay (0 of 126,300 / 154,632) and Silver plays 2025 (dc723a96, 166,236 rows, 0 null `offense_score`/`defense_score`).
  Bronze/raw 2025 plays could not be checked: `raw/plays/year=2025` has no files, and the Bronze `lake/bronze/provider=cfbd/entity=plays` captures are keyed by content sha
  rather than season, so I did not scan them. Gap recorded; a fillna(0) upstream of Silver (A1 L8) cannot be ruled out from Silver alone.

2025 measurement observations (manifest `output_refs["observations"]`, 285,952 rows; Neon `team_game_measurements` holds 2026 only):
- 2025 `ppp`, `offensive_possession_points`, `non_offense_points`: **151 of 1,868 team-games (8.1%) are `missing` / `unresolved_scoring_attribution`**
  (302 rows = 151 offense + 151 defense), quality flag `mixed_eligibility_drive` on all 151. EPA and play-count measurements are observed for all 1,868.
- Within the 2026 team universe: 149 of 1,743 team-games (8.5%) quarantined; 92 of 138 teams lost at least one 2025 game, 11 lost 3 or more
  (Arkansas State 6, Texas State 5, BYU 4, Texas 4, Arizona 3, Marshall 3, Michigan State 3, Troy 3, UNLV 3, Utah State 3, Virginia 3).
- `ppp` missing share by season: 2015 1.6%, 2016 3.0%, 2017 1.2%, 2018 1.1%, 2019 0.7%, 2021 6.8%, 2022 8.3%, 2023 3.6%, 2024 4.2%, 2025 8.1%. 2026 wk0-4: 27/430 = 6.3%. 2025 is comparable to or higher than 2026.
- Overlap with dips (1,755 of 1,868 team-games joined on game_id + team): of 151 quarantined, 135 have a decrease and 16 do not; of 554 with a decrease, 135 (24%) are quarantined.
  Related but not identical events: dips are common, quarantine is the subset that breaks the points identity.
- Selection: quarantined 2025 team-games are higher scoring (own points 31.4 vs 25.8 for observed; n=132 joined vs 1,390), so the quarantine removes
  disproportionately high-scoring offensive games from the 2025 ppp terminal ratings and so from the 2026 priors. Direction and size of the resulting rating bias not determined.
- Verdict: the quarantine **does** affect the 2025 data feeding terminal ratings, priors and bridge training (8.1% of team-games; 2021-2022 and 2025 are the high years).
  Those games are excluded, so the effect is information loss plus possible high-scoring selection, not corruption. Effect on 2026 predictions: **inconclusive** (not estimated).
