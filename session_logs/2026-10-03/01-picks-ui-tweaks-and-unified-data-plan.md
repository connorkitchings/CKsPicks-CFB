# Session: Picks UI record tweaks and the unified data-fix plan

## TL;DR
- **Worked On:** (1) Picks-page record display tweaks; (2) a single unified contract for all three open data plans.
- **Outcome:** Web: record cells now show `W–L–P` with a superscript-style win % (pushes already excluded from the denominator), no "X decided" label, no "· 52.4% target"; Best bets season line is now `2026: 29–21–0 (58.0%)`. Docs: plan `docs/plans/2026-10-03/01-unified-data-fix-and-matchup-rollout.md` created (Approved, writes gated on decisions D1–D6); plan 05 Superseded; plans 01/03 re-pointed; index, known_issues, status updated.
- **Plan Contract:** `docs/plans/2026-10-03/01-unified-data-fix-and-matchup-rollout.md` (docs only; no implementation run this session)
- **Approval / Status:** User accepted the unified single-batch recommendation in-session ("only do it once" for production). UI changes were user-directed fast path on `dev`.
- **Blockers:** None. R2 credentials are not loaded in the current shell; Phase 1 of the unified plan needs them before any read-only data work.
- **Next:** Run unified-plan Phase 1 (read-only investigation: score-stream audit, V5 impact check, drive-metric hand-check, zero-PPA audit), then the D1–D6 decisions with the user.

## Context and Decisions
- Win-% display iterated through three treatments (same-size/lighter weight → badge → superscript); user selected the superscript style (`relative -top-1 text-[11px]` inside the mono record line, green above 52.4% break-even).
- Pushes were confirmed already excluded from the win-% denominator (`winRatePct` divides by win+loss only) — no logic change needed.
- `TopLeans` now takes a `season` prop from `SlateView` so the label is `{season}: W–L–P (X.X%)` instead of "Best bets: … this season".
- Unified plan working assumptions (user-accepted): D3 Silver rebuild = now, D4 V5 rebuild = later unless Phase 1 shows V5 inputs affected, D5 2025 backfill = deferred, D6 matchup flag = open after verification. All still formal decisions in Phase 2.

## Work Completed
- `RecordCell` (ModelRecord.tsx): record + win % on one line (superscript style), removed the "X decided" subline; header no longer says "· 52.4% target".
- `TopLeans.tsx`: new season-prefixed label; `SlateView.tsx` passes `season`.
- `web/e2e/publication.spec.ts`: updated the Best bets assertion to `/2026: 7–3–0 \(\d+\.\d%\)/`; removed the "196 decided" assertion.
- Created the unified rollout contract and updated: plan 05 (Superseded), plan 03 (Phase 2 absorbed as D4; republish note re-pointed), plan 01 (Phase B gated as D5), `docs/plans/index.md`, `docs/data/known_issues.md`, `docs/status.md` (Next session + team-stats hold re-pointed; last-updated date).

## Files Modified
- `web/src/components/slate/ModelRecord.tsx` - record cell redesign, header text
- `web/src/components/slate/TopLeans.tsx` - season label + prop
- `web/src/components/slate/SlateView.tsx` - pass season to TopLeans
- `web/e2e/publication.spec.ts` - assertions updated
- `docs/plans/2026-10-03/01-unified-data-fix-and-matchup-rollout.md` - new contract
- `docs/plans/2026-10-02/05-data-issues-review-and-rerun.md` - Superseded
- `docs/plans/2026-10-02/03-team-stats-feeds-ratings.md` - Phase 2 absorbed note
- `docs/plans/2026-10-02/01-matchup-data-layer-v2.md` - Phase B gate note
- `docs/plans/index.md`, `docs/data/known_issues.md`, `docs/status.md` - cross-references

## Validation
- [x] `npm --prefix web run typecheck` / `lint` / `build` — passed
- [x] `npm --prefix web run test:publication` — 110/110
- [x] `npm --prefix web run test:ui -- publication.spec.ts` — 23/23
- [x] `git diff --check`

## Amendments and Blockers
- None.

## Handoff Notes
- **Resume at:** unified plan Phase 1 Task 1.0 (re-baseline Preview/production row counts) — needs `CFB_R2_*` credentials loaded (`.env` currently only carries storage backend + DB URLs).
- **Watch out for:** no production writes and no `CFB_MATCHUP_ENABLED=1` until D1–D6 are decided; any change to `ppp`/`epa_per_possession` stops the batch and needs its own contract.

**tags:** ["web", "ui", "docs", "data-quality", "planning"]
