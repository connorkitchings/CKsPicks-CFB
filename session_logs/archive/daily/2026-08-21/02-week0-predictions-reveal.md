# Session: Week 0 public predictions reveal

## TL;DR

- **Worked On:** Executed the approved Week 0 predictions reveal and manual
  snapshot policy.
- **Outcome:** Production now serves the reviewed active run in `predictions`
  mode. The first public timing snapshot is immutable and recorded below.
- **Plan Contract:** `docs/plans/2026-08-21/week0-predictions-reveal.md`
- **Approval / Status:** User explicitly approved implementation on 2026-08-21;
  contract implemented.
- **Blockers:** None. Final Week 0 freeze remains a pre-kickoff operation.
- **Next:** Manually publish as desired before kickoff; record every successful
  run, then review/freeze the final one and make no subsequent publishes.

## First Public Snapshot

| Field | Value |
| --- | --- |
| Run ID | `2026w0-55de0317120d` |
| State | `published` |
| Prediction checksum | `47dbbd55b62172d0c8cd52162c0070774afcf5ca829223b166298fb767398dc8` |
| Market capture | `2026-08-20T13:17:39.046195Z` |
| Cutoff (`dataAsOf`) | `2026-08-20T13:19:14.000Z` |
| Coverage | 8 expected / 8 predicted / 8 lined |
| Validation | Eight finite prediction/line/edge/lean rows; zero high-confidence rows |

## Work Completed

- Queried the production control plane read-only and verified the active run,
  artifact, coverage, finite values, market captures, and high-confidence
  count.
- Changed Vercel production `CFB_PUBLICATION_MODE` to `predictions` while
  retaining the current 2026/Week 0 scope.
- Deployed production successfully: `dpl_3knBcQJMQSt3fQCBgKLqQJowySfw`.
- Verified deployment readiness, primary-domain alias, health mode/run/coverage,
  and rendered homepage prediction cards, numeric edges, accuracy panel, and
  display-only framing.
- Updated the production runbook, weekly pipeline guide, and active launch
  contract with the manual-only snapshot policy and unchanged final-freeze
  boundary.

## Validation

- [x] Vercel deployment inspect: Ready, production alias attached.
- [x] `GET /api/health`: `mode=predictions`, run
  `2026w0-55de0317120d`, coverage 8/8/8.
- [x] Rendered homepage response contains the reviewed model/market cards and
  numeric edge context.
- [x] `npm run test:publication`, `npm run lint`, and `npm run typecheck`
  (from `web/`).
- [x] `uv run mkdocs build --quiet`.
- [x] `git diff --check`.

## Handoff Notes

- **Resume at:** Before each desired observation, run
  `make publish-week YEAR=2026 WEEK=0 AS_OF=<now-plus-five-minutes> ENV=production CONFIG=conf/weekly_bets/v4_2026.yaml`, then record the health/run data.
- **Watch out for:** The website advances to the latest publish. Immutable R2
  artifacts retain old lines, but manual-only capture cannot establish a
  continuous best-time-to-bet timeline. Freeze the final reviewed run before
  kickoff and do not publish afterward.

**tags:** ["week0", "production", "predictions", "vercel", "market-snapshots"]
