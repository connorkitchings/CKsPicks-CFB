# CK's Picks Web App

Next.js 16 / React 19 / Tailwind v4 application served from Vercel and backed
by Neon Postgres. The Python pipeline owns football-model generation; this app
only renders the active immutable season release under the configured publication policy.

## Current boundary

V5 Blitzkrieg is the only operational model. The active `season_releases` context resolves the Games, Ratings, Stats and Model tabs and `/api/health` to the same atomic release. The four-tab layout lives on `dev` until it is merged to `main`. Legacy reads remain only when no season release is active. Rollback reactivates a prior verified V5 release; V4 is [historical evidence](../docs/modeling/v4_retrospective.md). Research requires separate promotion before altering serving or publication.

Current release IDs and week state belong in [`docs/status.md`](../docs/status.md). Follow the [weekly runbook](../docs/ops/weekly_runbook.md) for revision, prepare, Preview rehearsal, owner-approved Production release and rollback.

`CFB_PUBLICATION_MODE=predictions` is an explicit approved release mode.
Anything else is fail-closed market-only rendering. Prediction publication does
not authorize a model change.

`CFB_DISPLAY_ONLY_NOTICE=0` hides the display-only timing notice on Games; unset (or anything else) shows it. The run's `display_only` database
flag and its freeze/evidence guards are independent of this presentation flag.

## Local matchup pages

Matchup pages are a public feature. Use local Preview reads for development and verification.

```bash
make web-local                    # preview data (default), http://127.0.0.1:3000/
make web-local ENV=production     # read the active Production release locally
# or: zsh scripts/ops/run_web_local.sh [preview|production]
```

The script uses the restricted pipeline login from the macOS Keychain (not the owner `DATABASE_URL` in `web/.env.local`) and the app only reads. Games (`/`) lists the week's games by day (`?week=N` for other weeks); each game card links to its matchup breakdown (`/matchup/[gameId]`), which links back to the week. Without a database, `CFB_UI_TEST_MODE=1 npm run dev` serves fixtures.

## Local Stats review

Stats (`/stats`) is unpublished by default in every environment. Only the exact setting `CFB_CHARTS_ENABLED=1` enables the navigation item and the route. Unset, empty, `0` or invalid values hide the item and return HTTP 404 for direct URLs (`src/proxy.ts` rejects before any data loads); legacy `/charts` URLs redirect to `/stats` when enabled. Development, Preview and fixture mode do not override the flag. Mobile navigation has three equal items when Stats is disabled and four when enabled.

Run these from the repository root:

```bash
CFB_CHARTS_ENABLED=1 make web-local ENV=preview
# Fixture-only review without a database:
CFB_CHARTS_ENABLED=1 CFB_UI_TEST_MODE=1 CFB_PUBLICATION_MODE=predictions npm --prefix web run dev
```

For owner-authorized Vercel Preview review, set `CFB_CHARTS_ENABLED=1` in Preview only. Keep Production unset or `0` until manual publication approval. Rebuild/redeploy after changing the environment setting; this is a deployment-level switch, not an instant runtime toggle.

Stats code can follow normal `dev` to `main` integration with public access disabled. The flag does not skip chart projection creation, the migration 0026/0027 requirements or owner-approved atomic releases. Review the newer weekly code and required migrations separately before preparing from the actual clean integrated commit.

## Local development

```bash
# Create web/.env.local from the example, then set DATABASE_URL to an isolated Neon branch.
cp .env.example .env.local
npm install
npm run dev
```

Use the explicit Preview migration command in the
[weekly runbook](../docs/ops/weekly_runbook.md) and
`make contracts-check`; `contracts/schema.ts` is canonical and the web copy
must remain synchronized.

## Routes and feature flags

| Route | Status |
|---|---|
| `/` (Games), `/ratings`, `/model`, `/model/method`, `/teams/[team]` | Public |
| `/stats` | Disabled unless `CFB_CHARTS_ENABLED=1`; disabled direct requests return HTTP 404 before chart data loading. Requires a chart-capable active release when enabled. |
| `/results`, `/matchup` | Redirect to `/` |
| `/performance`, `/methodology` | Redirect to `/model` and `/model/method` |
| `/charts`, `/charts/...` | Redirect to `/stats` (when enabled) |
| `/matchup/[gameId]` | The pre-game breakdown. Full-time public feature on the site (open in production and dev, emergency-disabled only if `CFB_MATCHUP_ENABLED=0`); always `noindex`. Game cards on Games show a **Matchup** button linking to each breakdown. The breakdown shows 12 raw metrics in three sections (the two tables sit side by side from `lg` up; smaller screens select one team’s offense at a time, with values and ranks paired in three columns on phones, in a `max-w-5xl` container); tied national ranks read `T-N`, an exact zero is shown without a rank, and PPA values are CFBD's predicted points added (labelled PPA, not EPA). The top card groups both teams together above a full-width Forecast & Lines grid (Spread and Total columns: Market, Model, Model Bet). A per-row edge calculation (offense rank against the opposing defense's rank) exists in `team-stats.ts` but is not drawn on the page; the explanatory notes sit below the tables. **Share:** when a game has published stats, the top strip offers *Download PNG* (plus *Copy image* or *Share* where the browser supports them): `ShareCard` is a fixed 1080x1350 always-dark card (literal colors, dark logo variants via `logoSrc`, Eastern kickoff time) rasterized at 2x by `html-to-image`; it is mounted only while an image is being made and carries a "Biggest mismatches" box per panel (`topMismatches` in `team-stats.ts`) and a footnote when any value shows "—". Team names are plain text everywhere: team pages are not linked (the `/teams/[team]` route still exists but nothing links to it). Shows pre-game team stats from `team_season_stats` (see the [team stats contract](../docs/plans/2026-10-01/10-authentic-team-stats-pipeline.md)). |

