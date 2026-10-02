# Data Issues: Review and Rerun Together

- **Status:** Draft (to run next session; needs Sol review and user approval of the decisions in Phase 4 before any write)
- **Created:** 2026-10-02
- **Planner:** Sol
- **Approval source:** User direction 2026-10-02: review the open data issues, then redo the affected aggregations together, with the production team-stats republish bundled into that rerun.
- **Implementation log:** none yet
- **Commit policy:** read-only phases need no commit (record findings in `docs/data/known_issues.md`); code and data changes land on `dev`, CI green before any push to `main`; production writes are user-run.

## Goal

Understand what is wrong or thin in the team-stats inputs, decide what to change once, rerun the affected data once (Preview first, then production), and only then open the matchup page in production.

## Inputs

- [Known data issues](../../data/known_issues.md): issue 1 (non-monotonic play-by-play score), 2 (V5 punt companions), 3 (zero-PPA plays), and the review checklist.
- [Team stats feeds ratings](03-team-stats-feeds-ratings.md): Phase 1 done; Phase 2 design; the held production republish commands.
- Decision log entries of 2026-10-02 (punt leak; bundling).
- Baseline numbers to compare against (2026-10-02): Preview `team_season_stats` weeks 1-5 = 11,506 rows (with `ppa_per_play`, punt fix); production = 10,460 rows (pre-fix, no `ppa_per_play`). Flagged score streams (`ppso_invalid_offenses` in the `publish_team_stats.py` report): week 1 7 of 16 team-games, week 2 36 of 102, week 3 72 of 200, week 4 98 of 314, week 5 133 of 430. CFBD verifier (like-for-like teams): PPA/play rho 0.990 offense, 0.961 defense.

## Rules

- Phases 1-3 are read-only: no database or lake writes, no new immutable artifacts.
- No production write and no change to a signed V5 artifact or the serving rating lineage without a contract and the user's go.
- Any change that moves `ppp` or `epa_per_possession` (the only measures the ratings fit) stops the work and needs its own contract and a delta report.
- Preview first, always: `--dry-run --diff`, review, then write.
- Keep `CFB_MATCHUP_ENABLED` unset in production until Phase 6.

## Phase 0: Baseline and tooling (read-only)

1. Confirm the baseline above still holds: `PYTHONPATH=src:. uv run python scripts/pipeline/publish_team_stats.py --season 2026 --weeks 1-5 --environment preview --dry-run` (report JSON per week), and the production row count with a read-only query.
2. Turn the ad-hoc hand-check into a committed script `scripts/analysis/handcheck_team_stats.py`: load the Silver `byplay` for a team's games, recompute the metrics with its own play filter (scrimmage plays only), compare with the stored `team_season_stats` rows, print a table. The 2026-10-02 version checked 32 offense/defense values for Western Kentucky and New Mexico State to four decimals. Add a unit test on a small fixture.

## Phase 1: Score-stream investigation (issue 1, read-only)

1. For game ids 401856684, 401856695, 401856698 (Vanderbilt), compare the raw CFBD plays (Bronze capture or a fresh read-only CFBD call) with Silver `byplay`: does the running score dip in the raw feed too? If only in Silver, the cause is in our build (`features/byplay/enrichment.py`); if in both, it is the provider.
2. Build `scripts/analysis/audit_score_stream.py`: for every flagged team-game (133 at week 5) record the first row where a team's score decreases, the size of the drop, the play type on and before that row, whether the next rows restore the score, and whether the final score reconciles. Output a table of causes with counts (suspected: extra point credited before the kick on defensive and special-teams touchdowns; reversed or mislogged touchdowns; unexplained such as Auburn 15 to 12).
3. Deliverable: counts per cause, and whether a safe correction rule exists (for example "a drop restored within N rows is provisional").

## Phase 2: V5 impact (read-only)

