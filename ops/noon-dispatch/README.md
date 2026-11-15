# noon-dispatch

A Cloudflare Worker that starts the `weekly-season-update.yml` workflow at 12:00 America/New_York on Sundays and Mondays. GitHub Actions `schedule` runs for that workflow arrive hours late or are dropped, so this worker calls the `workflow_dispatch` REST API on time instead.

It dispatches against `ref: "main"` with `mode` sent explicitly: Sunday sends `close-week`, Monday sends `market-refresh` (the controller itself turns Monday into a catch-up close when the week was never rolled over). It never sends `force`, `skip_production` or `accept_cutoff_correction`.

Two UTC crons (`0 16 * * 0,1` and `0 17 * * 0,1`) cover daylight and standard time. The handler checks the Eastern wall clock and calls GitHub only when it is 12:xx ET on Sunday or Monday; the other cron firing returns without a request. The worker has no HTTP surface (`workers_dev = false`, `fetch` returns 404).

Before every dispatch the worker reads the repository variable `CFB_WEEKLY_AUTOMATION_ENABLED` and skips unless its value is exactly `true`. A missing variable (404), any other value, a failed read, or a network error all skip and log the reason; the read is never retried. This keeps the owner kill switch effective for worker dispatches, not only for GitHub `schedule` runs.

The workflow file's GitHub cron slots stay in place as backup. The controller is idempotent, so a duplicate run after a successful close skips.

## Owner setup

1. Create a fine-grained personal access token at https://github.com/settings/personal-access-tokens/new, restricted to the single repository `connorkitchings/CKsPicks-CFB`, with only the repository permissions "Actions: Read and write" and "Variables: Read" (Metadata: Read is added automatically). Set an expiry (for example 90 days) and add a calendar reminder to renew it before then.
2. From `ops/noon-dispatch`, run `npm install`.
3. Run `npx wrangler login` and approve the Cloudflare login in the browser.
4. Run `npx wrangler secret put GITHUB_TOKEN` and paste the token when prompted.
5. Run `npx wrangler deploy`.
6. In the Cloudflare dashboard, open Workers & Pages, then `noon-dispatch`, then Settings, then Triggers, and confirm both cron triggers are listed.
7. To exercise the handler locally, run `npx wrangler dev --test-scheduled`, then request `curl "http://localhost:8787/cdn-cgi/local/scheduled?cron=0+16+*+*+0,1"` (the form shown in the Cloudflare Cron Triggers docs, with spaces written as `+`; add `&time=<epoch ms>` to simulate a specific fire time; `/__scheduled` is the older name for the same route). The docs do not mention commas, and an unencoded comma is valid in a query string. Locally the variable read needs a real `GITHUB_TOKEN` (for example in `.dev.vars`), otherwise the run skips with a logged reason. Outside noon Eastern on Sunday or Monday it logs a skip and calls nothing. The real check is the next Sunday or Monday noon: confirm a `workflow_dispatch` run appears in the repository's Actions tab, and read the worker's logs in the dashboard if it does not.
8. To disable, delete the cron triggers in the dashboard (Settings, Triggers) or run `npx wrangler delete`.

## Token renewal

When the token expires, create a new one as in step 1, then repeat step 4. No redeploy is needed. An expired token makes the scheduled run fail with a 401 in the Cloudflare logs.

## Tests

`npm test` runs `node --experimental-strip-types --test src/index.test.ts`. It needs no installed dependencies.