## Mobile presentation

Games uses compact game cards on phones, with visible spread/total records and collapsed Best Bets or Highlights. Game details expose the full forecast, line source, venue and applicable grading explanation. The grid/list choice remains available from 640 px; choosing a desktop list still renders cards on a phone without duplicating game anchors.

Ratings emphasizes the selected Overall, Offense or Defense value. The phone period selector and desktop timeline preserve live search and sort when navigating between frozen periods; filtering retains national rank. Overall uncertainty stays explicitly labeled.

Matchup pages show both teams together with forecasts below them. Below 1024 px, the offense selector switches between the two comparisons; larger screens show both. Share-image data and fixed export dimensions remain unchanged.

Model (`/model`) leads with separate spread and total records, with season diagnostics expandable; `/model/method` explains the method.

Shared controls use generous touch targets, and the bottom navigation reserves device safe-area space. The mobile implementation contract is [Mobile web experience](../docs/plans/2026-10-18/04-mobile-web-experience.md).

Fixture mode: `CFB_UI_TEST_MODE=1` serves sample data (no database) for the
Games slates, the matchup page and the Playwright suite. Optional tables
(`game_venues`, `team_season_stats`, `prediction_market_selections`) are
checked with `to_regclass`, so the app works before their migrations are
applied and simply shows no location, stats or best-line source.

## Verification

```bash
npm run lint
npm run typecheck
npm run test:publication   # unit tests (publication boundary, picks helpers, team stats, logos, gates)
npm run test:logos         # logo build script helpers
npm run build
npm run test:charts-gate   # separate disabled production build/server; no database
CI=1 CFB_UI_TEST_MODE=1 npx playwright test   # e2e in fixture mode (npm run test:ui)
```

`playwright.config.ts` starts its own dev server on port 3100 with `CFB_UI_TEST_MODE=1 CFB_PUBLICATION_MODE=predictions CFB_CHARTS_ENABLED=1`, so the slate tests run against the same fixtures locally and in CI (CI has no `web/.env.local`; the publication mode otherwise defaults to market). The enabled browser suite and disabled publication-gate suite run sequentially and never reuse an existing server. The gate suite builds with Charts off and tests the production server, including actual HTTP 404 responses, four-item navigation and the core pages. The e2e dev server shares `.next` with `npm run dev`: stop a local dev server before running it, or test a clean `git worktree` (clone `node_modules` with `cp -Rc`; Turbopack rejects a symlinked `node_modules`).

## Team logos

Logos are self-hosted, keyed by CFBD team id, and built once per season:

```bash
cd web
npm run logos:build -- --dry-run   # inspect the CFBD response first (needs CFBD_API_KEY in the repository-root .env)
npm run logos:build                # download, resize (96/256 px WebP, light + dark), write manifest
```

Output: `public/logos/v2/{sm,lg}/{light,dark}/<id>.webp`, `public/logos/v2/manifest.json`
(source URL, date and SHA-256 per file) and `src/lib/team-logos.generated.ts`
(school name to id). Commit all three. `TeamLogo` renders the light/dark pair,
an initials tile for unknown teams. Alternate spellings are mapped to the CFBD
name in `src/lib/team-logos.ts`. The Python leaderboards read the same manifest. Contract: `docs/plans/2026-10-01/07-high-quality-team-logos.md`.

The shared `logoSrc` policy preserves team colors where the standard mark remains readable on dark surfaces: Tennessee, Clemson, Sam Houston, Texas, North Texas, Buffalo and Utah use the existing `light` asset in both themes and sizes. Other schools retain their dark contrast variants, including Alabama, Michigan, Duke and Temple. This curated, visually audited policy applies to cards, charts and image exports; it changes asset selection without rewriting the assets or manifest. Audit evidence is in `session_logs/2026-10-16/10-dark-logo-color-repair.md`.

Started and reconstructed games remain visible on Games: forecasts use pre-cutoff observations, and grades select eligible pre-kickoff quotes per game/target. See the [record methodology](../docs/modeling/record_methodology.md). Operational release and rollback instructions live only in the [weekly runbook](../docs/ops/weekly_runbook.md).
