# Score-attribution investigation: the quarantined games, one by one

- **Status:** Implemented (2026-11-12, uncommitted on a branch; needs review, commit and pull request into `dev`)
- **Created:** 2026-11-12
- **Planner:** Sol
- **Approval source:** Owner approved implementation on 2026-11-12, after the direction of the same day: document the 44 quarantined games and examine each individually; the goal is to repair the running-score problem directly, not to keep removing games.
- **Implementation log:** [`session_logs/2026-11-12/03-score-attribution-investigation-impl.md`](../../../session_logs/2026-11-12/03-score-attribution-investigation-impl.md). Report: [score-attribution investigation](../../modeling/score_attribution_investigation_2026.md); data: `docs/modeling/evidence/score_attribution_games_2026.json`.
- **Commit policy:** Commit on local `dev` with implementation (documentation and read-only analysis only). Any later change to how scores are attributed is a separate contract.

## Goal and acceptance

The V5 pipeline leaves a team's offense (and the opponent's defense) out of the ratings for a game when the play-by-play running score cannot be attributed to possessions (`missing / unresolved_scoring_attribution`). That is a quarantine. The owner's position is that quarantining is a workaround, not a design: the running-score problem should be understood and fixed at its source. This contract is the read-only investigation that makes that fix specifiable.

Acceptance:

1. A per-game record for each of the 44 games in the Week 9 audit ledger (`quarantine_source_ledgers` in `docs/modeling/evidence/v5_offense_defense_ratings_audit_2026.json`: 39 partial and 5 whole-game quarantines, 98 unusable team-game-role observations), plus every game added to `conf/season/2026/score_reconciliation_exceptions.json` since (it holds 54 entries on 2026-11-12), with: game, week, teams, final score, the stored possession points per team, how the running score behaves around each defect, whether it is restored later, whether the maximum running score reconciles with the final, and the root-cause class.
2. A root-cause classification that covers every game, built from the raw provider plays and compared with the Silver rows, so each game is labelled either "defect in the provider feed" (with the evidence) or "defect in our handling". No game is classified without reading its plays.
3. For each class, a specified repair that reconstructs the points correctly instead of dropping the game, with the prior candidate rule (R1, the monotone envelope capped by the game final, in [known issues](../../data/known_issues.md) item 1) evaluated against the full set, including the 18 team-games R1 left unresolved (single-row jumps above 8 points).
4. A statement of what each repair would change in the V5 ratings if it had been applied to 2021 to 2025, measured read-only, so the next-model contract can decide. No change reaches the 2026 record, any release, Production or the stored data.

## Baseline and constraints

- Prior work is not redone: [known issues](../../data/known_issues.md) item 1 (the raw feed itself has the dips: 272 drop events in 158 team-games in the week 0 to 4 Bronze captures, none from our build; about a third of team-games affected), item 10 (the same rate in 2025, 8.1% quarantined), the October 3 investigation notes under `artifacts/backups/2026-10-03/investigation/`, and the [ratings audit](../../modeling/v5_offense_defense_ratings_audit_2026.md) section "Score exceptions and asymmetric quarantine". This contract extends them with per-game evidence.
- The 2026 V5 model is frozen for the 2026 record. Nothing here may change a 2026 prediction, grade or release. A repair is a candidate for the next model version under the [research protocol](02-offseason-research-protocol.md).
- Read-only: raw Bronze captures and Silver datasets are read, never written. Score exceptions stay immutable in place. No provider calls.
- Out of scope: changing `true_drive_points`, the score exceptions file, Silver or any stored table; deciding the next-model design.
- Stop gates: if a root cause needs a new provider request to settle (for example a different CFBD endpoint), list the exact request and its cost and stop for owner approval; do not call the provider.

## Ordered changes

1. **Inventory.** Build the list of games from the audit ledger and the current exceptions file. Output: a table in the report with the counts per week and per quarantine kind.
2. **Per-game reading.** For each game, read the raw plays and the Silver rows around every running-score defect and record the pattern (drop to zero, point-after credited before the kick, reversal after a penalty or review, scoring row restored later, score never restored, maximum below or above the final). Output: one row per game in a data file plus a plain-language paragraph for each distinct pattern.
3. **Classification.** Group the games by root cause and state which classes are provider defects and which, if any, are our handling. Output: the class table with counts and example games.
4. **Repair specification.** For each class, write the rule that reconstructs the true points per possession from the available evidence, the evidence it relies on, and its failure cases. Evaluate R1 and any new rule on the whole set: share of team-games whose reconstructed points equal the final, and games still unresolved with the reason.
5. **Historical effect.** Apply each candidate rule read-only to 2021 to 2025 and report how many team-games it restores and how the observation and rating values would move. No ratings are written.
6. **Report.** `docs/modeling/score_attribution_investigation_2026.md` plus the data file under `docs/modeling/evidence/`, linked from the backlog and the known-issues page.

## Validation

- Every game in the inventory has a record, and the class counts sum to the inventory total.
- A spot check: five games chosen across classes are re-read independently and match their records.
- The reconstruction rule reproduces the final score for every restored team-game by construction, and a test proves a rule never exceeds the game final.
- `git diff --check`, `uv run mkdocs build --strict --quiet`, and tests for any new code.

## Handoff/amendments

Approval and resume gate: the owner approves this path for implementation. A repair that changes stored data or metric definitions needs its own contract after this report. Related: [prediction-error diagnostics](03-prediction-error-diagnostics.md), whose partial-quarantine view is descriptive only until this investigation supplies a real repair to test.
