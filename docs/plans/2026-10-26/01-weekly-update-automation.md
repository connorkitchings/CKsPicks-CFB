# Unattended weekly season update (GitHub Actions)

- **Status:** Implemented (locally; awaiting owner commit, release to `main` and rehearsal)
- **Created:** 2026-10-26
- **Planner:** Sol
- **Approval source:** Owner decisions in session on 2026-10-26, recorded in the [decision log](../../decisions/decision_log.md).
- **Implementation log:** `session_logs/2026-10-26/01-weekly-update-automation.md`
- **Commit policy:** Git operations remain user-controlled. Proposed commits: scripts and tests, workflow, documentation.

## Goal and acceptance

Run the weekly cadence of the [weekly runbook](../../ops/weekly_runbook.md) without an operator: Sunday 12:00 ET close the completed week and open the next, Monday 12:00 ET refresh the active week's lines when coverage is incomplete, and activate Production automatically when every gate passes. The incremental close-week path of [2026-10-25/01](../2026-10-25/01-incremental-close-week-rollover.md) is the base.

**Definition of done:**

1. `.github/workflows/weekly-season-update.yml` runs on `schedule` (`7 17 * * 0` and `7 17 * * 1`) and `workflow_dispatch` (`mode`: `close-week`, `market-refresh`, `plan-only`; `force`; `skip_production`), gated on the repository variable `CFB_WEEKLY_AUTOMATION_ENABLED == 'true'`.
2. `scripts/ops/weekly_automation.py` runs capture, build, exceptions refresh, commit and push to `dev`, prepare, parity check, Preview release, Production release and the live health probe, in one job, printing only IDs, hashes and counts.
3. Any failed gate stops the run before the next step. A stop never activates anything and never rolls back.
4. The runbook, `AGENTS.md`, `docs/status.md` and the decision log describe the automation, the owner-only rollback and the merge-commit release path.

## Owner decisions (2026-10-26)

- Production activation is fully automatic when every gate passes. This replaces "Production activation is an owner decision"; rollback remains owner-only.
- Score-reconciliation exceptions are added automatically only when the final score equals the sum of the quarter line scores; otherwise the run stops.
- Sunday 12:00 ET close-week and Monday 12:00 ET market-only line refresh. The cron is `17:07 UTC` (13:07 ET in daylight time, 12:07 ET in standard time); GitHub schedules start late, so every step computes cutoffs at run time.
- Notifications come from GitHub only.

## Constraints

- **One job.** `run-manifest.json` stores absolute candidate paths and release re-hashes candidate files from local disk, so prepare, Preview release and Production release share one checkout.
- **Clean tree, one commit.** Prepare needs a clean tree and release needs `HEAD` equal to the prepared commit. The job commits the manifest and exceptions file, pushes to `dev`, then prepares and releases with no further commit. Pushes with `GITHUB_TOKEN` do not trigger `ci.yml`, so the workflow carries its own gates.
- **`--as-of`** cannot be in the future and must be earlier than the first kickoff of the upcoming week.
- **Public repository.** Logs and artifacts carry only IDs, hashes and counts; the uploaded receipt artifact holds small reports, the run manifest and a summary JSON.
- **No Docker, no Keychain.** Credentials come from the job environment; the controller builds an explicit environment for each subprocess, mirroring `scripts/ops/with_preview_env.sh` and `scripts/ops/with_production_pipeline_env.sh`. The Production URL appears only in the Production release step.
- **Scheduled workflows run only from the default branch.** The workflow must reach `main`, and `main` no longer fast-forwards from `dev` since the squash merge of PR #9, so release `dev` to `main` through a pull request merged with a merge commit.
- **Environment.** Production credentials live in the GitHub environment `season-production` (deployment branches `main` and `dev`).

## Ordered changes

### 1. Score-exception refresh

- **Components:** `scripts/pipeline/refresh_score_exceptions.py`, `tests/test_refresh_score_exceptions.py`.
- **Change:** for each score mismatch in the completed week, verify that the final equals the sum of the quarter line scores; add templated entries to `conf/season/2026/score_reconciliation_exceptions.json` and re-pin its SHA-256 in the manifest. Exit nonzero, writing nothing, when any mismatch fails the check, an earlier-week exception changes or becomes unused, or a new mismatch lies outside the completed week.
- **Acceptance:** tests cover a verified add, an unverified stop and an earlier-week change.

### 2. Release parity check

