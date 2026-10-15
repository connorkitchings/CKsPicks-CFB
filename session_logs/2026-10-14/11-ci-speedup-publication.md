# Session: Publish CI speedup for hosted verification

## TL;DR
- **Worked On:** Publish reviewed CI changes from isolated worktree through dev and a draft PR targeting main.
- **Outcome:** Published dev and draft PR #7; all six hosted CI jobs and Vercel Preview passed. GitGuardian historical disposable-password finding remains.
- **Plan Contract:** docs/plans/2026-10-14/03-ci-speedup.md
- **Approval / Status:** User asked "can you proceed?" after the proposed commit/push/PR steps, authorizing those git operations. Merging to main is not included.
- **Blockers:** External GitGuardian false positive for historical disposable test credential; no main merge.
- **Next:** Resolve GitGuardian false positive before a separate main merge decision.

## Context and Decisions
- Local and remote dev both dde737b1, with no unrelated local changes. No existing open PR.
- origin/main 1fd3afca has identical tracked content to the dev baseline; proposed PR contains only the approved changes.
- Keep prior local validation records as historical checkpoints. Publication is newly authorized in this session.

## Validation
- Remote refs refreshed; git diff --check passes.
- Prior local validation: 3,160 passed/19 skipped, 69% combined coverage, workflow syntax/lint/contracts/registry/docs checks pass.

## Handoff Notes
- **Resume at:** Hosted PR validation; record run URL, tested revision, job durations and private-cluster PostgreSQL result.
- **Watch out for:** dev push alone does not trigger CI; a PR targeting main does. No automatic main merge or production deployment authorized here.

**tags:** ["ci", "release", "github-actions"]

## Publication progress
- Committed reviewed implementation as 8aa6a4f5, fast-forwarded dev and pushed origin/dev.
- Opened draft PR https://github.com/connorkitchings/CKsPicks-CFB/pull/7 targeting main; first CI run https://github.com/connorkitchings/CKsPicks-CFB/actions/runs/38673532372 started lint/web/general/ratings/database concurrently.
- GitGuardian flagged the moved disposable postgres:postgres test URL as Generic Password. Replaced the service password and client URL password with the same github.run_id expression, retaining disposable fixture-only authentication without a hardcoded password literal. Actionlint and YAML expression checks pass; no production secret was exposed or rotated.


## Hosted acceptance
- Final implementation revision: bf53e5a6396b21ade868cbd7309386661a0bb7bc. CI run: https://github.com/connorkitchings/CKsPicks-CFB/actions/runs/38673650571 (success).
- All five independent jobs started together at 02:58:13–14Z; coverage gate completed 03:02:45Z. Execution 4m32s; total run 6m09s with queueing behind cancellation. Baseline cancelled run took 20m24s; its historical suite alone took 16m16s.
- Job durations: general 4m08s, ratings 2m57s, database 1m48s, lint 22s, web 1m55s, final gate 21s.
- General 3,012 passed/19 skipped; ratings 7 passed; database 141 passed/zero skipped. Host initdb/pg_ctl/postgres all report PostgreSQL 16.15. Coverage download/merge/report succeeded at 69%.
- Summed job elapsed time: 11m31s versus baseline 39m00s (includes hung/cancelled work). Timing API billable values are zero, so do not interpret these sums as billed usage/cost.
- Vercel Preview successful. GitGuardian still reports original commit 8aa6a4f5, not the current run-derived password. Finding: https://dashboard.gitguardian.com/workspace/743205/incidents/23000215?occurrence=304248002.
- No merge to main, force-push, security-check bypass or Production deployment performed.
- Contract marked Implemented; final documentation receipt is a separate commit after the tested implementation revision.
