# G3 / G4 findings: market lines sanity (2026 weeks 0-5) and team identity

Read-only investigation, 2026-10-03. All Neon reads used PREVIEW_DATABASE_URL with `default_transaction_read_only=on`. Lake reads via `get_storage()` (R2). Nothing was written to R2, Neon, or tracked files. Scratch parquet files (prefix `g3_`/`g4_`) are in this folder.

Selected runs (site_week_selections, season 2026): w0 `2026w0-v5repair-20260929-p1` (8 games), w1 `...w1...p1` (43), w2 (49), w3 (57), w4 (58), w5 `2026w5-v5repair-20260929-p2` (56). Total 271 games, each with a predictions row and a market_snapshot_id.

## 0. Where the lines live

| Store | What | Notes |
|---|---|---|
| Neon `public.market_quotes` | 3001 rows, providers DraftKings 1194, Bovada 1036, ESPN Bet 761, "Draft Kings" 10 | Only CFBD-derived quotes. Zero The Odds API rows (`quote_updated_at` is NULL on every row). |
| Neon `public.market_snapshots` | 1241 rows, `spread_rule`/`total_rule` = provider_median | `source_quote_ids` lists the quotes behind each snapshot. |
| Neon `public.prediction_market_selections` | policy `model_side_best_quote_v1` | One selected quote per game per target; `point` equals predictions.home_team_spread_line / total_line for all 271 games. |
| Neon `catalog.source_captures` entity betting_lines, 2026 | `cfbd`: 17 captures (weeks 0, 1, 5 only; plus 2015-2025 season dumps). `legacy_cfbd_export`: 78 | No registered CFBD capture exists for the 2026 week 2, 3, 4 snapshots. The quote `source_capture_id`s for those weeks (`2ad6474f...`, `0e9b9707...`, `cd851874...`) are absent from the catalog. Quote `captured_at` times (Sep 8, 13, 20) have no matching catalog capture. |
| Lake `raw/betting_lines/year=2026/week=0..5/part-0.parquet` | 941 rows, 374 games, columns include `spread`, `formatted_spread`, `over_under` | Unregistered "raw" tier. Each week file has ONE capture time (wk0 Sep 2, wk1 Sep 8, wk2 Sep 13, wk3 Sep 20, wk4 Sep 20 18:42, wk5 Sep 29 20:28), i.e. after kickoff for weeks 0-3 (closing-like lines), so they are NOT the same capture as the stored selections for weeks 0-3. Weeks 4 and 5 are the same capture as the stored lines. Weeks 1-3 files also contain FBS-vs-FCS games not in the Silver/Neon schedule (103 games). |
| Lake bronze `provider=cfbd/entity=betting_lines` | 2026 week captures (7), `line_data` dict with spread, formattedSpread, overUnder | Weeks 0, 1, 5 only. |
| Lake bronze `provider=the_odds_api/entity=market_quotes` | 2 captures: Sep 4 02:30Z (31 rows, 17 events, week 2) and Sep 30 12:32Z (126 rows, 14 events, week 5) | Only the Sep 4 capture is in `catalog.source_captures`; the Sep 30 capture exists only in the lake. Neither feeds Neon market_quotes or the selected predictions. |

Provider label hygiene: raw lake weeks 0-3 hold both "DraftKings" and "Draft Kings" for the same book and game (260 of 681 game-book pairs; 75 of those pairs differ in spread or total: 43 spread, 39 total). Neon market_quotes also has 10 "Draft Kings" rows. The selected quotes (427) use only "DraftKings"/"Bovada", so the selected runs are not affected, but any median over raw rows would double-count DraftKings.

## 1. Sign sanity (CFBD `spread` vs `formatted_spread`; stored line vs named favorite)

Home-perspective check: favorite named in `formatted_spread`, resolved to home/away via the CFBD schedule (`raw/games/year=2026`) after `canonical_team`; expected spread = -|x| if home favorite else +|x|.

