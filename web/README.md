# CK's Picks Web App

Next.js 16 / React 19 / Tailwind v4 application served from Vercel and backed
by Neon Postgres. The Python pipeline owns football-model generation; this app
only renders the selected immutable run under the configured publication policy.

## Current boundary

V5 is the 2026 serving family; V4 is the rollback path. Research/shadow models
must not alter web schemas, queries, publication, or the V4 rollback path until
separately promoted.

`CFB_PUBLICATION_MODE=predictions` is an explicit approved release mode.
Anything else is fail-closed market-only rendering. Prediction publication does
not authorize a model change.

`CFB_DISPLAY_ONLY_NOTICE=0` hides the display-only timing notice on Picks and
Results; unset (or anything else) shows it. The run's `display_only` database
flag and its freeze/evidence guards are independent of this presentation flag.

## Local matchup pages

The matchup pages are meant to be run locally for now; production stays closed and nothing in Vercel needs to change.

```bash
make web-local                    # preview data (default), http://127.0.0.1:3000/matchup
make web-local ENV=production     # the same Week 5 data from the production database
# or: zsh scripts/ops/run_web_local.sh [preview|production]
```

The script uses the restricted pipeline login from the macOS Keychain (not the owner `DATABASE_URL` in `web/.env`) and the app only reads. `/matchup` lists the week's games by day (`?week=N` for other weeks); each game opens its breakdown, and the breakdown links back to the week. Without a database, `CFB_UI_TEST_MODE=1 npm run dev` serves fixtures.

## Local development

```bash
cp .env.example .env
# Set DATABASE_URL to an isolated Neon branch.
npm install
npm run dev
```

Use the explicit Preview migration command in the
[weekly pipeline](../docs/ops/weekly_pipeline.md) and
`make contracts-check`; `contracts/schema.ts` is canonical and the web copy
must remain synchronized.

## Routes and feature flags

| Route | Status |
|---|---|
| `/`, `/results`, `/ratings`, `/performance`, `/teams/[team]` | Public |
| `/matchup` and `/matchup/[gameId]` | A game picker and the pre-game breakdown. Full-time public feature on the site (open in production and dev, emergency-disabled only if `CFB_MATCHUP_ENABLED=0`); always `noindex`. Game cards (Picks and Results) show a **Matchup** button linking to each breakdown. The breakdown shows 12 raw metrics in three sections (the two tables sit side by side from `lg` up, stacked on a phone, in a `max-w-5xl` container); tied national ranks read `T-N`, an exact zero is shown without a rank, and PPA values are CFBD's predicted points added (labelled PPA, not EPA). The top card shows a Forecast & Lines grid (Spread and Total columns: Market, Model, Model Bet). A per-row edge calculation (offense rank against the opposing defense's rank) exists in `team-stats.ts` but is not drawn on the page; the explanatory notes sit below the tables. **Share:** when a game has published stats, the top strip offers *Download PNG* (plus *Copy image* or *Share* where the browser supports them): `ShareCard` is a fixed 1080x1350 always-dark card (literal colors, dark logo variants via `logoSrc`, Eastern kickoff time) rasterized at 2x by `html-to-image`; it is mounted only while an image is being made and carries a "Biggest mismatches" box per panel (`topMismatches` in `team-stats.ts`) and a footnote when any value shows "—". Team names are plain text everywhere: team pages are not linked (the `/teams/[team]` route still exists but nothing links to it). Shows pre-game team stats from `team_season_stats` (see the [team stats contract](../docs/plans/2026-10-01/10-authentic-team-stats-pipeline.md)). |

Fixture mode: `CFB_UI_TEST_MODE=1` serves sample data (no database) for the
Picks/Results slates, the matchup page and the Playwright suite. Optional tables
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
CI=1 CFB_UI_TEST_MODE=1 npx playwright test   # e2e in fixture mode (npm run test:ui)
```

`playwright.config.ts` starts its own dev server on port 3100 with `CFB_UI_TEST_MODE=1 CFB_PUBLICATION_MODE=predictions`, so the slate tests run against the same fixtures locally and in CI (CI has no `web/.env`; the publication mode otherwise defaults to market). The e2e dev server shares `.next` with `npm run dev`: stop a local dev server before running it, or test a clean `git worktree` (clone `node_modules` with `cp -Rc`; Turbopack rejects a symlinked `node_modules`).

## Team logos

Logos are self-hosted, keyed by CFBD team id, and built once per season:

```bash
cd web
npm run logos:build -- --dry-run   # inspect the CFBD response first (needs CFBD_API_KEY in ../.env)
npm run logos:build                # download, resize (96/256 px WebP, light + dark), write manifest
```

Output: `public/logos/v2/{sm,lg}/{light,dark}/<id>.webp`, `public/logos/v2/manifest.json`
(source URL, date and SHA-256 per file) and `src/lib/team-logos.generated.ts`
(school name to id). Commit all three. `TeamLogo` renders the light/dark pair,
an initials tile for unknown teams. Alternate spellings are mapped to the CFBD
name in `src/lib/team-logos.ts`. The Python leaderboards read the same manifest. Contract: `docs/plans/2026-10-01/07-high-quality-team-logos.md`.

See the [weekly pipeline](../docs/ops/weekly_pipeline.md) and
[production runbook](../docs/ops/production_runbook.md) for publish, freeze,
close, health, and rollback operations.