1. Read-only query of `team_game_measurements` (Preview) for the flagged team-games: `coverage_status`, `missing_reason`, `quality_flags` on `offensive_possession_points` and `non_offense_points`.
2. Check the identity per game (offensive possession points + non-offense points + garbage-time points = final score); Vanderbilt's three games first. Question to answer: does V5 quarantine or silently use the dipping score? Vanderbilt shows a points-per-possession value (2.00, T-77).
3. Deliverable: affected or not, and how many team-games, with magnitude on `ppp`.

## Phase 3: Verify the unverified metrics (read-only)

Run the Phase 0 script on two clean-score teams and two flagged teams for `scoring_opp_rate`, `pts_per_scoring_opp` and `avg_start_field_pos`. Acceptance: equal to four decimals, or every difference explained (for example overtime and placeholder drives were already handled in Amendment 2 of contract 10).

## Phase 4: Decisions (user, with Sol)

- **D1 score-stream rule:** keep quarantine as is; accept a correction rule (needs a contract and tests); or take scoring-drive points from another source such as CFBD `drives`. Criteria: share of flagged team-games recovered, risk of wrong points.
- **D2 zero-PPA plays:** treat the 155 eligible non-punt `ppa == 0` plays as missing, or accept them. Depends on whether they are CFBD nulls hidden by Silver's `fillna(0)`.
- **D3 Silver rebuild** (enrichment fix for `Punt Return`, any `fillna` change): now or at the planned rating rebuild.
- **D4 V5 measurement and rating rebuild:** now or later; required if Phase 2 shows V5 is affected or if D3 runs now and the user wants the companions corrected.
- Record each decision in the decision log.

## Phase 5: Implement and rerun (after D1-D4)

1. Code and tests on `dev` for the decided changes (`data/team_stats.py`, `features/byplay/enrichment.py`, `ratings/observations.py` as decided); full CI rehearsal on a clean worktree before any push (see `web/README.md`).
2. If D3: build and validate Silver (`scripts/pipeline/build_silver.py`), then `make promote-silver YEAR=2026` (Preview and production share one R2 bucket; this registers versions only).
3. Team stats on Preview, weeks 1-5: `publish_team_stats.py --season 2026 --weeks 1-5 --environment preview --dry-run --diff`, review the deltas (expected only the metrics the decisions touch), write, then `verify_team_stats.py --season 2026 --as-of-week 5 --environment preview` and the Phase 0 hand-check.
4. If D4: V5 measurements and ratings through the reviewed weekly cycle (`scripts/pipeline/run_v5_weekly_cycle.py`, see `docs/ops/v5_weekly_operator.md`) under their own contract with a delta report against the served lineage; then `make matchup-data YEAR=2026 ENV=preview RATING_URI=... MEASUREMENT_URI=... APPLY=1` and `verify_matchup_data.py`.
5. Production (user-run), same order as Preview: dry run with `--diff` (compare with Preview's), write, verify. Week 6 team stats follow after Week 5 finals are certified.

## Phase 6: Close

1. Move issues 1-3 in `known_issues.md` to Resolved (or mark accepted with the reason); update `docs/status.md`, contract 03 (Phase 2 status), the plans index, a session log.
2. Only now set `CFB_MATCHUP_ENABLED=1` in production (user decision).

## Stop conditions

- Phase 2 shows V5 `ppp` or `epa_per_possession` would change: stop, write a contract.
- A Preview diff shows metrics changing that the decisions do not explain: stop and investigate.
- CI red, or a production dry-run diff that does not match Preview's: do not write.

## Definition of done

- [ ] Phase 1-3 findings recorded in `known_issues.md` with counts.
- [ ] D1-D4 decided and logged.
- [ ] Preview and production `team_season_stats` produced by the same code and Silver version; hand-checks pass on the Phase 3 teams.
- [ ] If rebuilt: V5 delta report reviewed, matchup data re-pinned and verified.
- [ ] `known_issues.md` items resolved or explicitly accepted; docs and session log updated.

## Carry-forward (separate from this contract)

- Week 5 close after certified finals: `scripts/pipeline/backfill_v5_unconstrained_grades.py --week 5 --grades-only` ([plan 04](04-remove-edge-constraints-grade-all-games.md)).