- **Components:** `scripts/pipeline/check_release_parity.py`, `tests/test_check_release_parity.py`.
- **Change:** compare the candidate with the active Preview release read-only. Close-week: completed-week predictions, variances, grades and earlier rating snapshots identical within 1e-9, only identity columns differ. Market-refresh: ratings, predictions, features and all grades identical, only the upcoming week's line, edge, lean and pending-pick columns differ. Require 100% predicted for the upcoming week; report line coverage without blocking.
- **Acceptance:** tests cover identical, a changed completed-week prediction (fails) and a changed market column (passes only in market-refresh mode).

### 3. Completed-week cutoff check in the revision builder

- **Components:** `scripts/pipeline/build_season_revision.py`, its tests.
- **Change:** refuse a new manifest whose completed-week `pre_week_cutoffs` or `post_week_cutoffs` differ from the previous certified manifest. This would have caught the stale Week 8 cutoff (18:00:00Z against the certified 14:39:00Z) in the Week 9 manifests; the Week 10 build corrects it and the Week 9 manifests are not edited.
- **Acceptance:** a test builds with a differing completed-week cutoff and expects the refusal.

### 4. Controller and workflow

- **Components:** `scripts/ops/weekly_automation.py`, `.github/workflows/weekly-season-update.yml`, `tests/test_weekly_automation.py`.
- **Change:** week detection from the active Production release (Sunday: next week is active plus one; Monday: refresh the active week); stop when the first kickoff of the upcoming week has passed, when past the final regular week or when a completed-week game lacks a final. Idempotent resume when `revision_manifest_w<NEXT>_v1.json` already exists on `dev`. Close-week: capture CFBD lines for the completed and upcoming week, Odds API quotes for the upcoming week, cutoffs computed at run time, incremental build, exceptions refresh, commit and push, wait for the pre-week cutoff, prepare, parity, Preview release with the previous release ID read from the database, Production release unless `skip_production`, health probe. Market-refresh: only when the active release has less than full line coverage (or `force`), capture the active week, `build_market_revision` to the next version, stop when coverage did not improve, then the same tail. `plan-only` detects the week, checks secrets and read-only database roles and computes cutoffs, with no provider call and no write.
- **Acceptance:** tests cover week and cutoff selection (kickoff passed, final week, missing final), idempotent resume, and environment isolation (the Production URL only in the Production release environment).

### 5. Documentation

- **Components:** `docs/ops/weekly_runbook.md`, `AGENTS.md`, `docs/status.md`, `docs/decisions/decision_log.md`, `docs/plans/index.md`, `.codex/QUICKSTART.md`, the `Makefile` help text, this contract and the session log.
- **Change:** the runbook gains an "Automated weekly update" section (schedule, gates, disable, rerun, rollback, owner setup); stale statements are corrected (32 checks for `resume_v1`, Week 9 Production state, `season-close-week` as the weekly command, merge-commit release path); `docs/status.md` records the stale Week 8 cutoff and the open items.
- **Acceptance:** `uv run mkdocs build --strict` passes.

## Owner one-time setup

1. Create the GitHub environment `season-production` with deployment branch policy selected branches `main` and `dev`.
2. Add `PRODUCTION_PIPELINE_DATABASE_URL` and `THE_ODDS_API_KEY` as secrets of that environment (commands in the runbook).
3. Release `dev` to `main` with a merge commit so the schedule is active.
4. Run the workflow with `mode=plan-only`, then `mode=close-week` with `skip_production=true`.
5. Set `CFB_WEEKLY_AUTOMATION_ENABLED=true` only after the rehearsal passes.

## Validation

- `PYTHONPATH=src:. uv run pytest tests/test_refresh_score_exceptions.py tests/test_check_release_parity.py tests/test_weekly_automation.py -q`, the builder test for the cutoff check, `make lint`, and `uv run mkdocs build --strict`.
- The rehearsal run (`skip_production=true`) is the end-to-end proof before enabling the schedule.

## Risks

- A bug in a gate could activate a wrong Production release without a human. Mitigations: parity and verification gates precede Preview, Preview proof precedes Production, the Production credential is scoped to one environment, and the owner-only rollback is documented and unchanged. The rollback drill has never been run; run it before relying on the automation.
- A late scheduled start can leave too little time before the first kickoff; the controller recomputes cutoffs and stops when the kickoff has passed.
- Cold-start repository state: the workflow pushes to `dev`; a concurrent manual push can make the push fail, which stops the run before prepare.

## Handoff/amendments

- **Approval and resume gate:** owner decisions of 2026-10-26; no Production write occurs until the owner enables the variable.
- **Precise next action:** owner completes the one-time setup, releases `dev` to `main` and runs the rehearsal.
- **Amendments:** none.
