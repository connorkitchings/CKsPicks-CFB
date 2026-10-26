# Quick Start Commands

Read [`docs/status.md`](../docs/status.md) for the active release and week state, the [V5 guide](../docs/modeling/v5_status.md) for accepted model authority, and the [weekly runbook](../docs/ops/weekly_runbook.md) before any operational action. V5 Blitzkrieg is the only operational model; [V4](../docs/modeling/v4_retrospective.md) is historical evidence. Six slates are not a prelaunch requirement.

## Setup and development

```bash
uv sync --group dev
npm --prefix web install
make help
make web-local ENV=preview
```

`make web-local ENV=production` reads Production for local inspection; it does not activate a release. `CFB_UI_TEST_MODE=1 npm --prefix web run dev` serves fixtures without a database. Graphs (`/stats`) is published with no feature flag. The 4-tab site is Games / Ratings / Graphs / Model. Matchup pages are public by default; `CFB_MATCHUP_ENABLED=0` is an emergency opt-out.

For R2 operations set `CFB_STORAGE_BACKEND=r2` and use the intended environment wrapper. `with_preview_env.sh` injects Preview catalog credentials and `CFB_ARTIFACT_ENV=preview`; Production pipeline and owner wrappers have distinct roles. Verify presence without printing credentials. For the local backend require `CFB_STORAGE_BACKEND=local`, `CFB_MODEL_DATA_ROOT` and a mounted external drive. Never create or read repository-local `./data/`.

`CFBD_API_KEY` is required for CFBD ingestion; `THE_ODDS_API_KEY` is needed for explicit paid Odds API captures. Keep secrets outside git. Do not copy owner or pipeline database credentials into Vercel: the web app uses a read-only role. `CFB_PUBLICATION_MODE=predictions` is the approved web rendering mode; other values fail closed to market-only output.

## Weekly V5 release

Follow the complete [weekly runbook](../docs/ops/weekly_runbook.md), including line capture, cutoff choice, exact score exceptions, Preview readback and owner activation. The commands below show the interfaces, not a ready-to-run current-week release:

```bash
make season-close-week WEEK=<NEXT_WEEK> AS_OF=<POST_WEEK_CUTOFF> PRE_WEEK_CUTOFF=<PRE_WEEK_CUTOFF> RUN_ID=<FRESH_RUN_ID>
# Owner commits reviewed revision manifest and score exceptions before prepare.
make season-prepare WEEK=<NEXT_WEEK> AS_OF=<PRE_WEEK_CUTOFF> [MANIFEST=<REVISION_MANIFEST>]  # default: revision_manifest_w<NEXT_WEEK>_v1.json
# Mid-week line refresh (market-only; see the runbook's "Mid-week line refresh"):
make season-market-revision WEEK=<NEXT_WEEK> FROM=<CERTIFIED_MANIFEST> TO=<NEW_MANIFEST> REVISION_ID=<ID> CUTOFF=<ISO_UTC>
make season-release ENV=preview RELEASE_ID=<RELEASE_ID> PROJECTION_SHA=<SHA256> EXPECTED_PREVIOUS=<ACTIVE_PREVIEW_RELEASE_ID>
# Production activation needs independent Preview proof; the weekly automation does it when every gate passes.
make season-release ENV=production RELEASE_ID=<RELEASE_ID> PROJECTION_SHA=<SHA256> EXPECTED_PREVIOUS=<ACTIVE_PRODUCTION_RELEASE_ID>
```

`WEEK` names the upcoming week. `season-close-week` is the normal incremental rollover: it fetches only the completed week's observations, carries the certified earlier-week captures, and gates completed-week history against the previous manifest. `make season-revision` re-ingests every completed week and refuses to run without `FULL_HISTORY=1`; it is a repair vehicle, not the weekly path. The revision builder refreshes completed-week controller inputs and unions registered market captures; `DRY=1` only rechecks an existing completed controller run and fetches nothing. It refuses to overwrite an existing manifest. Refresh and hash-pin exact per-game/team score exceptions; unlisted mismatches and unused exceptions fail.

Prepare requires a clean committed tree. Do not commit between prepare and the last release; candidates pin the code commit. Use `RECONSTRUCT=1` only for the runbook's reconstruction case after the pre-week cutoff. Forecasts use pre-cutoff observations even when started/reconstructed games remain visible on Games; grading selects eligible pre-kickoff quotes. The local folder uses `season-2026-...`; the database prefixes `preview-` or `production-`. Release and rollback accept bare IDs or matching environment prefixes and refuse mismatches.

Production rollback uses a prior verified V5 release, a clean committed tree, explicit owner authorization and the owner/migrator Keychain credential:

```bash
make season-rollback RELEASE_ID=<TARGET_PRIOR_RELEASE_ID> EXPECTED_PREVIOUS=<CURRENT_ACTIVE_RELEASE_ID> DECISION_REF=<OWNER_DECISION> OWNER_AUTHORIZED=1
```

Preview rollback is unsupported by the provided wrappers. `make weekly`, `publish-week`, `freeze-week` and `close-week` refuse execution; legacy scripts remaining in the tree are not operational alternatives.

## Validation

```bash
make check    # mirrors CI: ruff, contracts, quality registry, pytest, mkdocs --strict, web lint/typecheck/tests/build
make test
make contracts-check
make quality-check
uv run ruff format --check .
uv run ruff check .
uv run mkdocs build --strict
npm --prefix web run lint
npm --prefix web run typecheck
npm --prefix web run test:publication
npm --prefix web run build
git diff --check
```

Run focused Python tests with `uv run pytest tests/<affected_test>.py`. Database suites require disposable local PostgreSQL clusters; `TEST_DATABASE_URL` must never name Preview or Production. CI combines Python-suite coverage and enforces 60%. Do not broad-format a dirty worktree.

Schema changes start in `contracts/` and append migrations under `contracts/migrations/`; use `scripts/pipeline/migrate_db.py --database-url` only against a verified intended owner/migrator target. `make migrate-db` is disabled. See [contracts](../contracts/README.md).

## Research

Use `scripts/research/README.md`, the [research roadmap](../docs/planning/data-first-football-forecasting-roadmap.md) and an approved task contract. Development evidence is 2015–2019 and 2021–2025; exclude 2020 and prevent future leakage. Market data is post-model comparison evidence. The original Phase 4B retained manifest is prohibited as a forecasting parent. Research cannot alter serving or public publication without separate promotion.

V4 code was removed on 2026-10-22. See the [V4 retrospective](../docs/modeling/v4_retrospective.md) for lineage and the recovery commit. Use Make for pipeline work and `npm --prefix web run ...` for web work.
