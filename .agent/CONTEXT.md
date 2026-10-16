# Project Context

## Product and current authority

CKsPicks-CFB publishes college-football spread and total leans through a Next.js 16 / React 19 / Tailwind v4 web app. Python 3.12 produces V5 Blitzkrieg forecasts; Neon serves derived projections; Cloudflare R2 preserves immutable data and artifacts. See [`docs/status.md`](../docs/status.md) for live release IDs, week state and the scoreboard, the [V5 guide](../docs/modeling/v5_status.md) for the accepted model, and the [weekly runbook](../docs/ops/weekly_runbook.md) for all recurring operations.

V5 is the only operational model. V4 lineage, windows and results are [historical evidence](../docs/modeling/v4_retrospective.md), no longer an operational rollback path. Rollback reactivates a prior verified V5 season release. Six slates are not a prelaunch gate; the cumulative 2026 record is monitoring evidence.

## Architecture

```text
CFBD / Odds API → immutable Bronze captures + catalog registry
→ reconciled Silver schedules, outcomes, plays, drives, market quotes
→ revision manifest with URIs, hashes, capture times and exact score exceptions
→ season engine: point-in-time measurements → ratings → forecasts → grades
→ verified serving projections → stage + atomic activate → Neon → Vercel
```

`build_season_revision.py` reuses controller ingestion/Silver steps and creates cumulative registered market inputs. `run_season.py prepare` reconstructs completed weeks and forecasts the next slate at its pre-week cutoff; `season_verification_v2` enforces 23 verification checks. `run_season.py release` stages immutable projections and atomically activates the release after verification/readback, expected-prior-release checks and, for Production, independent Preview rehearsal proof. Active-release context makes Picks, Results, Ratings, Performance and health resolve the same release. Legacy web reads remain only as a fallback when there is no active season release.

Neon `season_releases`, `season_release_policies` and `season_release_*` projection tables are defined by migration `0025`. Earlier `prediction_runs`, `current_week`, `games`, grades and optional matchup tables remain for compatibility. Schema upgrades are append-only under `contracts/migrations/`; `contracts/schema.sql` and `schema.ts` are canonical. Web copies must pass `make contracts-check`.

## Operational invariants

- R2 is the durable source of truth; Neon is derived serving state and catalog metadata. `CFB_STORAGE_BACKEND=r2` selects the lake; `local` requires the external `CFB_MODEL_DATA_ROOT`. Never use repository-local `./data/`.
- Preview and Production use separate Neon branches and credentials. R2 credentials currently name the same immutable bucket; select the correct credential set with `CFB_ARTIFACT_ENV` through the environment wrappers. See the runbook's Environments section for roles and Keychain setup; never print secrets.
- Capture current lines before building the revision; reconcile the full FBS schedule against fresh spread and total coverage. Only registered captures enter cumulative market inputs. Registering additional captures can change best-quote grades and needs authorization.
- Exact per-team-game score reconciliation is mandatory, except for declared hash-pinned exceptions; unused exceptions fail too.
- Commit reviewed revision inputs before preparing from a clean tree. Do not commit between prepare and the last release: the code commit is part of candidate identity.
- Preview rehearsal precedes owner-approved Production activation. Production rollback requires owner authorization and the owner/migrator credential; the provided wrappers do not support Preview rollback.
- `make weekly`, `publish-week`, `freeze-week` and `close-week` refuse execution. Remaining legacy writers and the old ops publishing state machine are not the operational path.

## Modeling and evidence

V5 uses validated football measurements, primarily upstream opponent adjustment, continuous team ratings with changing prior/evidence credibility, and a rating-to-margin/total Ridge bridge. Market information never enters football features, ratings or model selection. Do not double-count schedule strength or rating variance. Polls/direct-core models are diagnostic-only; the original Phase 4B retained manifest is prohibited as a forecasting parent.

Research development windows are 2015–2019 and 2021–2025, excluding 2020 throughout. V4's sealed 2021–2025 chronology is historical and remains unchanged. Training and all target-aware transforms must precede prediction. Point-in-time data loading is mandatory for feature work.

The public 2026 record is one continuous V5 record from Week 0. Forecasts for started/reconstructed games use only pre-cutoff observations and remain visible on Picks. Grading uses the best eligible pre-kickoff quote per game/target under the [record methodology](../docs/modeling/record_methodology.md). Pre-kickoff forecast freezes distinguish prospective provenance; historical point-in-time reconstruction does not become prospective evidence. Betting decisions are deferred; research stays isolated until separately promoted.

Maintain `season`, `week`, `game_id` and `team` keys, with consistent `off_*`, `def_*` and `adj_*` naming. See the [measurement catalog](../docs/modeling/measurement_catalog.md) and [rating requirements](../docs/modeling/rating_system_requirements.md).

## Code and tooling

| Concern | Location |
|---|---|
| Season preparation, grading, verification, serving and release | `src/cks_picks_cfb/season/` |
| Revision and season CLI | `scripts/pipeline/build_season_revision.py`, `run_season.py` |
| Pinned model and weekly revision contracts | `conf/season/2026/` |
| Lake, catalog, providers, Silver and reconciliation | `src/cks_picks_cfb/data/` |
| Football measurements | `src/cks_picks_cfb/features/` |
| Accepted V5 and isolated rating/forecast research | `src/cks_picks_cfb/ratings/`, `forecast/`, `ratings_lab/`, `audit/`; `scripts/research/` |
| Shared schema and migrations | `contracts/`, `src/cks_picks_cfb/db/` |
| Read-only release resolution and publication rendering | `web/src/lib/season-release-context.ts`, `queries.ts`, `publication.ts` |
| Keychain environment wrappers | `scripts/ops/` |

Python remains at the root; web owns its npm toolchain in `web/`. Make targets and Nx coexist. V4/Hydra/MLflow, old inference and 6A/6B rebuild code still exist for compatibility pending deferred Phase 3 cleanup; do not infer live operational authority from their presence.

## Validation and workflow

Use [quickstart](../.codex/QUICKSTART.md) and `make help` for commands. Validate changed components, contracts and quality registry, Python/Ruff, web lint/typecheck/tests/build, strict MkDocs and `git diff --check`. CI combines Python-suite coverage with a 60% threshold. Database suites use disposable local clusters, never serving databases.

Substantial work follows a durable Sol-to-Terra contract in `docs/plans/`; review recent logs before editing, preserve unrelated changes, and leave staging/commits to the owner. Update status only when current release/week state changes. Historical contracts and dated logs are evidence, not operating authority.
