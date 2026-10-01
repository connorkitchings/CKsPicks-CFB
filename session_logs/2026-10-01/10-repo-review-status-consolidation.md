# Session: First-time repo review, status-doc consolidation, boundary plan, matchup leak fix

## TL;DR
- **Worked On:** Start-session context load and a comprehensive read-only repo review (Python pipeline, web/contracts/ops/CI, docs vs goals); then, per user decisions, (A) consolidated status docs, (B) drafted the production-boundary refactor contract, (C) closed the matchup-page publication leak.
- **Outcome:** New single status source `docs/status.md`; stale run IDs/V4-as-production wording removed from entry docs; success metric set to prospective ATS win % vs 52.4%; refactor contract drafted; `/matchup/[gameId]` now follows the selected-run / publication-mode boundary.
- **Plan Contract:** `docs/plans/2026-10-01/04-production-boundary-refactor.md` (Draft, written only); A and C were fast-path.
- **Approval / Status:** Plan approved by user in-session (order A → B → C); contract 04 awaits user approval before Terra.
- **Blockers:** None. No `.env` in this container, so no R2/Neon access; all work was code/docs only.
- **Next:** User reviews contract 04; Week 5 closes after certified finals + 24 h; triage stale In Progress contracts (list below).

## Review findings (summary)
- Deliverable met (public site, every FBS game); no defined predictive success metric existed. Decided 2026-10-01: prospective ATS win % vs 52.4%.
- Retrospective replay W0–4: spread 93-103-3 (47.4%), total 82-77 (51.6%); neither clears break-even. Week 5 (frozen) is the first live slate.
- High: matchup page bypassed publication gate (fixed); production V5 stages run from `scripts/research/` and `src` imports `scripts` (contract 04); V5 release/selection scripts sit outside the ops state machine (follow-up).
- Medium/low (not done): version sprawl, god-modules (`ops/__main__.py`, `publish_to_db.py`), dead modules, no schema.sql-vs-migrations CI check, no mkdocs CI job, `/api/health` ungated, default `GRANT SELECT TO cks_web`, `sys.path` hacks, `./data` fallbacks.

## Work Completed
- A: added `docs/status.md` (+ mkdocs nav, start/end-session skills point to it); replaced run-ID status blocks in AGENTS, README, QUICKSTART, CONTEXT, docs/index, production_runbook, plans/index; fixed migrations (0002–0018), test count (1543/3), log naming; replaced "V4 is production" in roadmap, betting_policy, repository_boundaries, web/README; added success metric to evaluation.md and betting_policy.md; corrected contract statuses (repair → Implemented, V6 → Closed, Phase 5 → Implemented) and added 2026-10-01 rows to the plans index; noted Week 5 freeze in v5_status and the operator doc.
- B: wrote `docs/plans/2026-10-01/04-production-boundary-refactor.md` (phased, behavior-preserving, golden-hash gated).
- C: `web/src/lib/matchup.ts` now resolves model fields via `getGamesForWeek`/`getMarketGamesForWeek` through new pure `matchup-visibility.ts` (market mode or unselected week → market only); unpublished season/week → 404; missing ratings render "—" not 0; `MatchupHero` hides Model rows in market mode. Added `matchup-visibility.test.ts` (4 tests) to `test:publication`.

## Files Modified
- Docs: `docs/status.md` (new), `docs/index.md`, `docs/modeling/{evaluation,betting_policy,v5_status}.md`, `docs/ops/{production_runbook,v5_weekly_operator}.md`, `docs/planning/roadmap.md`, `docs/architecture/repository_boundaries.md`, `docs/plans/index.md`, two V6 contract status lines, `docs/plans/2026-10-01/04-production-boundary-refactor.md` (new), `mkdocs.yml`, `AGENTS.md`, `README.md`, `.codex/QUICKSTART.md`, `.agent/CONTEXT.md`, `.agent/skills/{start,end}-session/SKILL.md`, `web/README.md`.
- Web: `web/src/lib/matchup.ts`, `web/src/lib/matchup-visibility.ts` (new), `web/src/lib/matchup-visibility.test.ts` (new), `web/src/components/matchup/MatchupHero.tsx`, `web/package.json` (test script).

## Validation
- [x] `cd web && npm run test:publication` (49/49)
- [x] `cd web && npm run typecheck`, `npm run lint`, `CFB_UI_TEST_MODE=1 npm run build`
- [x] `uv run python contracts/validation.py`; `uv run mkdocs build --quiet` (no errors). Note: `--strict` already fails on 6 pre-existing relative-link warnings in untouched pages (v5_status, plans/index, research audit).
- [x] `git diff --check`
- [ ] Not run: pytest/ruff (no Python changed); live-site check of `/matchup/<id>` (no DB access here).

## Stale In Progress contracts for user triage (not changed)
`2026-08-18/week0-launch-execution`, `2026-08-21/week0-launch-week1-continuity`, `2026-08-23/modernization-*`, `2026-08-31/week1-operations`, `2026-09-03/market-line-retention`, `2026-09-22/04-v5-authority-simplification-and-site-cutover`, `2026-09-23/01-v5-product-transformation`, `2026-09-27/03-archive-unique-local-artifacts`. Duplicate `02-` files exist in `2026-10-01/`; `2026-09-30/` skips `04`.

## Handoff Notes
- **Resume at:** approve or amend contract 04; separately consider follow-ups (V5 release scripts under `ops`, dead-code prune, CI schema-equivalence + mkdocs job, gate `/api/health`).
- **Watch out for:** `docs/status.md` must be the only place naming live runs; update it at every open/freeze/close. Orphaned matchup components were intentionally left for plan 10-01/02.

**tags:** ["review", "docs", "status", "web", "publication", "plan"]
