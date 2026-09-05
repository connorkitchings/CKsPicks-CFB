# Phase 0 Compatibility Baseline

**Baseline commit:** `b930066`  
**Production bundle:** `week0-2026-v4-strict-20260818-r2`  
**Production config:** `conf/weekly_bets/v4_2026.yaml`  
**Immutable bundle manifest:** `artifacts/preview/models/week0-2026-v4-strict-20260818-r2/manifest.json`  
**Manifest SHA-256:** `72429375bfa8c434c7d6fcb455bb9e22333af8c929c0cc3e832f0b80787bf25c`  
**Manifest:** `conf/repository/compatibility_v1.yaml`

This report records the clean starting point for repository alignment. It is a
compatibility record, not authorization to run production or mutate R2, Neon,
or deployment state.

## Supported interfaces

| Interface | Entry point | Primary dependencies | Offline Phase 0 check |
|---|---|---|---|
| Environment preflight | `make preflight` | runtime configuration, storage and DB clients | CLI/import and focused tests |
| Weekly preparation | `make prepare-week` | point-in-time inputs, immutable refs, ops state | state-machine tests |
| Readiness | `make readiness` | policy, artifacts, configured environment | state-machine tests |
| Prediction publish | `make publish-week` | V4 config, weekly inference, R2, Neon | isolated inference and ops tests |
| Freeze | `make freeze-week` | immutable prediction artifact | state-machine tests |
| Close and score | `make close-week` | finalized outcomes, scoring, Neon | isolated scoring and ops tests |
| Replay | `make replay-season` | recorded runs and immutable artifacts | CLI/import and ops tests |
| Reconcile and audit | `make reconcile`, `make audit-data` | R2 catalog and lineage | CLI/import and audit tests |
| Database publish/score | `make db-publish`, `make db-score` | canonical contracts and Neon | contract and publisher tests |
| Web presentation | `web/` | Neon schema and publication policy | lint, typecheck, production build |

The database schema, migrations, and team map are owned by `contracts/`.
Bundle loading is owned by `src/cks_picks_cfb/model_bundle_v3.py`; weekly
prediction routing is owned by `src/cks_picks_cfb/inference/weekly.py`; and
resumable operations are owned by `src/cks_picks_cfb/ops/`.

Named research compatibility covers the certified R1 foundation
`r1-full-corpus-20260831-5f2a384`, fixed rating measurements and states,
candidate-v1 shadow evaluation at `ac1fba1`, completed R2 prior result
`r2-prior-20260904-4c6e610`, and direct early-game candidate generation and
evaluation. Their exact required paths are recorded in the manifest.

## Starting validation

| Check | Baseline result |
|---|---|
| Worktree | Clean at `b930066` |
| Full Python suite | 666 passed, 2 skipped |
| Focused compatibility suite | 84 passed |
| Ruff | Passed |
| Strict MkDocs build | Passed |
| Web lint, typecheck, build | Passed |
| Contract synchronization | Failed only for missing `FIU → Florida International` copies |

The FIU discrepancy was pre-existing drift: canonical `contracts/teams.py`
contained the mapping while `contracts/teams.ts`, `web/src/lib/teams.ts`,
`scripts/pipeline/publish_to_db.py`, and `scripts/pipeline/publish_review.py`
did not. Phase 0 synchronizes those four copies without changing another team
mapping.

## Deterministic compatibility assertions

The checked-in fixtures remain the immutable comparison mechanism:

- V3 team-score derivation produces spread `7.0` and total `49.0`.
- Frozen blend routing produces spread `15.0`.
- Weekly inference preserves regime routing and spread sign behavior.
- Reconstructed research manifests remain blocked from production bundle
  loading.

Prediction differences are never treated as volatile output. Only execution
timestamps and non-semantic logs may be excluded from an operational diff.

## Credential boundary

Contract validation, boundary checks, fixture-based inference, Python tests,
Ruff, MkDocs, web lint/typecheck/build, and CLI `--help` checks run offline.
Real R2 catalog access, source capture, Neon publication, deployment, and live
weekly operations require configured credentials and are outside Phase 0.
The web build may require normal host execution because Turbopack opens a local
worker port; that host requirement is environmental rather than a product
failure.

## Final validation

| Check | Final result |
|---|---|
| Contract and boundary focus | 19 passed |
| Named benchmark CLI smoke | 7 of 7 `--help` commands passed |
| Focused compatibility suite | 89 passed |
| Contract synchronization | Passed |
| Ruff | Passed |
| Full Python suite | 673 passed, 2 skipped |
| Strict MkDocs build | Passed |
| Web lint | Passed |
| Web typecheck | Passed |
| Web production build | Passed; 338 logos synchronized with no tracked diff |
| Deterministic inference | Existing exact fixture assertions passed unchanged |
| `git diff --check` | Passed |

The first CLI smoke invocation through `uv` could not inspect its user cache
inside the filesystem sandbox. The same read-only commands all passed with the
repository's `.venv/bin/python`; this is an execution-environment limitation,
not a command failure. No credentialed or state-mutating check was run.

Phase 1 may start from
`docs/plans/2026-09-05/01-data-and-evidence-audit.md`. It must first verify the
storage backend needed for that task and resolve manifests/catalog entries
before reading datasets. Contract synchronization, repository boundaries,
supported production interfaces, and deterministic fixture outputs are all
green at Phase 0 close.
