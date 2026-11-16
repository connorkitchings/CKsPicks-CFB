# Stratum CFB Web App

Next.js 16 / React 19 / Tailwind v4 application served from Vercel and backed
by Neon Postgres. The Python pipeline owns football-model generation; this app
only renders the active immutable season release under the configured publication policy.

Public identity is centralized in `src/lib/brand.ts`; the outlined wordmark and reproduction/license records live in `design/stratum-wordmarks/` at repository root. The existing host is unchanged. See the [Stratum brand decision](../docs/decisions/2026-10-27-stratum-cfb-brand.md).

## Current boundary

V5 Blitzkrieg is the only operational model. The active `season_releases` context resolves the Games, Teams, Graphs and Model tabs and `/api/health` to the same atomic release. Legacy reads remain only when no season release is active. Rollback reactivates a prior verified V5 release; V4 is [historical evidence](../docs/modeling/v4_retrospective.md). Research requires separate promotion before altering serving or publication.

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

### Matchup "How the ratings are built"

Below Team stats (only when lineage is ready and stats are present), the matchup page explains the four displayed unit ratings from the release's `team_rating_components` rows: each unit's raw points per possession explained in a plain sentence (with the adjusted value), the rating with its rank and "above/below average" wording, the preseason estimate's share of the rating, and a collapsed "Week by week" season-to-date table (cumulative raw and adjusted points per possession after each week, ending at the headline numbers) and a nested, collapsed "Each game's effect on the rating" table whose per-game effects plus the preseason estimate add up to the rating. Components are looked up by `${snapshotId}:${role}` from the rendered rating rows, and opponent names come from `games`. `src/lib/rating-breakdown.ts` fail-closes per unit (`missing`, `mismatch`, `invalid` or `lookup`): a unit whose stored rating, snapshot, source, team or role disagrees with what the page rendered, or whose row does not sum to its rating, shows "Breakdown unavailable" with no numbers. A failure here never fails the page. Fixture game ids `987657` (one mismatched unit) and `987658` (preseason-only units) exercise those states.

## Graphs (`/stats`)

Graphs (`/stats`) is public alongside Games, Teams and Model. Legacy `/charts` URLs redirect to `/stats` with a 307. Mobile navigation has four equal items (`grid-cols-4`).

Run these from the repository root:

```bash
make web-local ENV=preview
# Fixture-only review without a database:
CFB_UI_TEST_MODE=1 CFB_PUBLICATION_MODE=predictions npm --prefix web run dev
```

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
| `/` (Games), `/teams`, `/stats`, `/model`, `/model/method`, `/teams/[team]` | Public |
| `/ratings` | Permanent redirect to `/teams`, preserving query parameters |
| `/results`, `/matchup` | Redirect to `/` |
| `/performance`, `/methodology` | Redirect to `/model` and `/model/method` |
| `/charts`, `/charts/...` | Redirect to `/stats` |
| `/matchup/[gameId]` | Public pregame breakdown (emergency opt-out: `CFB_MATCHUP_ENABLED=0`), always `noindex`. Forecast and market overview, deterministic facts, one shared offense selector, contextual unit measurements, validated rating evidence, and sharing controls. Completed games preserve frozen pregame context alongside the final outcome. |

## Analytical navigation and presentation

The editorial interface uses Games / Teams / Graphs / Model, with global team search, a common analysis canvas, light/dark themes, and persistent phone navigation. The [implementation contract](../docs/plans/2026-11-15/site-redesign-and-analytical-usability.md) records scope and validation state.

Games offers Today / Upcoming / Results / All, card/list layouts and model-versus-market comparison. Upcoming and awaiting-published-result states use the existing Eastern-time rules; the site is not a live scoreboard. The Model vs market view shows spread and total together, side by side on larger screens and stacked on phones, with separate coverage and point scales. Point differences are descriptive comparisons. Line-capture timestamps remain in serving provenance but are hidden in the interface. Forecast updates and release activation are distinct timestamps.

Teams (`/teams`) combines Rankings, Trends, Strength vs résumé and two-team Compare. All views use the same exact certified period. National competition ranks are independent of filtering and sort direction; weekly movement requires the preceding certified week. Profiles connect schedules, component trajectories, comparisons and validated rating evidence.

Graphs is for football measurements. It defaults to Efficiency vs explosiveness, offers persistent team details and equivalent sortable tables, and preserves filters in shareable URLs. Explicit unavailable views retain their requested context and explain coverage without substituting data.

Matchup pages lead with forecasts and concise facts, then offense-versus-defense comparisons and rating evidence. A single comparison selection governs related tables and exports. Full tables remain available as detail. Raw-to-adjusted explanations reuse verified rating components, rather than combining incompatible statistical windows.

Model leads with separate spread/total records and paired pre-kickoff market comparisons, followed by trends and game-level errors. The error scatter compares model and retained-market absolute errors on the same eligible games. Weekly summaries initially show the latest four periods, with the full archive expandable. `/model/method` explains the method and evidence limits.

All new views preserve publication and lineage safeguards. Public forecast ranges, pace, turnovers and detailed actual-game postgame analysis are deferred. Shared controls remain keyboard accessible and phone layouts reserve safe-area space.

Fixture mode: `CFB_UI_TEST_MODE=1` serves sample data (no database) for the
Games slates, the matchup page and the Playwright suite. Optional tables
(`game_venues`, `team_season_stats`, `prediction_market_selections`) are
checked with `to_regclass`, so the app works before their migrations are
applied and simply shows no location, stats or best-line source.

## Verification

```bash
npm run lint
npm run typecheck
npm run test:publication   # unit tests (publication boundary, picks helpers, team stats, logos)
npm run test:logos         # logo build script helpers
npm run build
CI=1 CFB_UI_TEST_MODE=1 npx playwright test   # e2e in fixture mode (npm run test:ui)
```

`playwright.config.ts` starts its own dev server on port 3100 with `CFB_UI_TEST_MODE=1 CFB_PUBLICATION_MODE=predictions`, so the slate tests run against the same fixtures locally and in CI (CI has no `web/.env.local`; the publication mode otherwise defaults to market). The e2e dev server shares `.next` with `npm run dev`: stop a local dev server before running it, or test a clean `git worktree` (clone `node_modules` with `cp -Rc`; Turbopack rejects a symlinked `node_modules`).

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