| Test | Result |
|---|---|
| Raw lake betting_lines, 941 rows (weeks 0-5, 374 games incl. FCS-opponent games) | 941/941 `spread` equal the value implied by `formatted_spread`. 0 sign mismatches, 0 value mismatches, 0 unresolved favorite names, 0 zero spreads. |
| Bronze CFBD week captures (7 captures, 502 rows) | 502/502 consistent. |
| Neon market_quotes vs bronze, same capture ids (406 quotes) | 406/406 spread equal, 406/406 total equal. |
| Stored `home_team_spread_line` sign vs favorite, weeks 4 and 5 (same capture as raw) | 114/114 agree. |
| Stored sign vs bronze captures closest in time (w0 Aug 16 and Aug 18, w1 Sep 2 18:01 and 18:13, w5 Sep 29) | 0 disagreements (8, 8, 43, 43, 56 games). |
| Stored sign vs raw lake week 0-3 files (later, closing-like captures) | 3 games disagree on side: w2 Minnesota/Mississippi State (401856677), w1 Nevada/Western Kentucky (401864432, Bovada only), w3 Central Michigan/Wyoming (401864508). All are small lines (|line| <= 2.5) that crossed pick'em between the stored capture and the later capture. Not a sign-convention bug. |

Label: **Sign convention bug: REFUTED.** CFBD `spread` is home-perspective (negative = home favored) everywhere checked.

Notable: game 401856677 (w2, Minnesota vs Mississippi State) has the same book contradicting itself inside the Sep 13 raw file: "DraftKings" -1.5 "Minnesota -1.5" and "Draft Kings" +1.5 "Mississippi State -1.5". The stored Neon line (+1.5, DraftKings) agrees with the "Draft Kings" value, the Bovada quote is -1.0, so the snapshot median is +0.25 and the stored best-quote line is +1.5. Which side was truly favored at selection time cannot be determined from stored data (**inconclusive** for that game).

## 2. Value ranges

| Check | Result |
|---|---|
| Stored lines, 271 selected games, abs(spread) > 45 | 3 games: Ohio State vs Ball State -50.5 (w1), Ohio State vs Kent State -51.5 (w3), Ole Miss vs Charlotte -47.5 (w2). Each is backed by real book quotes. Max abs spread = 51.5. |
| Stored totals outside 30-90 | 0. Overall 38.5 to 67.0 (w0 47.5-59.5, w1 44.5-60.0, w2 40.5-67.0, w3 39.5-62.5, w4 38.5-62.5, w5 42.5-62.5). |
| Raw lake rows, abs(spread) > 45 | 52 rows / 18 games (max 59.5). 16 of those games are FBS-vs-FCS games not in the Silver/Neon schedule; 2 are selected games (the Ohio State games). Totals 38.5-71.5, none outside 30-90. |
| Bronze CFBD captures | 16 rows with abs(spread) > 45 (max 55.5); totals 42.5-66.5. |
| The Odds API | max abs spread 29.5; totals 40.5-62.5. |

Label: **Out-of-range values: REFUTED** (3 large spreads are plausible mismatches, no total out of range).

## 3. Book agreement

Selected-run quotes: weeks 0, 1, 2, 5 have two books per game (DraftKings, Bovada); weeks 3 and 4 have ONE book (DraftKings only: 57 + 58 = 115 games), so "consensus" is a single book and no agreement test is possible there. With two books the deviation from the median is half the gap, so the 3-point and 4-point thresholds need a gap above 6 / 8.

| Dataset | Multi-book quotes | Spread > 3 from median | Total > 4 from median | Max spread dev | Max total dev |
|---|---|---|---|---|---|
| Neon selected quotes (156 two-book games, 312 quotes) | 312 | 0 | 0 | 1.5 (w0) | 1.0 |
| Raw lake, DraftKings label de-duplicated, all raw games | 614 | 0 | 0 | 1.5 | 1.5 |
| Raw lake, selected-run games only, de-duplicated | 426 | 0 | 0 | 1.25 | 1.0 |
| Raw lake, NOT de-duplicated (3 labels), selected games | 583 | 0 | 0 | 2.5 | 2.0 |
| The Odds API (9 books on Sep 30, 3 books on Sep 4) | 149 | 0 | 0 | 0.5 (Sep 30) / 2.5 (Sep 4) | 1.0 |

Label: **Book disagreement beyond thresholds: REFUTED** (0 outliers everywhere). Caveat: weeks 3 and 4 are single-book (not testable), and Bovada is absent from the week 3-4 stored snapshots even though the raw week-3 file has Bovada rows (captured later).

### Side finding: the stored line is not the stored consensus (confirmed)

The task describes the predictions line as selected/consensus. It is neither a consistent consensus nor always the snapshot value:

