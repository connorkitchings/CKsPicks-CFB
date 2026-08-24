# CK's Picks Web App

Next.js 16 / React 19 / Tailwind v4 application served from Vercel and backed
by Neon Postgres. The Python pipeline owns football-model generation; this app
only renders the selected immutable run under the configured publication policy.

## Current boundary

V4 is the 2026 production champion. The future rating architecture is
research/shadow-only and must not alter web schemas, queries, publication, or
the V4 rollback path until separately promoted.

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

Use the repository-root migration flow (`make migrate-db ENV=preview`) and
`make contracts-check`; `contracts/schema.ts` is canonical and the web copy
must remain synchronized.

## Verification

```bash
npm run lint
npm run typecheck
npm run test:publication
npm run build
```

See the [weekly pipeline](../docs/ops/weekly_pipeline.md) and
[production runbook](../docs/ops/production_runbook.md) for publish, freeze,
close, health, and rollback operations.
