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

## Verification

```bash
npm run lint
npm run typecheck
npm run test:publication
npm run build
```

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
an initials tile for unknown teams, and the legacy 32 px PNG only until the
generated map is populated. Contract: `docs/plans/2026-10-01/07-high-quality-team-logos.md`.

See the [weekly pipeline](../docs/ops/weekly_pipeline.md) and
[production runbook](../docs/ops/production_runbook.md) for publish, freeze,
close, health, and rollback operations.