* `prediction_market_selections.policy_version` = `model_side_best_quote_v1`; `predictions.home_team_spread_line` / `total_line` equal the selected quote's `point` for 271/271 games (spread-side rows), and the stored spread equals one of the book quotes in 271/271 games. It is the best quote for the model's side, not a median.
* Weeks 0-2: the snapshot (`market_snapshots.spread`, `provider_median`) holds the true median (quarter-point values for 49 of 100 games), but the prediction line differs from that snapshot spread in 54/100 games (w0 8, w1 20, w2 26; mean abs diff 0.40, max 1.50) and the total in 43/100 (w0 1, w1 19, w2 23).
* Week 5: the snapshot values equal the prediction line (0 differences) yet differ from the median of the snapshot's own `source_quote_ids` in 16 spreads and 32 totals (two books per game). So the week-5 snapshot rows do not honor their labeled `provider_median` rule. Mechanism not determined.
* Weeks 3-4: single book, so snapshot = quote = prediction.
* Consequence: edges and any ROI computed against `home_team_spread_line` use the most favorable of two books for the model's side, which flatters apparent edge relative to a consensus line. Label: **CONFIRMED** (policy design plus a week-5 snapshot/rule inconsistency).

## 4. Staleness (The Odds API)

| Capture | Quotes | quote_updated_at missing | quote_updated_at == capture time | Book update age at capture | Lead time to kickoff |
|---|---|---|---|---|---|
| Sep 4 02:30Z (week 2) | 31 | 0 | 0 | 0.2-0.6 min (median 0.57) | 205-213 h |
| Sep 30 12:32Z (week 5) | 126 | 0 | 0 | 0.14-1.13 min (median 0.73) | 35-86 h (median 77 h) |

* Quotes captured less than 1 hour before kickoff: 0 of 157 (0%); 157 of 157 (100%) were captured 35 h or more before kickoff. None is a closing line.
* 8 of 157 quotes have no total (all in the Sep 4 capture).
* Odds API vs CFBD for week 5 (Sep 30 vs Sep 29 capture, 126 comparable quotes): spread diff within +-0.75, total within +-1.0, so no sign or team-swap problem. The Sep 4 capture differs from the Sep 13 raw file by up to 7 points because it is 9 days earlier (line movement, not comparable).
* Selected-run CFBD snapshots: hours before kickoff (median, min): w0 224 h (219), w1 73 h (27), w2 98 h (78), w3 144 h (99), w4 145 h (101), w5 93 h (52). 0 games within 1 hour of kickoff. Raw lake week 0-3 files are post-game captures (closing-like).

Label: **Stale/zero-timestamp Odds API quotes: REFUTED** for book timestamps; **CONFIRMED** that every Odds API and CFBD selection is days before kickoff. Odds API quotes are not used by any selected prediction.

## 5. Unmatched Odds API events

Matching code: `src/cks_picks_cfb/data/the_odds_api.py:65-130` (`match_odds_events_to_schedule`) and `scripts/data/fetch_odds_api_market_quotes.py` ~lines 124-150 (`allow_prefix=True`; unmatched names only printed to stdout). The schedule passed in is ONE week of Silver games, so events for other weeks are "unmatched" by design.

| Capture | Week schedule games | Matched events | Unmatched board events (capture metadata) | Schedule games with no quote |
|---|---|---|---|---|
| Sep 4 (week 2) | 49 | 17 (all map to the correct game, kickoff exact) | 638 | 32 |
| Sep 30 (week 5) | 56 | 14 (all correct) | 383 | 42 |

Weeks 0, 1, 3, 4: no Odds API capture exists.

