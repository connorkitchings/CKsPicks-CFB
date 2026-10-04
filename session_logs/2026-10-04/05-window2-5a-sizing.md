# Session: Window 2 Step 5A (sizing) — opened

## TL;DR
- **Worked On:** Opened 5A. Recorded the user's three decisions, froze the group, channel and cause definitions before any historical evidence, and built the non-serving R1 candidate and group-diff module with tests.
- **Outcome:** No historical diff, CFBD request, R2 write or database write has been run. The port reproduces the 2026 investigation (145 changed team-games, rollback and cap counts exactly). The 25% gate has not been evaluated.
- **Plan Contract:** `docs/plans/2026-10-03/04-data-integrity-two-window-implementation.md`, Amendment 2, Appendix A (5A).
- **Approval / Status:** Amendment 2 approved 2026-10-04. The user directed 5A to open on 2026-10-04.
- **Scope note:** the user described 5A as covering "the retrospective replay and best-quote alignment for Weeks 0-5". As contracted, 5A is the scoring-allocation sizing and baseline reproduction; the replay is 6B. The best-quote part is already sized for Weeks 0-5 (known issue 13).

## Decisions (user, 2026-10-04)
1. Grouping: per team-game region.
2. If the 25% gate fails: stop and review, as the contract says. No pre-authorized reduced Window 2.
3. CFBD: compute the diff offline first, report games and request count, fetch only changed games after the user approves.

## Verified this session
- The baseline ledger builder is `build_possession_ledger` (`possession_measurements.py:104`, rollback at :294, final cap at :358). R1 existed only as investigation scratch code (`delta_build_candidate.py`); no R1 code is in `src/` apart from the new module.
- The Preview catalog holds Silver plays, byplay, drives, games, game outcomes, team-game stats and reconciliation for 2015-2019, 2021-2025 and 2026. Production holds plays for 2021-2026 only, so the sizing runs on Preview. No CFBD drive retention exists for 2015-2025 (the only CFBD drive files are 2026 weeks 0-4).
- `CFBD_API_KEY` is present in the environment (value not read).
- The prior 2026 evidence leans against the gate: CFBD drives were clean in 9 of 30 affected team-games and, on clean ones, agreed with the baseline on 36 of 66 differing drives versus 28 for R1 (decision packet items 21 and 26, labelled verified there; not re-derived by me). That is evidence about 2026 weeks 0-4, not a forecast for the historical corpus.

## Built
- `docs/plans/2026-10-03/window2/5a-frozen-definitions.md`: frozen definitions plus the port check.
- `src/cks_picks_cfb/ratings/score_envelope_r1.py`: `apply_r1`, `restoration_jumps`, `align_events`, `changed_groups`, `summarize_groups`. Not wired into serving, ratings or any publisher.
- `tests/test_score_envelope_r1.py`: 10 tests.

## Next (not started)
1. Baseline reproduction of the served artifacts (byte or canonical record hash) for the full served lineage: needs the exact measurement and rating manifest ids from `docs/plans/2026-09-29/v5-repair-2026-source-lock.json` and the repair manifest's per-season Silver refs.
2. Historical baseline-versus-R1 diff for 2015-2019 and 2021-2025 from the pinned Silver byplay and game outcomes (read-only on Preview R2; compute-heavy), plus null-PPA exposure by season, metric and team-game.
3. Report changed groups, games and CFBD request count; wait for the user's go-ahead before any CFBD request.
4. Corroboration, go/no-go, signed sizing receipt (the signing and any R2 publication are user-run).
