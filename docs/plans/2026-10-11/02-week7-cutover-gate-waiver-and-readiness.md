# Week 7 cutover gate waiver and readiness

- **Status:** Approved
- **Created:** 2026-10-11
- **Planner:** Sol (planning session) · **Implementer:** Terra
- **Approval source:** The user approved the plan in Plan Mode on 2026-10-11 after three decisions (below). Approval covers local code, tests, documentation and the exact data steps listed here, each still run as its own user go-ahead. It is not a Production release authorization.
- **Planning log:** `session_logs/2026-10-11/05-week7-waiver-planning.md`
- **Commit policy:** Separate commits; the user controls Git.

## User decisions (2026-10-11)

1. **Attempt the Week 7 cutover.** The Sunday-evening checkpoint rule ("if the successor Week 6 certification integration is not built and tested by then, move the cutover to Week 8") and the October 9 direction that integrity closure precedes the cutover are **waived for the Week 7 cutover only**.
2. **Plan the dev → main release** so graded Week 6 appears on the public site.
3. **Grade Week 6 today and remove the 24-hour finals-stability rule from operations permanently.** The user said the rule can be removed; the research and prospective-evidence verifiers are not part of that decision (see scope).

## Gates that still stand

Preview before Production; dry run, then user-run apply, then independent readback; owner-login rollback proof in the Preview rehearsal; Tuesday 2026-10-13 14:00Z pivot to a frozen standalone Week 7; 22:00Z freeze deadline (first kickoff 23:00Z); the three early-game late-quote exceptions stay disabled; Week 6 is never frozen or closed; a separate exact Production approval for every Production write, authorization and selection.

## Obligations carried past the waiver

These remain open and are tracked in the [repair completion matrix](../2026-10-08/02-repair-track-certification-and-closure.md#completion-matrix): historical EPA replacement and exact stale-key cleanup, the six quality follow-ups, scoring/full-metric correctness, descendant recertification, and the complete 2025 matchup candidate. The 2025 candidate is still certified before its publication (Amendment 10). The waiver does not close any of them.

## Replacement for the stability rule

Finals load once every scheduled game is `completed` in a fresh CFBD capture taken at load time and a certified Silver `game_outcomes` ref covers all of them. `finals_stabilized_at` in certification receipts now means the all-final observation time; the cutoff must not precede it. A late score correction is caught by `load_game_finals.py`'s conflict stop and handled by an owner-role correction and re-grade, so complete pre-write exports are mandatory. For Week 6, one CFBD diff at or after 2026-10-12T14:08Z is recorded as monitoring, not as a gate.

## Scope

- **Code:** `ops/v5_cycle.py` and `ops/v5_batch_selection_v2.py` drop the 24-hour wait and keep timestamp validation; `build_corrected_successor_lock.py` derives its weeks from the base lock and takes `--week6-display-run-id` and `--week-config`.
- **Not changed, deliberately:** `ratings/prospective_v5*.py`, `forecast/shadow*.py`, `build_rating_shadow_score.py` and the `score_stabilization_seconds` policies in `conf/ratings/` and `conf/research/`. They verify pre-registered, sealed evidence designs and are off the weekly serving path.
- **Lock extender:** the lock records Silver kickoffs only and cannot observe the database's old values, so append mode needs no kickoff-revision recording. The three Week 6 differences (401862797, 401856827, 401856808) are retained as evidence; the serving `games` table is not rewritten here.
- **Data steps (separate user go-aheads):** `ops prepare-week` for the post-Week-6 Silver refresh; pre-write exports; Week 6 finals load and grades-only backfill (Preview, then Production); the Weeks 0–6 corrected replay chain in Preview; Week 7 preparation.
- **Release:** the user merges `dev` into `main`; the deployed revision is verified afterwards.

## Known facts the steps rely on (verified 2026-10-11 against source)

- `backfill_v5_unconstrained_grades.py` applies unless `--dry-run` is passed, and Production needs `--confirm-production` even to dry-run. Always pass `--dry-run` first.
- `RECOMPUTE_STATS_SQL` counts only `scored` runs, so `system_stats` stays at Weeks 0–5; `main`'s Performance query also counts only `scored` runs. Public Week 6 visibility needs the `dev` release.
- `load_game_finals.py` writes no backup and loads finals for all 58 scheduled games, including the three without predictions.
- The market-sources lock `--as-of` must be at or after the snapshot capture (2026-10-08T16:19Z); the forecast cutoff is set separately.
- `audit_point_in_time_leakage.py` needs explicit Week 6 run, lock, rating and bridge overrides.

## Validation

Focused pytest over the successor lock, batch selection, lock extension, finals loader, backfills, market-sources lock and leakage audits; scoped Ruff; documentation-authority tests; `mkdocs build --quiet`; `git diff --check`. Real-data checks run per the approved plan with their own receipts.

## Amendments

None.
