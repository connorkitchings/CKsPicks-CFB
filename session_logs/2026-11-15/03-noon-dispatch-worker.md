# Session: Noon Eastern dispatch Worker for the weekly season update

## TL;DR

- **Worked On:** A Cloudflare Worker that calls the GitHub `workflow_dispatch` API at 12:00 America/New_York on Sundays and Mondays, because GitHub `schedule` runs for `weekly-season-update.yml` arrive hours late.
- **Outcome:** The Worker, its unit tests and a runbook subsection are committed on `dev` (local only, not pushed). The owner deployed it on 2026-11-15 after fixing the cron day numbering. Nothing under `.github/` changed, so no `dev` to `main` release is needed.
- **Plan Contract:** `N/A (fast path)`
- **Approval / Status:** Owner chose the Worker approach and decided that the Worker must honor `CFB_WEEKLY_AUTOMATION_ENABLED`.
- **Blockers:** None for the code. Deployment needs the owner's Cloudflare login and a GitHub token (steps below).
- **Next:** Owner deploys the Worker, then checks the next Sunday's run.

**tags:** ["ops", "automation", "cloudflare-worker", "weekly-update"]

## Context and Decisions

Delay evidence: the workflow's cron slots are Sunday and Monday `07 17` UTC (primary) and `37 22` UTC (backup). Runs started as follows (GitHub run `createdAt`, UTC; the slot each run belongs to is inferred as the nearest earlier slot).

| Run | Event | Started (UTC) | Slot | Late by |
|---|---|---|---|---|
| 40405402764 | schedule | 2026-10-26 21:33 | Mon 17:07 | about 4h 26m |
| 41350368740 | schedule | 2026-11-01 21:07 | Sun 17:07 | about 4h 00m |
| 41548481208 | schedule | 2026-11-02 23:50 | Mon 22:37 backup | about 1h 13m (the 17:07 slot never fired) |
| 42523428823 | schedule | 2026-11-08 21:05 | Sun 17:07 | about 3h 58m |
| 42548224689 | schedule | 2026-11-09 01:57 | Sun 22:37 backup | about 3h 20m |
| 42729877957 | schedule | 2026-11-10 00:38 | Mon 17:07 | about 7h 31m |
| 42754989556 | schedule | 2026-11-10 04:18 | Mon 22:37 backup | about 5h 41m |

- **Design:** Cloudflare Cron Triggers (Cloudflare numbers weekdays 1 to 7 with 1 as Sunday, so a standard `0,1` is rejected; the crons use `SUN,MON`) `0 16 * * SUN,MON` and `0 17 * * SUN,MON` (UTC) cover daylight and standard time. The handler computes the `America/New_York` wall clock and dispatches only at hour 12: Sunday sends `mode=close-week`, Monday sends `mode=market-refresh`. `mode` must be sent explicitly because the workflow derives it from the cron string only for `schedule` events. The request targets `ref: "main"` and sends only `mode` (never `force`, `skip_production` or `accept_cutoff_correction`). Only a 204 counts as success; a 5xx is retried once; any other status throws with the status and a truncated body. The token is the `GITHUB_TOKEN` Worker secret. `workers_dev = false`, and `fetch` returns 404.
- **Kill-switch decision:** The variable `CFB_WEEKLY_AUTOMATION_ENABLED` gates only `schedule` events in the workflow, so Worker dispatches would have bypassed it, including Production activation. Owner decision: the Worker reads the variable first and dispatches only when it is exactly `true`. A 404, any other value, a failed read or a thrown error skips and logs the reason. A manual dispatch from the Actions page still bypasses the variable, as before.
- The GitHub cron slots stay as backup. The controller is idempotent, so a late duplicate skips as "already rolled over".

## Work Completed

- Built `ops/noon-dispatch` (Worker, tests, `wrangler.toml`, `README.md`), with `wrangler` pinned to 4.155.0 and not needed to run the tests.
- Added the "Noon Eastern dispatcher" subsection to `docs/ops/weekly_runbook.md`.
- Added the Worker tests to the `check` target in the `Makefile`.

## Files Modified

- `ops/noon-dispatch/` — new Worker package.
- `docs/ops/weekly_runbook.md` — dispatcher subsection.
- `Makefile` — `check` runs the Worker tests.
- `docs/status.md` — release-state sentence and last-updated line.

## Validation

- [x] `node --experimental-strip-types --test src/index.test.ts` in `ops/noon-dispatch`: 14 pass, 0 fail (EDT and EST noon, off-hour null, Tuesday null, 204, 403, 500 then 204, persistent 500, kill switch true, false, 404, read 500, thrown read).
- [x] `make check` passed `ruff`, `pytest` and `mkdocs build --strict`. It stopped at `npm --prefix web run lint` (`eslint: command not found`) because this worktree has no `web/node_modules`. The Worker test line, added last in `check`, was run directly instead.
- [x] `git diff --check dev` clean.
- [ ] `tsc --noEmit` not run (no install).
- [ ] Not exercised against the real GitHub API or a deployed Worker. The `wrangler dev --test-scheduled` URL form comes from the Cloudflare Cron Triggers docs; the comma in the cron value and the `--test-scheduled` flag page were not confirmed.
- [ ] `make web-e2e` skipped: nothing under `web/` changed.

## Amendments and Blockers

- None.

## Handoff Notes

- **Resume at:** Owner deployment steps.
  1. Create a fine-grained token for `CKsPicks-CFB` only, with Actions: Read and write plus Variables: Read, and an expiry. Put the renewal on the calendar.
  2. `cd ops/noon-dispatch && npm install`
  3. `npx wrangler login`
  4. `npx wrangler secret put GITHUB_TOKEN`
  5. `npx wrangler deploy`
  6. In the Cloudflare dashboard, confirm both cron triggers are listed.
  7. Next Sunday after 12:05 ET, run `gh run list --workflow weekly-season-update.yml --event workflow_dispatch --limit 1` and expect a run that started at about 12:00 ET.
- **Watch out for:** `CFB_WEEKLY_AUTOMATION_ENABLED` must be `true` for the Worker to dispatch. `dev` is local only and has not been pushed.
