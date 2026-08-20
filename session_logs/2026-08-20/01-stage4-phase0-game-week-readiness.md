# Session: Stage 4 Planning + Phase 0 Game-Week Readiness

## TL;DR

- **Worked On:** Planned Week 0 launch-contract Stage 4 (gap analysis of what
  remains to publish), then executed Phase 0 de-risking: first-ever production
  readiness pass, production rehearsal publish, on-demand ISR revalidation
  setup, and `.env` hygiene.
- **Outcome:** Production game-week operations are proven end-to-end. Active
  run is now `2026w0-55de0317120d` (fresh Aug-20 lines, 8/8/8, market mode).
  Publishes now refresh the site instantly via signed revalidation.
- **Plan Contract:** `docs/plans/2026-08-18/week0-launch-execution.md`
  (In Progress — Stages 4–5; Amendment 4 records this session)
- **Approval / Status:** User approved the Stage 4 plan and all Phase 0
  decisions on 2026-08-20 (rehearsal now; daily assistant-run publishes;
  skip Pick'em for Week 0; flip evening of Aug 28; configure revalidation).
- **Blockers:** None. `CFBD_PREDICTION_TOKEN` intentionally not needed
  (Pick'em skipped this week).
- **Next:** Daily publish sessions Aug 25–27; Aug 28 final publish → review →
  freeze → predictions flip → smoke test.

## Context and Decisions

- Gap analysis found **nothing hard-blocks publishing**: `publish-week`
  self-refreshes schedule and captures CFBD market lines
  (`consensus_then_median_v1`); `.env` was already production-ready; missing
  lines fail soft. Remaining work was sequencing, approvals, and de-risking.
- Key traps encoded into the game-week plan: `AS_OF` ~5 min ahead of every
  run; `CONFIG=conf/weekly_bets/v4_2026.yaml` explicit (default config fails
  preflight); **no publishes after freeze** (a later publish moves
  `current_week` off the frozen run); freeze requires both line types on all
  8 games (WAIVER only for genuine provider exceptions).
- Pick'em deferred to Week 1 by user decision (token is short-lived anyway).
- Revalidation secret is marked Sensitive in Vercel; `vercel env pull` masks
  it, so the secret lives only in Vercel + local `.env` (rotation requires
  both sides + redeploy).

## Work Completed

1. **Production readiness pass** (first ever; `make readiness` blocks
   `ENV=production` so the ops CLI was used): preflight + contracts +
   model-ready audit — all passed, zero errors.
2. **Rehearsal publish** `2026w0-55de0317120d`: all 8 state-machine steps
   green in ~35s; activated with 8/8 predicted, 8/8 lined; market mode
   unchanged; `/api/health` verified.
3. **On-demand revalidation**: generated 32-byte secret → `REVALIDATION_SECRET`
   (Vercel, production, Sensitive) + `CFB_REVALIDATION_URL`/`REVALIDATION_SECRET`
   (local `.env`) → redeployed production → verified signed call returns
   `{"status":"revalidated","path":"/"}` and forged signature returns 401.
   (Note: first `vercel env pull` attempt failed because Vercel masks
   sensitive values — resolved by rotating via a single atomic command.)
4. **`.env` hygiene**: removed stale `PREVIEW_DATABASE_URL`
   (`ep-delicate-sun`, deleted branch); collapsed 2 duplicate lines.
5. **Docs**: production runbook updated (revalidation live; stale-env note
   resolved); launch contract Amendment 4 appended.

## Files Modified

- `docs/ops/production_runbook.md` — revalidation configured; credential notes
- `docs/plans/2026-08-18/week0-launch-execution.md` — Amendment 4
- `session_logs/2026-08-20/01-stage4-phase0-game-week-readiness.md` — this log
- Local `.env` (not committed) — revalidation vars added; stale entry removed
- Vercel: `REVALIDATION_SECRET` (production) added; production redeployed

## Validation

- [x] Production readiness: preflight/contracts/audit all `passed: true`
- [x] Rehearsal publish: 8/8 steps succeeded; health shows
      `2026w0-55de0317120d`, 8/8/8, market mode
- [x] Revalidation: 200 on valid HMAC, 401 on forged signature
- [x] `.env`: 30 vars; `DATABASE_URL` (production) intact; no stale entries
- [x] `uv run mkdocs build --quiet` after doc edits
- [x] `git diff --check`

## Amendments and Blockers

- Launch contract Amendment 4 appended (see above). No blockers.

## Handoff Notes

- **Resume at:** Tue Aug 25 — daily publish session:
  `AS_OF=$(now+5min)` → `make publish-week YEAR=2026 WEEK=0 AS_OF=...
  ENV=production CONFIG=conf/weekly_bets/v4_2026.yaml` → health check.
  Identical Wed Aug 26, Thu Aug 27.
- **Aug 28 (flip day):** final publish (morning) → generate run review for
  user → user approval → `make freeze-week YEAR=2026 WEEK=0 ENV=production` →
  **no further publishes** → set `CFB_PUBLICATION_MODE=predictions` in Vercel
  → redeploy → smoke test `/` + `/api/health` + lean rendering.
- **Aug 30+:** Stage 5 `close-week`, grades/stats, retrospective, Week 1
  cadence (incl. `CFB_PUBLICATION_WEEKS` expansion decision + Pick'em revisit).
- **Watch out for:** line coverage holding at 8/8 both-types through Aug 28
  (WAIVER path if a provider gap appears); never publish after freeze.

**tags:** ["week0", "stage4", "production", "publish", "revalidation", "launch"]
