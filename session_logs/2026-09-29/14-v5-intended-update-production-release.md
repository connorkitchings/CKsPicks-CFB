# Session: V5 intended-update production release

## TL;DR
- **Worked On:** Activated the user-approved exact repaired-V5 release packet for 2026 Weeks 0–5.
- **Outcome:** Production serves repaired ratings and predictions; Weeks 0–4 have replacement grades and 2026 season totals of 93–103–3 spread and 82–77–0 total. Week 5 has 56 selected predictions and no grades. The original six selected runs remain the batch rollback.
- **Plan Contract:** [V5 intended-update production repair](../../docs/plans/2026-09-29/v5-intended-update-2026-production-repair.md), Tasks 6–7.
- **Approval / Status:** The user explicitly approved packet SHA-256 `deb1fd34ebd98410eedce6e7ae7088e54da95dd6d36ca6a1d7ac90a595781fcc`. Production data release completed; retrospective UI disclosure awaits deployment from the final user-executed commit. Week 5 final market refresh/freeze remains a pre-kickoff operation.
- **Blockers:** None for the completed-week data release. Do not call the Week 5 p2 quotes current; later provider checks found six changed values across five games.
- **Next:** Commit/push the disclosure and release record together; verify the Vercel deployment and visible retrospective labels. Run the full Week 5 market/freeze checklist before 2026-10-02 00:00Z.

## Context and Decisions
- The approved machine packet was checksummed again before every stage; its bytes were not changed. Vercel had deployed `2a878a43308580425dc07b5b0bb0dfa841e01aa6` and all CI jobs passed before activation.
- The production admin role and 56-game Week 5 population were verified. First kickoff remained 2026-10-02 00:00Z. Read-only selection preflight matched all six original rollback IDs.
- The retrospective disclosure was missing from the live completed-week pages despite correct release data. This session adds a visible label to Week 0–4 game pages and the season performance page. It does not modify forecasting or scoring.

## Work Completed
- Staged 22 production-namespace R2 objects from the signed Preview source, with write-once collision checks and SHA-256 readback. Independently validated all six release authorizations against the staged source chain.
- Registered the model-pair approval and six exact run authorizations on the verified production branch. Projected 1,370 repaired rating snapshots with `cks_prod_pipeline`.
- Published the six authorized prediction runs without changing public selection, then scored Weeks 0–4 from their exact scored artifacts. Pre-selection readback found 271 predictions, 199 spread grades, 159 total grades, and no Week 5 grade; the public selection and old season totals remained unchanged.
- The first atomic selection command failed on `ModuleNotFoundError: scripts` before commit. A read-only check proved all six old runs and old season totals were still selected. Re-running the same packet with `PYTHONPATH=.:src` succeeded. Post-selection readback showed the six approved run IDs, 1,370 ratings, 215 completed-week predictions, 199/159 grades, and new season totals 93–103–3 spread / 82–77–0 total (profit units −18.4537 / −2.4538).
- Public HTTP readback returned 200 for home, ratings, performance, and Week 0. The home page contained `2026w5-v5repair-20260929-p2`; Week 0 contained its repaired run ID; ratings contained source SHA `e80ae3473d88d0c458325c19343e7dae6447924d9abad29b15089bc19cacd26b`; home and performance showed the new season records.

## Files Modified
- `web/src/app/page.tsx`, `web/src/app/performance/page.tsx` — disclose retrospective replacement on completed-week pages and season record.
- `docs/plans/2026-09-29/v5-intended-update-production-release-packet.md` — approval, execution, and readback evidence.
- `docs/plans/2026-09-29/v5-intended-update-2026-production-repair.md` — actual production release status and remaining gates.
- `docs/ops/v5_weekly_operator.md`, `docs/ops/weekly_pipeline.md`, `docs/modeling/v5_status.md` — current selected lineage, rollback, and Week 5 operator handoff.
- This session log.

## Validation
- [x] Exact JSON packet SHA-256 unchanged; signed source chain, six authorizations, and 22 staged R2 objects verified.
- [x] Production admin and restricted pipeline roles; current selection preflight; all six staged runs; five scored runs; atomic selection; post-selection ratings, grades, stats, and Week 5 no-grade readback.
- [x] Live home, ratings, performance, and Week 0 HTTP/data checks.
- [x] `npm run lint`, `npm run typecheck`, `npm run build` in `web/`.
- [x] `npm run test:publication` (38 passed) and `npm run test:ui` (8 passed; the sandbox first blocked the local server bind, then the scoped rerun passed with network permission).
- [x] `.venv/bin/mkdocs build --quiet`; `git diff --check`.
- [ ] New retrospective disclosure visible on deployed Vercel site after final commit/push.
- [ ] Final Week 5 market refresh and freeze before first kickoff.

## Amendments and Blockers
- The exact packet, model, game population, and score policy did not change. The selector's first import-path failure made no committed public change; retry used the same sealed packet.
- The selected Week 5 p2 run is published and ungraded. A later market check found moved quote values, so a final market reconciliation remains required before freeze.

## Handoff Notes
- **Resume at:** User commits/pushes this one post-release documentation and disclosure set; inspect the new Vercel deployment and verify a visible retrospective notice on `/?week=0` and `/performance`. Then complete Week 5 market/freeze operations under the weekly checklist.
- **Watch out for:** Do not rescore Week 5 before certified finals or silently replace the selected p2 run. Any new candidate needs its own exact release authorization. The six original run IDs in the packet remain the batch rollback.

**tags:** ["v5", "ratings", "production", "release", "weekly-ops"]
