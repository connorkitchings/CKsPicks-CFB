# Week 5 Data-Issue Investigation (Read-Only Deep Dive)

- **Status:** Approved (read-only; this plan authorizes investigation only — every write stays gated behind [the unified rollout](01-unified-data-fix-and-matchup-rollout.md) decisions D1–D6)
- **Created:** 2026-10-03
- **Planner:** Sol
- **Approval source:** User approval in-session 2026-10-03 ("write out a plan for continued digging into these many data issues"), following the Week 5 full-slate audit.
- **Implementation log:** Audit queries run in-session 2026-10-03 (session log `02`); findings summarized below as starting points.
- **Commit policy:** No code commits from Phases A–F except the two committed analysis scripts (Tasks A2, C1) and their tests, which land on `dev` with normal CI. Findings are recorded in `docs/data/known_issues.md`.

## Goal

Produce decision-ready evidence for D1–D4 and the venue/harmonization items of the unified plan: for every open data issue, a cause classification, an impact count, a simulated fix delta, and a recommendation. Nothing here writes to the lake or any database.

## Evidence base (from the 2026-10-03 audit)

- 56 Week 5 games; all teams present in `team_season_stats` and `team_possession_stats`.
- `pts_per_scoring_opp` nulls: 8 rows / 7 games (Vanderbilt off; Air Force off+def; South Carolina def; Illinois def; Toledo def; Old Dominion def; James Madison off).
- V5 quarantine casualties: 129 `missing/unresolved_scoring_attribution` team-measurements for Week 5 teams; Kent State offense `ppp=0.00` (W4 num=7 quarantined; W3's 3 points unattributed — identity check pending); Air Force W2 (num=14/0) and Army W2 (num=24) quarantined, leaving 1-game samples.
- Venue gaps: 401858476 (Northwestern @ Penn State), 401864515 (North Dakota State @ Wyoming) — rows exist, city/state NULL.
- Drive-metric divergence: `avg_start_field_pos` keeps overtime drives (Louisiana Tech def 40.8, rank 138/138).
- Zero-PPA plays: 155 eligible non-punt plays with `ppa == 0` (from contract 05's baseline).

## Prerequisites

- `CFB_STORAGE_BACKEND=r2` plus `CFB_R2_*` credentials loaded (not currently in the shell; `.env` only carries the backend name and DB URLs).
- Read-only roles only: `PREVIEW_DATABASE_URL` (read) for Neon; R2 reads via the existing `read_any`/catalog helpers.
- A scratch output dir under `artifacts/backups/2026-10-03/investigation/` for JSON/CSV findings (working copies, not lake writes).

## Phase A — Score-stream cause classification (feeds D1)

**A1. Raw-vs-Silver comparison (Vanderbilt trio + the new quarantine cases).**
For games 401856684, 401856695, 401856698 (Vanderbilt W2–W4), 401866425 (Kent State W4), 401864502 (Air Force W2), 401862702 (Army W2): pull the Bronze CFBD play capture (or a read-only CFBD re-fetch, rate-limit aware) and diff the running-score columns against Silver `byplay`. Classify each dip as (a) present in the raw feed, (b) introduced by `features/byplay/enrichment.py`, or (c) introduced by Silver reconciliation.
**Output:** per-game table: first decreasing row, play type before/at/after, drop size, restoration distance, final-score reconciliation.

**A2. Committed audit script.**
`scripts/analysis/audit_score_stream.py`: for every flagged team-game (the `ppso_invalid_offenses` sets, weeks 1–5), emit the A1 columns plus a cause label from a fixed taxonomy (working hypotheses: extra point credited before the kick on defensive/special-teams touchdowns; reversed or mislogged touchdown taken back on the next row; penalty-row score desync; unexplained). Unit test on a small synthetic fixture.
**Output:** cause counts per week; the share of flagged team-games each cause explains; whether a safe correction rule exists (e.g. "a drop restored within N rows is provisional and the restored value is authoritative").

**A3. D1 options matrix.**
For each D1 option (keep quarantine / correction rule / CFBD `drives` points), record: team-games recovered, risk of wrong points, code surface touched, test burden.
**Output:** one table, recommendation, and the candidate rule spec precise enough to implement if chosen.

## Phase B — V5 impact quantification and the D4 flip (feeds D4)

**B1. Quarantine inventory.**
From `team_game_measurements` (Preview): every `missing/unresolved_scoring_attribution` row for 2026 weeks 1–4 with a non-zero `offensive_possession_points` numerator (these are real points the ratings never saw). Known: Kent State W4 (7), Air Force W2 (14), Army W2 (24).
**B2. Identity checks.**
For each quarantined team-game, run offensive + non-offense + garbage-time = final score. Specifically resolve **Kent State W3**: offense `offensive_possession_points = 0` observed while the team scored 3 — confirm garbage-time classification is the explanation (losing 59–3) and that nothing is silently dropped.
**B3. Simulated fix.**
Under the candidate D1 rule from A3, lift the quarantine in-memory and recompute each affected team's aggregated `ppp`, rank and cohort. Apply the unified plan's flip criterion (> 0.05 ppp move or > 5 rank places ⇒ D4 = now).
**Output:** per-team before/after table for every affected team; explicit D4 recommendation.

## Phase C — Drive-metric verification and harmonization (feeds D3)

**C1. Committed hand-check script.**
`scripts/analysis/handcheck_team_stats.py` (unified plan Task 1.0): recompute `scoring_opp_rate`, `pts_per_scoring_opp`, `avg_start_field_pos` from Silver `byplay`/drives for two clean-score teams and two flagged teams; equal to four decimals or every difference explained. Unit test on a fixture.
**C2. Overtime/placeholder distortion.**
Count teams whose `avg_start_field_pos` includes overtime drives (drive starts at the opponent's 25) or "End of Game" placeholders; reproduce Louisiana Tech defense (40.8, rank 138/138). Simulate the rank shift if the V5 exclusion were applied.
**Output:** affected-team count, simulated rank shifts, and the exact filter change for the Silver rebuild if D3 = now.

## Phase D — Zero-PPA audit (feeds D2)

**D1.** For the 155 eligible non-punt `ppa == 0` plays: join back to the Bronze CFBD capture and classify each as (a) CFBD null → Silver `fillna(0)`, (b) genuine zero-EPA play, (c) build artifact.
**D2.** Simulate the D2 = null option: recompute `ppa_per_play`, `epa_pass`, `epa_rush`, `early_down_epa` means excluding the (a)-class plays; report value and rank deltas.
**Output:** classification counts + delta table + D2 recommendation.

## Phase E — Venue gaps (feeds the production batch)

**E1.** Read the Bronze venue/game captures behind `game_venues` rows 401858476 and 401864515; determine whether CFBD returned null city/state or the publisher dropped them.
**E2.** Scan all 2026 `game_venues` rows for NULL city/state; count and list.
**E3.** Decide the backfill path: re-run the venue publisher from an existing capture, or a fresh capture (`make fetch-source`), inside the unified plan's Phase 5 production window.
**Output:** root cause, full NULL list, chosen backfill command sequence (executed later, in the batch).

## Phase F — Cross-checks and recording

**F1.** Re-run the Preview-vs-production diff (the audit's inline query, committed into `audit_score_stream.py --env-diff` or a sibling script) so the batch has a regression baseline: expect diffs confined to `conv_rate_3rd_4th`, `explosive_rate` and missing production `ppa_per_play`.
**F2.** Record every finding in `docs/data/known_issues.md` (counts, causes, affected lists) and update the unified plan's Phase 2 evidence.
**F3.** Present the D1–D6 recommendation packet to the user; no writes until the decisions are logged.

## Acceptance / Definition of Done

- [ ] A1–A3: cause taxonomy with per-week counts; D1 options matrix delivered.
- [ ] B1–B3: quarantine inventory, Kent State W3 identity resolved, simulated `ppp` deltas, D4 recommendation against the flip criterion.
- [ ] C1–C2: hand-check script committed with tests; overtime distortion counted and simulated.
- [ ] D1–D2: zero-PPA classification counts and delta table; D2 recommendation.
- [ ] E1–E3: venue root cause, full NULL scan, backfill path chosen.
- [ ] F1–F3: env-diff baseline recorded; `known_issues.md` updated; recommendation packet presented.
- [ ] Zero lake/DB writes performed; the only committed artifacts are the two analysis scripts + tests on `dev`.

## Stop conditions

- Any query needs write access → stop; the answer belongs in the unified plan's write phases.
- A finding shows the served V5 ratings themselves are wrong (not just thin) → stop and escalate to a standalone contract; this plan cannot authorize a rating change.
- CFBD rate limits block A1 → use existing Bronze captures only and note the coverage gap.
