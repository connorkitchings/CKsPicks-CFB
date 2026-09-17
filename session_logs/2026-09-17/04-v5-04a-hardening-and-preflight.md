# Session: V5-04A Hardening and Preflight (Terra)

## TL;DR
- **Worked On:** Executing Tasks 1–6 of `docs/plans/2026-09-17/03-v5-04a-hardening-preflight-and-04b-rebase.md`.
- **Outcome:** Hardening code complete and all quality gates pass (full warning-as-error suite 948 passed, 2 skipped). Awaiting user hardening commit; Tasks 7–8 (three-repeat no-write Preview preflight, review/closure, 04B rebase) execute after that commit.
- **Plan Contract:** `docs/plans/2026-09-17/03-v5-04a-hardening-preflight-and-04b-rebase.md` (In Progress).
- **Approval / Status:** Approved plan; Terra executing. Entry state verified: HEAD `da19a54`, clean worktree, 04A checkpoint `d380765` beneath.
- **Blockers:** None. Preview preflight identity selection is gated on the user's hardening commit.
- **Next:** User commits; then Task 7 preflight (`forecast-v1-20260917-<shortsha>-04a`, three byte-equivalent runs) and Task 8 closure/04B rebase.

## Context and Decisions
- `verify_rating_parent` now binds all three parent URIs exactly (new `REQUIRED_RATING_MANIFEST_URI` constant; CLI R6/Repair URIs must equal the rating manifest's pinned `parents` URIs) in addition to every existing signature/state/run-id/candidate/hash check; mirrors the proven 03B verifier pattern.
- `forecast_identity` now requires six parent keys (three URIs + three raw SHA-256s); `identity_sha256` changes shape — expected, no frozen 04 identity exists.
- Reporting seasons (2018, 2019, 2021) are evaluated for both heads with the identical per-season procedure and returned in a separate `HeadComputation.reporting_predictions` frame; they never enter retention gates, bootstrap, model recipes, planned outputs, or row counts. Reporting rows are retained in evidence only.
- Two test-premise corrections during Task 5 (both about training sensitivity, not design): (a) the config-overlap fixture must vary `outer_seasons` because reporting-season exact-equality fires first; (b) perturbing reporting-season outcomes legitimately changes later fits (they are training history), so the exclusion regression asserts selection-population identity and reporting liveness instead of gate-value invariance — the plan-required invariant (requesting reporting evaluation changes nothing) is asserted directly via `plain == with_reporting`.
- `REQUIRED_SELECTION_SEASONS` constant was considered and dropped to keep `validate_config` within the plan's three listed checks.
- `_Progress` is a local runner class mirroring the ratings-runner bounded heartbeat (30 s cap, forced phase events, blocked-keyword filter, stderr only).

## Work Completed
- Task 1: exact-URI binding in `data_first_forecast_v1.py` (+50 lines) and runner pass-through with `parent_uris` evidence.
- Task 2: `selection.reporting_seasons` config; `validate_config` reporting drift/overlap/development checks; `evaluate_heads(reporting_seasons=...)` with separate `reporting_predictions`.
- Task 3: `head_metrics` expanded to `{head, selection: {pooled, by_season, by_completed_game_stage}, reporting: {by_season}}` with `{mae, gaussian_crps, n}` slices; `horizon_populations`; top-level `selection_seasons`/`reporting_seasons`.
- Task 4: bounded stderr `_Progress` wired through parent loading, source streaming (`rating_inputs`, `scoring_events`, `team_states`), offsets, both horizons, selection, and evidence construction; `dry_run_complete` on success; stdout stays pure JSON.
- Task 5: 7 new regressions — URI substitution rejection (signed fixture, `verify_parents` monkeypatched for the acceptance path only), identity parent-key enforcement, config reporting policy, reporting-exclusion invariance, overlap guard, missing-reporting-population loud failure, deterministic complete metrics block.
- Task 6: all gates green (see Validation).

## Files Modified
- `src/cks_picks_cfb/data/data_first_forecast_v1.py` — URI constants/binding, reporting config validation, identity parent keys.
- `src/cks_picks_cfb/forecast/heads.py` — reporting-season evaluation, `HeadComputation.reporting_predictions`.
- `scripts/research/run_data_first_forecasts.py` — URI pass-through, expanded evidence, `_Progress`, horizon loop events.
- `conf/research/data_first_football_v1/forecast_v1.yaml` — `reporting_seasons`.
- `tests/test_data_first_forecasts.py` — 7 new regressions (14 total in file).
- `docs/plans/2026-09-17/03-v5-04a-hardening-preflight-and-04b-rebase.md` — status In Progress.
- `session_logs/2026-09-17/04-v5-04a-hardening-and-preflight.md` — this log.

## Validation
- [x] Focused warning-as-error forecast suite — 14 passed.
- [x] Adjacent rating/possession suites warnings-as-error — 258 passed.
- [x] Full warning-as-error suite — 948 passed, 2 skipped.
- [x] Scoped `ruff format` on changed files; full `ruff check .` clean.
- [x] `contracts/validation.py` and `make contracts-check`.
- [x] Strict MkDocs build.
- [x] CLI `--help` and `py_compile` checks.
- [x] `git diff --check`.

## Amendments and Blockers
- **Amendment 1 (2026-09-17):** First preflight attempt (run 1 of
  `forecast-v1-20260917-367b4a3-04a`, commit `367b4a3`) failed at
  `_feature_frame`: `completed_games` does not exist in the 03
  `possession_team_state` contract. Repair streams `possession_rating_state`
  and sources per-team counts from the retained candidate's offense rows with
  uniqueness validation; `_feature_frame` gained direct unit coverage
  (16 focused tests). Mechanical only — recorded in the plan's Amendments.
  The failed run is a dead diagnostic identity; preflight repeats under a
  fresh run ID after the repair commit. Failed-run stderr (heartbeats through
  `offsets_built` at ~448 s, then the KeyError) is retained in the evidence
  temp directory.

## Handoff Notes
- **Resume at:** User executes the repair commit, then Task 7 restarts with a fresh
  run ID derived from the new commit short SHA, same captured cutoff
  `2026-09-17T14:19:09Z`, three byte-equivalent runs.
- **Watch out for:** No Preview identity before the commit; keep all three runs in one environment; long runtime expected (~8 min parent streaming + head evaluation; stderr heartbeat is the liveness signal); any mismatch/warning/gate failure = failed identity → repair + new commit; 04B rebase lands as Draft.

**tags:** ["v5", "forecasting", "hardening", "preflight", "terra"]
