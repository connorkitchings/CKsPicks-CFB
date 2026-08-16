# Session: Vercel App Presentation Overhaul

## TL;DR
- **Worked On:** Full presentation redesign of the `web/` Next.js app — semantic design-token layer, matchup-centric game cards, refined-minimal restyle of every component.
- **Outcome:** 12 files under `web/src/` restyled onto a token system; all quality gates pass (lint, typecheck, publication boundary 3/3, production build).
- **Plan Contract:** `N/A (fast path)` — presentation-only, single subsystem; plan approved in-session before implementation.
- **Approval / Status:** User approved the stated plan ("go") covering token system, card anatomy, color discipline, emoji removal, and ThemeToggle relocation.
- **Blockers:** Local smoke test limited by pre-existing Neon schema drift (see Handoff).
- **Next:** User reviews visually (`npm run dev` once DB branch is migrated), then commit lands on `feat/web-presentation`.

## Context and Decisions
- **Routing:** Fast path. Presentation-only inside `web/`; no changes to queries, publication boundary, schema, contracts, pipeline, or deployment behavior. The fail-closed `market`/`predictions` modes are untouched.
- **Design direction (user-selected):** refined minimal; matchup-centric cards; zinc + Geist retained and systematized.
- **Token layer (`globals.css`):** semantic Tailwind v4 `@theme` tokens — `surface-page/card/inset`, `line/line-strong`, `ink/ink-muted/ink-faint`, single `accent` family (blue), `win`/`loss` (emerald/rose) reserved for graded results, `warn` (amber). Light/dark flips via the existing `.dark` class; components no longer carry `dark:` variants or raw palette classes (verified: zero remain outside token definitions).
- **Color discipline:** one accent hue marks the lean (team identity carries direction, not home=blue/away=rose); over/under leans are neutral with ↑/↓; emerald/rose only for win/loss grades; 🏠/✈️ emojis removed; high-confidence is now a single quiet ★ in the meta row (was card ring + badge).
- **Game card anatomy:** shared shell for both modes — meta row (kickoff, regime chip, ★) → matchup block (28px logos, leaned team in semibold, big tabular-nums final scores inline) → right rail (predictions: lean team + signed line + edge; market: current lines) → hairline Market-vs-Model footer (predictions only). No-line games show a quiet inline note instead of an amber banner.
- **ThemeToggle** moved from the floating fixed bottom-right overlay into the header right cluster.
- **Typography:** Geist Sans/Mono kept; `tabular-nums` on all numerics (lines, edges, scores, records, week counts).
- **Branch:** new `feat/web-presentation` off `codex/2026-ops-cleanup` HEAD so Vercel-only commits stay separate from the parallel data/pipeline session.

## Work Completed
- Token layer in `globals.css` (light + dark values, `@theme inline` mapping).
- Rebuilt `GameRow.tsx` (shared shell, `MarketGameRow` rail, `TeamLine` with inline scores, `ResultChip`) and `LeanBadge.tsx` (rail-style lean + total with edge subscript; new `homeLine` prop).
- Restyled `GamesList.tsx` controls, `Header.tsx` (+toggle), `Footer`, `RecordBanner.tsx` (also computes ROI once instead of 3×), `WeekNav.tsx`, `ThemeToggle.tsx`, `page.tsx`, `loading.tsx` (skeleton mirrors new card), `error.tsx` onto tokens.

## Files Modified
- `web/src/app/globals.css` — semantic token layer
- `web/src/components/GameRow.tsx` — matchup-centric card, shared market/predictions shell
- `web/src/components/LeanBadge.tsx` — rail lean presentation, emoji-free, arrow totals
- `web/src/components/GamesList.tsx` — controls on tokens
- `web/src/components/Header.tsx` — toggle relocated in, metadata quieted
- `web/src/components/ThemeToggle.tsx` — button on tokens
- `web/src/components/RecordBanner.tsx` — tokens + tabular-nums
- `web/src/components/WeekNav.tsx` — tokens
- `web/src/app/layout.tsx` — floating toggle removed
- `web/src/app/page.tsx` — banners/empty states on tokens (warn token family)
- `web/src/app/loading.tsx` — skeleton mirrors new card shape
- `web/src/app/error.tsx` — loss token family

## Validation
- [x] `npm run lint` — clean
- [x] `npm run typecheck` — clean
- [x] `npm run test:publication` — 3/3 pass (fail-closed market/predictions boundary unchanged)
- [x] `npm run build` — Next.js 16 production build succeeds; all routes generated
- [x] `git diff --check` — clean
- [x] Production-server smoke: header + new loading skeleton render with token classes
- [ ] Full page visual smoke — **blocked** (see below)

## Amendments and Blockers
- **Blocker (pre-existing, not session-caused):** the Neon branch behind `web/.env` `DATABASE_URL` is missing `current_week.active_run_id` (NeonDbError: column does not exist), so `page.tsx` cannot fully render locally. `contracts/schema.sql:189` already contains the column — the branch simply hasn't had the contract schema applied. Fix belongs to the data/pipeline session: apply `contracts/schema.sql` (or `make migrate-db`) to that Neon branch. No action taken here — DB/migrations are out of this session's scope.

## Handoff Notes
- **Resume at:** `git add` the 12 `web/src/` files and commit with the proposed message; then `npm run dev` (after DB branch migration) for visual review in light + dark.
- **Watch out for:** do not stage `artifacts/preview/` (untracked, belongs to the data/pipeline session). Untouched.
- **Commit message:**

  ```text
  feat(web): redesign presentation layer with semantic design tokens

  - Add semantic token layer in globals.css (surface/line/ink/accent/
    win/loss/warn) replacing all ad-hoc palette + dark: classes
  - Rebuild game card as matchup-centric shell shared by market and
    predictions modes: inline final scores, right lean/market rail,
    hairline market-vs-model footer
  - Simplify lean visuals: single accent hue, arrow-marked totals,
    quiet high-confidence star, emojis removed
  - Move ThemeToggle into header; restyle nav, record banner,
    controls, loading skeleton, and error/empty states
  - tabular-nums on all numeric displays

  Validation: lint, typecheck, test:publication (3/3), next build
  ```

**tags:** ["web", "vercel", "presentation", "design-system", "fast-path"]
