# G1 / G6 findings (read-only; 2026-10-03; w4 certified Silver set, 215 games)
Scripts: g1_script.py, g6_script.py; outputs g1_score_compare.csv, g6_fill_counts.csv, g6_dup_sample.csv (this directory).

## G1(a) reconcile_completed_games: score and box-score sub-checks  -> CONFIRMED (both silently skip)
- Score check, src/cks_picks_cfb/data/reconciliation.py:111-137: looks for the first of ("points","team_points","score") in the team's row (lines 120-126); if none exists `score_column` is None and the `if score_column and ...` guard (128-132) is false, so nothing is compared and no flag is raised.
- w4_team_games.parquet (430 rows, 110 cols) has NONE of points/team_points/score. It has `team`, `off_points_scored`, `def_points_allowed`. So the score comparison never executes on a real team-game frame.
- Box-score check, reconciliation.py:139-190: runs only when team_stats is given. Per metric (yards, turnovers, plays, possessions; policy.tolerances(), lines 22-29) it needs a left column in (metric, off_metric, n_metric) at 160-166. Team-game columns present: n_off_plays, off_turnover_rate, etc. None of yards/off_yards/n_yards, turnovers/off_turnovers/n_turnovers, plays/off_plays/n_plays, possessions/off_possessions/n_possessions exist. So `if not left or not right: continue` (176-177) fires for every metric: no metric is ever compared, regardless of the box-score frame. (The earlier team-set / row-count / expected-teams checks DO run; `team` exists.)
- Callers: scripts/pipeline/build_team_game_dataset.py:124 (passes frames.get("team_game_stats")), scripts/research/build_data_first_phase2c.py:550.
- Caveat: the check reads raw `game["home_team"]` vs `team_game["team"]` without canonicalization (line ~86-98); not tested here.

## G1(b) Five-source final-score comparison (names canonicalized; 430 team-games)
Sources: Silver games, Silver game_outcomes, Neon game_results (Preview), max running score in Silver byplay, max running score in raw Bronze.
Team running max = max over (offense_score where offense=team, defense_score where defense=team). Both variants computed.
- Missing finals: 0 in every source (215/215 rows each; Neon completion_state all 'completed'; no null points; no duplicates). No 'missing-final' cases.
- Silver games == Silver game_outcomes == Neon game_results for all 430 team-games: 0 disagreements. CONFIRMED all three finals agree.
- Running max != final: exactly 6 team-games, identical in Silver byplay and raw Bronze (CONFIRMED; same 6 games as known):
  | game | team | final (all 3 tables) | run max (silver=raw) |
  | 401856790 | UCF | 7 | 13 |
  | 401858429 | Toledo | 20 | 21 |
  | 401860881 | Memphis | 20 | 21 |
  | 401862702 | Army | 24 | 30 |
  | 401864443 | Middle Tennessee | 27 | 30 |
  | 401864579 | New Mexico State | 18 | 12 |
  The opposing team in each game matches (Pittsburgh 12, Michigan State 30, Boise State 38, South Florida 28, Nevada 20, New Mexico 42). These are true mismatches between the finals (3 agreeing tables) and play-by-play running scores. Cause not diagnosed here (see score_drops_detail/ledger files).
- Extra observation, Air Force 401864509: final 36, Silver byplay max 36, raw Bronze max 37. Raw has a drive 22 'End Period' row with offenseScore 37 that Silver's play-type filter removes (raw 199 rows vs Silver 186 for that game). Raw-only artifact; Silver correct. Raw therefore has 7 team-games differing from final, Silver 6.
- Methodology note (false-mismatch trap): using offense_score-only max per offense gives 9 diffs; the extra ones (Vanderbilt 401856695 28 vs 35, Wisconsin 401858460 48 vs 54) are defensive/special-teams points scored while the team is on defense (score appears only in defense_score). These are an artifact of the metric, not data mismatches; the both-columns max resolves them.
- Week 5 in Neon game_results: 0 rows for 2026 week 5 (join to games). All 215 2026 game_results rows are completed with points; no non-completed row has points. Nothing to report -> no premature W5 scores in table state (REFUTED as a concern).

## G6 Silent defaults (enrichment.py:235-275; ppa coercion at 672)
Dedup (line ~235-237, drop_duplicates on game_id, drive_number, play_number, keep first):
- Raw w4-set plays 38,403 (Bronze all-2026 58,379 across 331 games, 6 captures). Raw `id` unique (0 dups, 0 null). Triple-key duplicates: 1 extra row (1 group). CONFIRMED fires, but only once.
- That one case is a REAL distinct play lost: game 401856693 (Texas/UTSA) drive 8 play 1, id 401856693256 (10:02, incomplete pass to UTSA26, ppa -0.998, capture 2026-09-20) vs id 401856693264 (09:32, incomplete to UTSA40, ppa -1.162, capture 2026-09-27). Silver kept the 09:32 play. Using the id as key would keep both. Impact: 1 play of 38,403 (negligible, but the key is not unique).
- Silver matches raw 1:1 on the triple (35,407/35,407; Silver has 0 dup triples). Raw 38,403 vs Silver 35,407: the ~2,996-row difference is the playtype_delete filter, not a fill.
Null->0 fills (raw nulls among the w4 set; identical in all-2026 Bronze except ppa):
| field | raw nulls (w4) | all-2026 | Silver rows changed by fill |
| yardsToGoal | 0 | 0 | 0 |
| yardline | 0 | 0 | 0 |
| down | 0 | 0 | 0 |
| yardsGained | 0 | 0 | 0 |
| distance | 0 | 0 | 0 |
| period (quarter) | 0 | 0 | 0 |
| offenseScore | 0 | 0 | 0 |
| defenseScore | 0 | 0 | 0 |
| ppa | 9,594 | 14,508 | 7,213 of 35,407 Silver rows (20.4%) have ppa==0 exactly where raw ppa is null; Silver ppa has 0 NaN |
- Verdict: the numeric default fills on yards_to_goal/yard_line/down/yards_gained/quarter/scores are REFUTED as active in current data (never fire; Bronze has no nulls there). The ppa fill (line 265 list; the later to_numeric at 672 then finds no NaN) is CONFIRMED active and material: 7,213 null ppa become 0.0 in Silver. Cannot tell from this data which raw null-ppa rows are legitimately zero-valued vs missing (sample: raw true-zero ppa count not separated); related to the d_zero_ppa analysis.
- Caveat: bronze_plays_2026_parsed.parquet is already a parsed file; if parsing itself defaulted nulls, raw nulls could be hidden upstream (not checked). Silver down==0 count 86 (raw down==0 354 over 38,403 incl. filtered play types) are genuine zeros in raw, not fills.

## G6 Neon
- games, season 2026: 271 rows, 0 null start_date -> REFUTED (no null start_date).
- market_quotes exists (columns: quote_id, game_id, provider, captured_at, spread, total, home_spread_price, away_spread_price, over_price, under_price, ...). No column named `price`; checked the four price columns.
  - Whole table 3,001 rows, 0 null captured_at. 2026-game quotes: 753 rows, 0 null captured_at.
  - 2026 quotes: home_spread_price, away_spread_price, over_price, under_price are null in 753/753 rows (prices are never populated for 2026; all four null in every row). spread null 0; total null 31. -> null captured_at: REFUTED; null price: CONFIRMED (100%, though may simply mean the provider doesn't supply prices).
