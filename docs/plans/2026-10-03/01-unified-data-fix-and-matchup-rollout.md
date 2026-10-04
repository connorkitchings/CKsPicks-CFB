# Unified Data Fix and Matchup Rollout (Historical Investigation Record)

> **Authority update (2026-10-04):** this document preserves dated investigation/decision evidence. [Contract 04, Amendment 2](04-data-integrity-two-window-implementation.md#amendment-2-window-2-measurement-repair-and-prospective-cutover-2026-10-04) and its two appendices document the approved (2026-10-04) Window 2 scope. Earlier neutral-refit, single-batch and all-or-nothing allocation recommendations below are historical, not current instructions. Window 1 remains independent.


- **Status:** Superseded by [04-data-integrity-two-window-implementation.md](04-data-integrity-two-window-implementation.md)
- **Created:** 2026-10-03
- **Planner:** Sol
- **Approval source:** User accepted the unified single-batch recommendation in-session on 2026-10-03 ("only do it once" for production data fixes).
- **Implementation log:** Pending
- **Commit policy:** Separate plan commit on `dev`; implementation commits land with the code phases; production writes are user-run.
- **Supersedes:** [data issues review and rerun](../2026-10-02/05-data-issues-review-and-rerun.md). **Historical scope:** [team stats feeds ratings](../2026-10-02/03-team-stats-feeds-ratings.md) Phase 2 and [matchup data layer v2](../2026-10-02/01-matchup-data-layer-v2.md) Phase B (2025).

> This document preserves the investigation and its original one-batch proposal. It is not execution authority. The user selected two independently gated windows, full R1 subject to attribution certification, no EPA imputation, and an all-certified-week reconstructed replay; see [04](04-data-integrity-two-window-implementation.md).

## Goal

Resolve all known 2026 data-quality issues and the missing `ppa_per_play` production rows in **one Preview → production pass**, then open the matchup page. Observable success: production `team_season_stats` matches Preview in method and row count (11,506 rows, weeks 1–5, incl. `ppa_per_play`); the sealed V5 rating lineage is either verified unchanged or explicitly rebuilt under its own delta report; matchup data is re-pinned only if the rating lineage moves; 2025 backfill is either included or explicitly deferred in the log.

## Why unify

Three open contracts touch the same tables and the same Silver/V5 lineage:

| Plan | What it writes | Depends on |
|---|---|---|
| 2026-10-02/05 (data issues) | Score-stream rule, zero-PPA fix, Silver rebuild decision; team stats rerun | Decisions D1–D4 |
| 2026-10-02/03 Phase 2 | `team_game_stats` dataset; V5 measurements read team stats; rating rebuild | Silver rebuild, team stats structure |
| 2026-10-02/01 Phase B | 2025 matchup tables backfill | 2026 methodology locked, rating lineage stable |

Running them separately would republish `team_season_stats` (and possibly the matchup tables) multiple times in production. The single-batch order is:

```
Investigate (read-only) → Decide D1–D4 → Code → Silver rebuild (if D3)
  → team_game_stats (if D4) → team_season_stats → V5 measurements/ratings (only if D4)
    → matchup data (only if the rating lineage changed) → 2025 backfill (if decided)
      → verify → open CFB_MATCHUP_ENABLED=1
```

## Current State

- **Production `team_season_stats`:** 10,460 rows; V5 play-filter fixes applied 2026-10-02 (1,955 rows changed); **no `ppa_per_play`**.
- **Preview `team_season_stats`:** 11,506 rows; V5 filter fixes + `ppa_per_play` (1,046 only-new rows expected at production dry run).
- **Matchup tables (migration 0021):** live in production (payload `a4a1062d…71215` verified); `/matchup/[gameId]` closed (`CFB_MATCHUP_ENABLED` unset).
- **V5 rating lineage:** pinned to the intended-update run (`v5-intended-update-2026-ratings-v1`, source SHA `e80ae347…`); unchanged since 2026-09-30.
- **Open issues** ([known data issues](../../data/known_issues.md)): (1) non-monotonic play-by-play score stream, ~31–36% of team-games flagged (week 5: 133 of 430); (2) V5 per-play companions still count returned punts (stored, not shown; `ppp`/`epa_per_possession` unaffected); (3) 155 eligible non-punt plays with `ppa == 0`, probably CFBD nulls behind Silver's `fillna(0)`.
- **Flagged score streams per week:** 1: 7/16, 2: 36/102, 3: 72/200, 4: 98/314, 5: 133/430.
- **Week 5 full-slate audit (2026-10-03, read-only):** every one of the 56 matchups was checked across `team_season_stats`, `team_possession_stats`, `team_game_measurements`, `v5_rating_snapshots`, `games` and `game_venues`. Findings:
  - `pts_per_scoring_opp` nulls: 8 rows / 7 games (Vanderbilt offense, Air Force offense+defense, South Carolina defense, Illinois defense, Toledo defense, Old Dominion defense, James Madison offense).
  - **V5 `ppp` is also hit by the score stream, not just the Silver metric:** Kent State offense `ppp = 0.00` despite 29 points scored (W4 vs Ball State quarantined with a 7-point numerator; W3's 3 points attributed elsewhere — identity check pending), Air Force and Army offense `ppp` aggregate over 1 game instead of 2 (W2 quarantined, numerators 14 and 24). `team_game_measurements` shows 129 team-measurements `missing/unresolved_scoring_attribution` for Week 5 teams.
  - **Venue gaps:** `game_venues` rows exist for Northwestern @ Penn State (401858476) and North Dakota State @ Wyoming (401864515) but `city`/`state` are NULL.
  - **Play-filter divergence:** `avg_start_field_pos` (Silver, drive-based) still counts overtime drives starting at the opponent's 25 — e.g. Louisiana Tech defense 40.8, rank 138/138 — while the V5 filter drops them. Ranks for this metric are currently not comparable across teams with/without overtime games.
  - Expected, not bugs: 12 games with null spread/total lean (no line at freeze; matches the Week 5 freeze note); rating-name legacy spellings resolve correctly; all Week 5 teams present in both stats tables; Preview↔production diffs confined to `conv_rate_3rd_4th` and `explosive_rate` (the punt-leak fix) plus the missing production `ppa_per_play`.
  - Full investigation procedure for each finding: [Week 5 data-issue investigation](02-week5-data-issue-investigation.md).

## Scope

### Included

1. Read-only investigation (Phases 0–3 of the absorbed plan 05).
2. Decisions D1–D4 plus the 2025-backfill and matchup-flag decisions, recorded in the decision log.
3. Code changes for the decided fixes (`data/team_stats.py`, `features/byplay/enrichment.py`, `ratings/observations.py` as decided) with tests.
4. One Silver rebuild **only if D3 = now** (punt-return special-teams tag, `fillna` rule, score-stream correction if D1 accepts one, drive-metric play-filter harmonization per Task 1.6).
5. `team_game_stats` builder + V5 measurement/rating rebuild **only if D4 = now**, under its own delta report against the served lineage.
6. `team_season_stats` weeks 1–5 republished to Preview, then production, with `--diff` reviewed at each step.
7. 2026 matchup data republished **only if the rating lineage changed**; otherwise verified unchanged.
8. 2025 matchup backfill **only if decided in this batch** (default: defer).
9. Venue backfill for the two NULL city/state games (Task 1.5 root cause determines re-publish vs fresh capture), in the same production window.
10. Docs: `known_issues.md`, `docs/status.md`, decision log, session log, plans index.
11. `CFB_MATCHUP_ENABLED=1` in production **only after** all writes are verified (user decision).

### Excluded

- Changing the V5 forecast model, the 2026 selected run, or any frozen prediction.
- Preseason prior data (recruiting, returning production, coaching).
- Displaying adjusted values, rating decomposition, or 2025 matchup pages in the web UI.
- Any production write before the Phase 2 decisions are recorded and the user gives the go.

## Rules (carried from plan 05)

- Investigation phases are read-only: no database or lake writes, no new immutable artifacts.
- No production write and no change to a signed V5 artifact or the serving rating lineage without a decision record and the user's go.
- Any change that moves `ppp` or `epa_per_possession` (the only measures the ratings fit) stops the work and needs its own contract and a delta report.
- Preview first, always: `--dry-run --diff`, review, then write.
- Keep `CFB_MATCHUP_ENABLED` unset in production until the final verification step.

## Implementation Tasks

### Phase 1 — Read-only investigation (from absorbed plan 05, Phases 0–3)

**Task 1.0 — Baseline and tooling.**
- Re-confirm baselines: `publish_team_stats.py --season 2026 --weeks 1-5 --environment preview --dry-run` and a read-only production row count.
- Commit the ad-hoc hand-check as `scripts/analysis/handcheck_team_stats.py` with a unit test on a small fixture.

**Task 1.1 — Score-stream investigation (issue 1).**
- Compare raw CFBD plays with Silver for games 401856684, 401856695, 401856698 (Vanderbilt); determine whether dips are provider-side or build-side.
- Build `scripts/analysis/audit_score_stream.py`: for every flagged team-game record the first decrease, drop size, play types around it, restoration, final-score reconciliation; output cause counts.
- Deliverable: counts per cause; whether a safe correction rule exists (e.g. "a drop restored within N rows is provisional").

**Task 1.2 — V5 impact check and D4 flip criterion (read-only).**
- Query `team_game_measurements` (Preview) for flagged team-games: `coverage_status`, `missing_reason`, `quality_flags` on `offensive_possession_points` and `non_offense_points`.
- Check the per-game identity (offensive + non-offense + garbage-time points = final score); Vanderbilt and Kent State W3 (the 3 points that vanish from both `offensive_possession_points` and `non_offense_points` — confirm garbage-time classification) first.
- **Quantify the D1 fix impact on V5 `ppp`:** for every quarantined team-game with a non-zero `offensive_possession_points` numerator (Week 5 teams: 129 measurements; known cases Kent State W4 num=7, Air Force W2 num=14/0, Army W2 num=24), recompute what the team's aggregated `ppp` and rank would be if the quarantine were lifted under the candidate D1 rule.
- **Flip criterion:** if restoring the quarantined numerators moves any team's aggregated `ppp` by more than 0.05 or any rank by more than 5 places, D4 defaults to **now** (V5 rebuild in this batch) instead of later, because serving stale `ppp` next to corrected team stats would make the matchup page internally inconsistent.
- Deliverable: affected team-games with numerators, simulated `ppp` deltas and rank shifts per team, and the D4 recommendation.

**Task 1.3 — Verify the unverified drive metrics (read-only).**
- Hand-check `scoring_opp_rate`, `pts_per_scoring_opp`, `avg_start_field_pos` for two clean-score teams and two flagged teams.
- Acceptance: equal to four decimals, or every difference explained.

**Task 1.4 — Zero-PPA audit (read-only).**
- Confirm whether the 155 eligible non-punt `ppa == 0` plays are CFBD nulls hidden by Silver's `fillna(0)`.

**Task 1.5 — Venue-gap investigation (read-only).**
- For 401858476 (Northwestern @ Penn State) and 401864515 (North Dakota State @ Wyoming): read the Bronze venue/game captures behind the `game_venues` rows; determine whether CFBD returned null city/state or the publisher dropped them.
- Check the rest of 2026 for the same pattern (`game_venues` rows with NULL city/state).
- Deliverable: root cause + the backfill path (re-run the venue publisher from an existing capture vs. a fresh capture), scoped into Phase 5 as part of the single production batch.

**Task 1.6 — Play-filter harmonization audit for drive metrics (read-only).**
- Quantify how many teams' `avg_start_field_pos` (and `scoring_opp_rate` denominators) are distorted by overtime/placeholder drives that the V5 filter drops but the Silver drive-based metrics keep; reproduce the Louisiana Tech defense case (40.8, rank 138/138).
- Deliverable: affected-team count and rank-shift simulation if the drive metrics adopted the V5 exclusion; feeds the D3 (Silver rebuild) decision — harmonization is in scope of the rebuild only if D3 = now.

**Acceptance:** findings recorded in `known_issues.md` with counts; no writes of any kind.

### Phase 2 — Decide (user, with Sol)

- **D1 score-stream rule:** keep quarantine; accept a correction rule (needs contract + tests); or take scoring-drive points from CFBD `drives`. Note the quarantine now demonstrably costs V5 `ppp` games (Kent State, Air Force, Army), so "keep quarantine" is no longer a zero-cost option.
- **D2 zero-PPA plays:** treat as missing/null or accept as zeros.
- **D3 Silver rebuild:** now or at the planned rating rebuild. **Working assumption: now** — and if now, it also carries the Task 1.6 drive-metric play-filter harmonization (overtime/placeholder exclusion for `avg_start_field_pos`).
- **D4 V5 measurement/rating rebuild:** now or later. **Working assumption: later**, but the Task 1.2 flip criterion applies: if lifting quarantines under the candidate D1 rule moves any team's `ppp` by more than 0.05 or any rank by more than 5 places, D4 defaults to **now** (its own delta report still required — that is the plan's standing stop condition, not a waiver).
- **D5 2025 matchup backfill (plan 01 Phase B):** in this batch or deferred. **Working assumption: deferred.**
- **D6 matchup flag:** enable `CFB_MATCHUP_ENABLED=1` after verification, or keep closed pending separate review. **Working assumption: enable after verification.**
- Each decision recorded in the decision log.

### Phase 3 — Code and tests (on `dev`)

1. Implement the decided D1/D2 rules (`ratings/observations.py`, `features/byplay/enrichment.py` fillna policy as decided).
2. If D4 = now: build `team_game_stats` per plan 03 Phase 2 design (per-game numerator/denominator rows; `team_season_stats` becomes an aggregation; drive-point reconstruction moves out of `ratings/observations.py`).
3. `publish_team_stats.py --diff` per-metric delta reporting (old vs new value, rank shifts, top movers, rows changed).
4. Tests: play filters, team-stats leak guard, enrichment, hand-check script fixture.
5. Full CI rehearsal on a clean worktree before any push (see `web/README.md`).

### Phase 4 — Preview dry run, review, write

1. If D3: build and validate Silver (`scripts/pipeline/build_silver.py`), then `make promote-silver YEAR=2026`.
2. If D4: V5 measurements and ratings through the reviewed weekly cycle (`scripts/pipeline/run_v5_weekly_cycle.py`) under its delta report against the served lineage; then `make matchup-data YEAR=2026 ENV=preview RATING_URI=… MEASUREMENT_URI=… APPLY=1` and `verify_matchup_data.py`.
3. Team stats Preview: `publish_team_stats.py --season 2026 --weeks 1-5 --environment preview --dry-run --diff`, review deltas (only decided metrics may move), write, then `verify_team_stats.py --season 2026 --as-of-week 5 --environment preview` plus the Phase 1 hand-check.
4. If D5: 2025 matchup backfill on Preview (plan 01 Phase B tasks, `lineage='historical_replay'`).

### Phase 5 — Production write (user-run)

Same order as Phase 4, each step dry-run with `--diff` compared against Preview's before writing, then verify. Expected team-stats dry run: 11,506 rows, 1,046 only-new (`ppa_per_play`), 2,291 changed, only conversion/explosive/turnover rates changing (plus whatever D1–D4 decide). Week 6 team stats follow after Week 5 finals are certified.

### Phase 6 — Close

1. Move issues 1–3 in `known_issues.md` to Resolved (or Accepted with the reason).
2. Update `docs/status.md`, plan 03 (Phase 2 status), plan 01 (Phase B status), plans index, decision log, session log.
3. Only now, per D6, set `CFB_MATCHUP_ENABLED=1` in production and spot-check a real Week 5 matchup page.

## Testing Strategy

- Unit tests for every code change (filters, enrichment fillna, score-stream rule if accepted, hand-check script).
- `publish_team_stats.py --diff` delta review as the data-level regression gate on Preview and production.
- `verify_team_stats.py` + `verify_matchup_data.py` (11 gates) after each write.
- Full Python suite with `-W error`; web lint/typecheck/`test:publication`/build/Playwright if any web file changes.
- Hand-check acceptance: metrics equal to four decimals on the Phase 1.3 teams, or every difference explained.

## Risks and Edge Cases

- **Rating lineage drift:** if D4 = later while D3 = now, team stats and V5 measurements diverge in source until the planned rating rebuild; accepted as a documented interim state (companions are stored, not fitted).
- **Score-stream correction risk:** any rule that "fixes" dips could introduce wrong points; default is to keep quarantining unless Phase 1 proves a safe, high-coverage rule.
- **One-shot failure:** if a Preview/production diff shows metrics moving that the decisions do not explain, stop and investigate; do not write.
- **Stop conditions (carried):** Phase 1.2 shows V5 `ppp`/`epa_per_possession` would change → stop, write a contract. CI red, or production dry-run diff ≠ Preview's → do not write.
- **Scope creep:** 2025 backfill adds significant work; deferred by default unless D5 says otherwise.

## Definition of Done

- [ ] Phase 1 findings recorded in `known_issues.md` with counts (incl. the Week 5 audit items: venue gaps, drive-metric divergence, V5 `ppp` quarantine cases).
- [ ] Venue city/state backfilled for 401858476 and 401864515 (or the NULLs explained and accepted).
- [ ] D1–D6 decided and logged (D4 per the Task 1.2 flip criterion).
- [ ] Preview and production `team_season_stats` produced by the same code and Silver version; production includes `ppa_per_play`; hand-checks pass.
- [ ] If rebuilt: V5 delta report reviewed, matchup data re-pinned and verified; otherwise matchup tables verified unchanged.
- [ ] 2025 backfill complete or explicitly deferred in the log.
- [ ] `known_issues.md` items resolved or explicitly accepted; docs and session log updated.
- [ ] `CFB_MATCHUP_ENABLED=1` set only after verification (or explicitly kept closed per D6).

## Carry-forward (separate from this contract)

- Week 5 close after certified finals: `scripts/pipeline/backfill_v5_unconstrained_grades.py --week 5 --grades-only` ([plan 2026-10-02/04](../2026-10-02/04-remove-edge-constraints-grade-all-games.md)).

## Amendments

> **Pointer (2026-10-03):** the read-only investigation finished; its evidence and the D1-D9 recommendations are in the [decision packet](03-data-decision-packet.md), and the investigation's own scope additions are in [Amendment 3 of plan 02](02-week5-data-issue-investigation.md). This contract's scope and its D1-D6 gate are unchanged; the matchup pages are live by default (user decision), so D6 now means confirming them after the batch.

### Amendment 1 — Unified single-batch scope

**Reason:** User direction 2026-10-03: if a production data fix is going to run eventually, run it once.
**Original approach:** Plan 05 reviewed and reran the data issues alone; plan 03 Phase 2 rebuilt at "the planned rating rebuild"; plan 01 Phase B backfilled 2025 "afterwards".
**Revised approach:** One contract owns the whole sequence with decision gates (D1–D6); plan 05 is superseded, plan 03 Phase 2 and plan 01 Phase B are absorbed as decision-gated scope.
**Impact:** No production writes change until Phase 2 decisions are recorded; read-only phases are unaffected.

### Amendment 2 — Week 5 full-slate audit findings (2026-10-03)

**Reason:** A read-only audit of all 56 Week 5 matchups (Preview, compared with production) found that the score-stream quarantine also empties V5 `ppp` for several teams (Kent State `ppp=0.00` despite 29 points; Air Force and Army one-game samples), two games have NULL venue city/state, and the Silver drive metrics keep overtime drives the V5 filter drops (`avg_start_field_pos` distortion).
**Original approach:** Task 1.2 only asked whether V5 was affected; venues and the drive-metric filter divergence were out of scope; D4 = later by default.
**Revised approach:** Task 1.2 gains an explicit flip criterion (ppp move > 0.05 or rank move > 5 places ⇒ D4 = now); new Tasks 1.5 (venue gaps) and 1.6 (drive-metric harmonization) feed D3; venue backfill joins the single production batch; the detailed procedure lives in [02-week5-data-issue-investigation](02-week5-data-issue-investigation.md).
**Impact:** Still no writes; Phase 1 grew by two read-only tasks and Phase 2 decisions gained evidence-based defaults.
