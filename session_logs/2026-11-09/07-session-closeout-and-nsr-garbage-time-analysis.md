# Session: 2026-11-09 close-out and net success rate garbage-time analysis

## TL;DR

- **Worked On:** Closed out the 2026-11-09 session: underdog picks (every pick, featured card, header, win rate), the model page market comparison, CFBD retrospective lines for three Week 6 games, the Net success rate overtime change and its Preview release, the Production migration and `dev` into `main` release, and a read-only analysis of why our Net success rate for UGA 42-7 Ole Miss differs from Parker Fleming's chart.
- **Outcome:** Everything is merged to `dev`, and `main` carries the release (PR #29). The Production database has migration 0029. Preview serves the retrospective lines and overtime counts; Production still serves its Week 11 release until the next weekly run. The analysis found that a tighter garbage-time rule, not the success definition or missing plays, reproduces his chart (details below). Nothing was changed on the site for it.
- **Plan Contract:** each change has its own contract under `docs/plans/2026-11-08/` and `docs/plans/2026-11-09/` (see Work Completed); the analysis is `N/A (fast path, read-only)`.
- **Approval / Status:** Owner approved each change in this session; the contracts are `Implemented`. Merges were done by the owner.
- **Blockers:** None.
- **Next:** Sunday 2026-11-15, the scheduled close-week run builds the first Production release carrying the overtime columns and the three retrospective Week 6 grades. Check its receipts. Optional: decide whether the Net success rate chart should use a tighter garbage-time rule (needs a stored per-game column and a release, like the overtime change).

**tags:** ["session-closeout", "net-success-rate", "analysis", "underdog-picks", "release"]

## Context and Decisions

- Merged PRs on `dev`: #20 model page comparison, #21 scatter details above the tab bar, #22/#23/#24 underdog picks, flipper and every pick, #25 card header and copy, #26 CFBD retrospective lines, #27 overtime in Net success rate, #28 and #30 `AGENTS.md` and status notes, #31 win rate on the underdog record. `dev` was released to `main` as #29.
- Process decision (owner): finish and validate work locally, rebase on the latest `origin/dev`, then push once and open the PR in the same step. Delegated workers never push. Recorded in `AGENTS.md`.
- The Net success rate chart keeps dropping garbage time and now includes overtime. Keeping garbage time was tested and rejected (rank agreement with his order fell from 0.966 to 0.952 and the UGA bar did not move).
- Weekly automation: paused on 2026-11-09 and re-enabled after the release PR merged (`CFB_WEEKLY_AUTOMATION_ENABLED` is `true`).

## Work Completed

- Contracts: `model-performance-dashboard.md`, `model-underdog-picks.md` (2026-11-08); `underdog-flipper.md`, `all-underdog-picks.md`, `featured-card-header.md`, `cfbd-retrospective-lines.md`, `nsr-include-overtime.md` (2026-11-09). Their session logs are `session_logs/2026-11-08/02`, `03` and `session_logs/2026-11-09/01` to `06`.
- Production database: migration 0029 (two nullable overtime success columns) applied by the owner login after a read-only check that the target was Production; the live site stayed healthy.
- Analysis (read-only, scripts only in the session scratchpad, not committed):
  - Our Week 10 byplay data matches CFBD box scores (8,199 scrimmage rows vs 8,192; 95 of 124 team-games identical; all five blowouts checked match exactly), and the stored success flags match a 50/70/100 recompute on all but 51 of 8,191 plays (about 42 are turnovers, failures by design).
  - UGA 42-7 Ole Miss from the plays: UGA 34 of 63 (.540), Ole Miss 26 of 69 (.377), net +0.163 with garbage time kept; +0.160 with our garbage flag; CFBD's own `successRate` gives +0.147. Fleming's bar is about +0.465 (read off an image).
  - Tighter garbage-time rules reproduce his chart: dropping plays when the score margin passes 17 to 27 points lowers the largest error against his six readable values from 0.305 to 0.043 to 0.058 and raises rank agreement over all 62 games from .966 to about .98 (flat 24 gives UGA .422, TLSA .422, OKST .380, DUKE .179, OHIO -.148, SJSU -.123). Our own pipeline flag never marks Q1 or Q2 as garbage time and starts about 33 to 35 points in Q3 and 27 points in Q4.
  - Quarter-specific thresholds (900 rules tried) do not beat a flat cut: the best by ordering (Q2 over 21, Q3 over 17, Q4 over 17; .984, error .043) and the best by value fit (Q2 over 17, Q3 over 24, Q4 over 28; .972, error .032) trade off within the noise of his image-read values.
  - UGA 42-7 under each rule (UGA / Ole Miss / net): all plays .540 / .377 / +.163; our flag .500 / .340 / +.160; margin over 21 to 27 removed .613 (31 plays) / .190 (21) / +.422; over 14 to 17 removed .789 (19) / .267 (15) / +.523.

## Files Modified

- This log only (`session_logs/2026-11-09/07-session-closeout-and-nsr-garbage-time-analysis.md`). All code and docs changes of the session are in the merged PRs above.

## Validation

- [x] Final state of `dev` after #31: `make check` and `make web-e2e` were run on each PR before it was pushed (last run 449 passed, 10 skipped, plus the known expected-failure market board test); all PR checks passed.
- [x] `git diff --check` on this log

## Amendments and Blockers

- None. One CI step (coverage upload on PR #28) failed with a GitHub network reset and passed on re-run.

## Handoff Notes

- **Resume at:** Sunday 2026-11-15 weekly run, or the optional tighter garbage-time rule for the Net success rate chart. Session otherwise complete.
- **Watch out for:** Production still has the old record (271-279-9 and 267-289-2) and shows "success rate unavailable" on the Net success rate chart until that run. A Production release of any candidate needs the Preview proof and the owner's go-ahead for manual runs. Two local items are not part of this work: the `codex/v5-ratings-audit` worktree has two commits that exist only locally, and a stash entry (`wac-tmp` on `connorkitchings/weekly-automation-catchup`) is still present. The old local `connorkitchings/matchup-rating-breakdown` branch and worktree are a pre-rebase duplicate of work already on `dev`; removal is pending the owner's go-ahead.