* The unmatched event list is not persisted (only counts in the observation JSON), so the 42 and 32 missing games **cannot be classified** as "not on the board" versus "name mismatch". **INCONCLUSIVE.**
* Kickoff times are not the cause for week 5: the Silver games version used (`31a337df...`, as_of Sep 27) agrees with Neon start_date to the minute for all 56 games, `start_time_tbd` is false for all, and unmatched games share kickoff slots with matched ones. Most unmatched week-5 games have trivially prefix-matchable names (Iowa State/West Virginia, Georgia/Vanderbilt, Tennessee/Auburn), which points toward "not on the board at capture time" rather than naming, but this is not proven.
* Prefix-collision risk (Miami vs Miami (OH), Texas vs Texas State/Texas Tech, Louisiana vs Louisiana Tech): tested on the weeks 0-5 Neon schedule and the raw weeks 0-6 schedule. Zero pairs of games in the same +-5 minute slot where both home and away names are prefix-related, so neither a wrong match nor the "ambiguous" ValueError can occur on the current schedule. **Prefix collision: REFUTED for 2026 weeks 0-6.**
* Swapped home/away at neutral sites: the matcher requires exact home=home and away=away with no swap fallback, so a swapped neutral-site event would be silently unmatched. Neutral-site selected games: w0 1 (TCU vs North Carolina, Dublin), w1 3, w3 2, none in weeks 2, 4, 5. Since week 5 has 0 neutral games, this does not explain the 42 missing; no captured data tests it. **INCONCLUSIVE** (code risk exists).
* Names that may fail prefix matching against Odds API names and are on the 2026 schedule: `UL Monroe` (Odds API likely "Louisiana Monroe ..."; not in CFBD_NAME_EXPANSIONS; South Alabama vs UL Monroe is unmatched in week 5) and `San José State` (depends on Odds API accent spelling; Hawai'i vs San José State unmatched). `UConn`, `UTSA`, `Pittsburgh`, `Texas A&M` matched correctly in captured events. Cannot verify without a board listing. **INCONCLUSIVE.**

## 6. Null lines by week and week 5

Selected runs (predictions rows):

| Week | Games | Null spread | Null total | Notes |
|---|---|---|---|---|
| 0 | 8 | 0 | 0 | DraftKings total null for 6 of 8 games (quote level); Bovada fills them. |
| 1 | 43 | 0 | 0 | |
| 2 | 49 | 0 | 0 | |
| 3 | 57 | 0 | 1 | Texas Tech vs Houston (401856811): DraftKings quote has spread -8.5, total null; single-book week, so no fallback. Raw week-3 file later shows total 52.5. |
| 4 | 58 | 0 | 0 | |
| 5 | 56 | 0 | 0 | |

Week 5: 0 of 56 games lack a spread or total in the selected run (`2026w5-v5repair-20260929-p2`, 112 quotes, two books per game, lined_games 56/56). Context: the Sep 27 15:48 CFBD capture had 34 of 56 lined (published run `2026w5-d6366e59fd43` lined_games 34); Sep 27 21:46 had 56 DraftKings-only; Sep 29 has 112 (both books). Earlier replay runs for week 3 show lined_games 56 of 57 (same missing total). Label: **"week 5 lacks lines": REFUTED for the selected run; CONFIRMED for the earlier Sep 27 15:48 capture (22 of 56 unlined).**

## G4. Team identity

### Sources compared

| Source | Distinct teams | Notes |
|---|---|---|
| Silver games (`w4_games.parquet`, 761 rows, lake games version `31a337df...`) | 138 | All rows FBS vs FBS (classification fbs both sides). |
| Bronze plays (`bronze_plays_2026_parsed.parquet`, offense/defense, 58,379 plays) | 233 | 138 FBS + 95 FCS opponents. |
| Neon `games` (season 2026, weeks 0-5) | 138 | Same names as Silver. |
| Priors frame | 138 teams x 2 roles = 276 rows | Located: source lock `docs/plans/2026-09-29/v5-repair-2026-source-lock.json` -> `research_source_import.replay_parents.rating_uri` -> `output_refs.priors` = `lake/gold/dataset=possession_rating_prior/version=3f45825e9ce5f5fe586cafde/partitioned-manifest.json` (276 rows, content sha `703ee308...`). Copy: `g4_priors_276.parquet`. |
| Neon `v5_rating_snapshots` | 138 distinct teams, 802 rows (w0-w4: 138 teams each, w5: 112) | Stores legacy names. |
| `web/src/lib/rating-names.ts` | n/a | Uses `TEAM_LOGO_MAP` from `web/src/lib/teams.ts` (13 entries). Parsed and compared: identical to `contracts/teams.py` `TEAM_LOGO_MAP`; `preseason_features.canonical_team` uses the same dict (one-directional: CFBD name to stored name). |

### Raw-name differences (before canonicalization)

Silver/Neon/bronze game names vs priors/snapshots names differ for exactly 9 teams:

| Game name | Priors/snapshots name |
|---|---|
| App State | Appalachian State |
| Hawai'i | Hawai_i |
| Massachusetts | UMass |
| Sam Houston | Sam Houston State |
| San José State | San Jose State |
| Southern Miss | Southern Mississippi |
| UConn | Connecticut |
| UL Monroe | Louisiana Monroe |
| UTSA | UT San Antonio |

After `canonical_team`: Silver FBS teams, Neon games, priors, and snapshots are identical sets (138 each, 0 names in one but not another). Bronze vs Silver: only the 95 FCS opponents differ (raw and canonical), by design (Silver omits FBS-vs-FCS games; raw schedule has 888 games vs 761 in Silver). No FBS team is missing from bronze.

### Alias collisions

* One team to several names: `Hawai'i`, `Hawaii`, `Hawai i` -> `Hawai_i` (one team, not a collision).
* Two different teams to one name: none. The map's targets are distinct, and canonicalization merges no names within any source (bronze, Silver, Neon, priors, snapshots: 0 merges).
* One team under two names within one source: none (no source contains both an alias and its target).
* Texas vs Texas State, Miami vs Miami (OH), San Jose State vs San José State, UL Monroe vs Louisiana Monroe: consistent. Texas, Texas State, Texas Tech, Texas A&M, Miami, Miami (OH), Louisiana, Louisiana Tech all stay separate in every source. San José State (U+00E9) matches the Neon string byte for byte; Hawai'i uses a straight apostrophe (U+0027) in both. `FIU`, `Hawaii`, `Hawai i` keys are unused (the Silver name is already `Florida International`).
* Label: **Alias collision: REFUTED. Name drift across sources after canonicalization: REFUTED.**

Gaps and risks (not collisions):
* Raw-string joins between bronze/Silver/Neon and priors/snapshots fail for exactly those 9 teams. `web/src/lib/matchup.ts:147` and `web/src/lib/v5.ts:92` apply `ratingName`/`withGameNameAliases`, so they are covered; any other web query keyed by game name against snapshots would not be (not exhaustively audited; grep found only those two call sites).
* Week-5 `v5_rating_snapshots` has only the 112 teams that play in week 5 (verified equal to the week-5 playing set); the 26 bye teams have no week-5 row, so a page reading only the latest snapshot week would drop them.
* Snapshots carry two `snapshot_class` values (current/pregame), so (team, week) is not unique by design.

### Priors: duplicates and neutral fallbacks

* 276 rows = 138 teams x {offense, defense}; 0 duplicate (team, unit_role); 0 duplicates in the 2025 terminal frame (`ppp`, 457 rows, 230 teams), so `drop_duplicates('team', keep=False)` at `possession_live_replay.py:177` removed nothing.
* 274 rows use `rho_0_60` carryover priors; 2 rows (North Dakota State offense and defense) use the neutral fallback `no_predecessor` (mean 0.0, variance 1.0). NDSU has terminal rows only for 2016, 2022 and 2024, none for 2025, yet is an FBS team in the 2026 schedule. In `v5_rating_snapshots` NDSU carries `fallback_reason = no_predecessor` in weeks 0, 2 and 3 (2 rows each). NDSU is in the selected set in week 0 (home, line -7.0) and week 5 (home vs Wyoming, line -18.0), so the neutral prior affects real predictions. No other team falls back.
* Labels: **Duplicates in priors: REFUTED. Neutral-prior fallback: CONFIRMED, exactly one team (North Dakota State).**

## Summary of labels

| Item | Label |
|---|---|
| G3-1 sign convention, favorite in formatted_spread | Refuted (no bug); 1 self-contradicting game (inconclusive) |
| G3-2 out-of-range values | Refuted (3 plausible spreads > 45; no total out of range) |
| G3-3 book disagreement | Refuted (0 outliers); weeks 3-4 single-book, untestable |
| G3-3b stored line = best quote, not consensus; week-5 snapshot != own median | Confirmed |
| G3-4 Odds API stale/missing timestamps | Refuted; all captures days before kickoff (confirmed); not used by selections |
| G3-5 name-prefix collisions | Refuted for weeks 0-6; neutral-site swap and 42/32 unmatched games inconclusive (list not persisted) |
| G3-6 null lines | w3 one null total; week 5 selected run 0 of 56 unlined (refuted); old Sep 27 capture 22 of 56 unlined |
| Provider label duplicates (Draft Kings / DraftKings) | Confirmed, not in selected quotes |
| Weeks 2-4 CFBD captures unregistered in catalog | Confirmed |
| G4 name sets after canonical_team | Refuted (FBS sets identical); 9 raw-name aliases confirmed |
| G4 alias collisions | Refuted |
| G4 priors duplicates | Refuted |
| G4 neutral fallback | Confirmed: North Dakota State only |
