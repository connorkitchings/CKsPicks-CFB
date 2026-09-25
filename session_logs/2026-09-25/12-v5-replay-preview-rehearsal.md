# Session: V5 replay Preview history and serving rehearsal (Task 3)

## TL;DR

- **Worked On:** Converted verified replays into per-week Preview serving artifacts, published/scored/selected Weeks 1–4 on Preview, staged frozen W4 quotes, rehearsed the V4 rollback, and added truthful replay labeling to the site.
- **Outcome:** Preview shows V5 replay for Weeks 0–4 (W0–3 scored, W4 published 58/58); V4 Week 4 rollback proven and V5 restored; page data layer verified against Preview (215 replay games, live 0/null).
- **Plan Contract:** `docs/plans/2026-09-25/02-v5-week4-replay-site-cutover.md` (Approved), Task 3.
- **Approval / Status:** Approved plan + Amendment 1. All operations Preview-only with the restricted preview pipeline role; no production writes.
- **Blockers:** None. W4 scoring awaits certified finals (timing).
- **Next:** Commit, then Task 4 (production release packet for the separate approval decision).

## Context and Decisions

- Serving runs use stable IDs (`2026w{W}-v5replay-w0w3`, `2026w4-v5replay-w4`) and actual UTC `as_of` timestamps (late-publication honesty). Converter re-verifies each frozen manifest before slicing.
- A first W1 upload landed in the `artifacts/production/` namespace because `CFB_ARTIFACT_ENV` defaults to production; caught by URI review, removed (audited SHAs below), and re-uploaded under `artifacts/preview/`. All serving operations now set the namespace explicitly.
- Direct `publish_to_db.py` on Preview uses the migrator URL by default, which the dual-role guard correctly rejects for V5 writes; V5 Preview publishes run with `DATABASE_URL` pointed at the pipeline URL inside the wrapper (documented pattern for direct publisher invocation).
- W1–3 scoring = outcomes only (W0 precedent: 0 grade rows); W4 market grades vs frozen quotes happen at score time after finals certify (quotes staged now).
- The web app already had evidence-aware queries and a replay/live performance split; added only the plain-language replay notice and badge tooltip.

## Work Completed

- Fixed the W4-aware replay→serving dispatch (`generate_v5_replay_weekly_bets.py` + 3-tuple callers) with 5 focused tests; serving config `v5_replay_w4_2026.yaml`.
- Uploaded 4 Preview serving artifacts (43/49/57/58 rows; code SHA = committed HEAD; correct replay parents) and published them to Preview Neon (backfill mode, current_week untouched).
- Scored W1–3 on Preview from the certified Silver outcomes (`669856aa…`: 43/49/57 finals) via `publish_scored_run`; runs are `scored`.
- Selected W1–4 on Preview with explicit retrospective reasons; W0–3 scored, W4 published.
- Backfilled the exact frozen V4 W4 quotes (Silver `48466f45…`, captured 2026-09-20 18:42 UTC — all 58 pre-kickoff, zero nulls) into Preview `market_quotes` via an explicit content-bound ref; verified 58/58 pre-kickoff in DB.
- V4 rollback rehearsal: published the frozen V4 W4 run to Preview (byte-identical manifest pointer copy, predictions referenced at production URIs), selected V4 (view = 58 V4 picks, history recorded), restored V5 as a separately recorded action.
- Web: replay notice on week pages + evidence badge tooltips; lint, typecheck, unit tests (8/8), production build all pass.
- Verified the page data layer against Preview: all weeks V5/replay with full counts; performance split replay=215 games, live=0/null.

## Files Modified

- `scripts/pipeline/generate_v5_replay_weekly_bets.py`, `scripts/pipeline/publish_to_db.py`, `scripts/pipeline/preflight.py` - W4 dispatch + tuple update (committed in `32759c3`).
- `conf/weekly_bets/v5_replay_w4_2026.yaml` - W4 replay serving config (committed).
- `tests/test_v5_replay_serving.py` - converter dispatch tests (committed).
- `web/src/app/page.tsx`, `web/src/components/Header.tsx` - replay notice + badge tooltips.
- Preview R2 (working + immutable rehearsal objects) and Preview Neon (runs, predictions, finals, quotes, selections) as detailed above.

## Validation

- [x] Dry runs before every upload (43/49/57/58 match canonical populations).
- [x] Neon readback: runs, predictions, finals, quotes, selections, rollback history.
- [x] Page-layer render check vs Preview (all weeks + performance split).
- [x] Web lint, typecheck, unit tests, production build.
- [x] `git diff --check`; strict MkDocs unaffected by web-only edits (rerun at commit).

## Amendments and Blockers

Staging cleanup from the namespace near-miss (unreferenced, minutes old):
- `artifacts/production/predictions/year=2026/week=1/run_id=2026w1-v5replay-w0w3/{manifest.json, predictions.csv, point_in_time_features.csv}` — predictions sha `7842f7d9…` (re-uploaded byte-identical under `artifacts/preview/`).

## Handoff Notes

- **Resume at:** Commit web edits + this log, then Task 4 — read-only exact packet validator replay mode, per-week byte-bound packets (W0–4), presentation for the separate production approval decision. No authorizations or production selection before that decision.
- **Watch out for:** W4 scoring (outcomes + frozen-quote grades) runs only after all 58 finals certify. The Week 5 live path keeps priority at the finals gate (~Sun/Mon). Keep 0014/0015 byte-identical.

**Suggested commit message:** `Rehearse V5 replay history on Preview with rollback proof`

**tags:** ["v5", "replay", "preview", "serving", "rollback"]
