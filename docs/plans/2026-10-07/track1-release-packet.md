# Track 1 release preparation packet — HOLD

- **Contract:** [approved Track 1 plan](01-track1-production-promotion.md).
- **Capture date:** 2026-10-07, 08:43–08:56 EDT (12:43–12:56 UTC).
- **Decision:** Preparation only. No Production venue apply, deployment, Git mutation, or Stage 7B serving operation is authorized or performed.
- **Candidate:** Local base `1405f33b4853f7ac15f6050068e5e21f8c0e9f85` plus uncommitted implementation. No final candidate commit exists. [Candidate file hashes](track1-evidence/candidate-files.json) bind the review state, not a deployable SHA.

## Venue and serving evidence

Restricted pipeline identities were freshly verified in both environments with read-only transactions. The earlier missing-Keychain observation was a sandbox limitation; approved host access succeeded. R2 backend and environment-specific credentials were verified without revealing values. Existing Week 5 designations were independently verified against immutable receipt/source bytes and live original records with `ReadOnlyStorage`.

| Input | Exact version | Content SHA-256 |
| --- | --- | --- |
| Silver games | `31a337df6cf49f1578457ec6` | `f2cdccedbc81c99841c5841151af83ba35ca988adbecc15bc05a2e07868ef788` |
| Silver venues | `b569d242e8c4c53b416bfe14` | `bee1f3c7b731cb24265bd7fa86233e8232f83dfd6235dfbbfe1d51dfeaf7c856` |

The newest validated 2026 games version covers all **271 current Production database games**, independently recaptured rather than inherited from an old count. Preview has the same coverage. All 271 have unique resolved venues and cities; 269 also have states. Zero absent games, unresolved IDs, or ambiguous source duplicates. The business-column insert/update diff is **empty in both environments**. Applying the existing upsert would still rewrite `updated_at` for all rows, so it is not a zero-write operation and remains gated.

The pinned Production dry run passed:

```bash
PYTHONPATH=src:. zsh scripts/ops/with_production_pipeline_env.sh \
  .venv/bin/python scripts/pipeline/publish_game_venues.py \
  --season 2026 --environment production \
  --games-version 31a337df6cf49f1578457ec6 \
  --venues-version b569d242e8c4c53b416bfe14 \
  --require-city --dry-run
```

The raw captures retain every before row, proposed row, complete current game set, proposed diff, migration ledger, role privileges and serving fingerprints: [Production](track1-evidence/production-capture.json), [Preview](track1-evidence/preview-capture.json). The database game set ends October 4 and has no Week 6 game rows despite the current-week pointer being Week 6. This is the observed serving baseline; these captures do not certify provider-wide Week 6 schedule/line coverage or authorize week opening.

Migration ledger entries through 0024 match repository raw bytes in both environments. Actual `cks_prod_web`/`cks_preview_web` effective grants permit SELECT on prospective records, rating snapshots, possession stats and matchup publication tables; INSERT/UPDATE/DELETE are denied. They have public schema USAGE and no ops schema USAGE or revocation-table access. This is effective-role evidence from restricted pipeline queries, not an actual deployed web-login certification. Local `web/.env` contains an owner-role database configuration and was not used to claim restricted real-data web validation.

Independent post-dry-run readbacks show unchanged hashes for current week, selections, system stats, prospective records, venues, team stats, predictions, grades and finals. Current pointer remains `(2026, 6)`; there are six selections and one Week 5 designation per environment. See [Production readback](track1-evidence/production-final-readback.json) and [Preview readback](track1-evidence/preview-final-readback.json). Live run IDs remain in `docs/status.md`; raw evidence snapshots retain their original identities for review.

## Code review and validation

Reviewed all 19 changed `main..HEAD` web files, plus this session's query repair. Changes separate selected replay from designated prospective Performance reads, disclose retrospective Week 5 attestation, and guard matchup model sections/sharing on provenance. No web mutation activates Window 2. `.vercelignore` still ships only `web/`, excluding local credentials/build state.

A real-data check reproduced PostgreSQL **42P10** in the new rating provenance `SELECT DISTINCT`: it ordered by unselected `cutoff_utc`. The user explicitly authorized a localized behavior-preserving repair. The extracted production query now includes that ordering field; a regression tests actual Drizzle-generated SQL, cutoff scope and team parameters. The repaired generated SQL passed against both real environments. Original and repaired query evidence is preserved in `track1-evidence/`.

| Check | Result |
| --- | --- |
| Full Python suite | 2,039 passed, 12 skipped; 284.82 seconds |
| Focused venue suite | 19 passed |
| Disposable PostgreSQL migration/batch/attestation/revocation/authorization suite | 32 passed; cluster stopped |
| Full Ruff and changed-file format check | Passed |
| `make contracts-check` | Passed with host uv-cache access |
| Web lint/typecheck/publication tests after repair | Passed; 135 publication tests, one local-DB test skipped in the ordinary run and separately passed |
| Fixture-mode production build after repair | Passed |
| Same-cutoff source query regression with disposable PostgreSQL | 3 passed, no skips |
| Performance/matchup Playwright after repair | 24 passed |
| MkDocs / `git diff --check` | Passed at close-out |

Fixture tests and pipeline SQL checks do not satisfy the required exact-SHA real-data Vercel Preview gate.

## Deployment evidence and unresolved gates

[Vercel evidence](track1-evidence/vercel.json) freshly confirms the project root is `web` and configured Production branch is `main`. Production is Ready at commit `562319aaf0510d840d60806e11c4802ea0c80049`, matching local and remote `main`. Retained rollback target: [current Production deployment](https://c-ks-picks-32ixekgj0-connorkitchings-projects.vercel.app), ID `dpl_FiycAhixbCrDsZK638CVXtdq9XNM`.

Remote `dev` and the deployed Preview still point to `eca6871d727060adf8612bd7d8769c29d5243579`. Fresh GitHub inspection found no open `dev`→`main` PR and no returned CI runs for `dev`. The current Preview cannot validate this uncommitted candidate. No deployment was created by this agent.

**Source ambiguity resolved on reopened implementation pass:** The user explicitly requested binding provenance to the source derivable from the approved read path. `getRatingsAsOf` returns source-tagged rows, and `getWeeklyRatings` pins both current rows and preseason backfills to the owning source. The matchup guard now derives a single nonempty source from the exact two rendered teams and filters provenance to that source. Missing, mixed or ambiguous rendered sources skip the provenance query and remain fail closed; forecast/stat comparison remains unchanged. This implements the existing Stage 7A lineage contract without changing public selection or rating ownership.

The generated source-bound query passed in real Preview and Production, each containing two competing manifests at the representative cutoff. Every returned row belongs to the actual rendered source. A disposable PostgreSQL regression inserts two manifests at the same cutoff and executes actual generated Drizzle SQL; only the rendered manifest's two teams return. Three focused query tests passed, including the database regression. Source-bound evidence is retained in `track1-evidence/*-selected-source-query.json`. The earlier hold is resolved; exact-SHA CI and real restricted-web Preview route verification remain open.

Before release:

1. Source-binding repair and same-cutoff regression are complete. Include them in the committed candidate and verify representative real matchups remain available or deliberately guarded for a documented forecast/stat mismatch.
2. User commits the reviewed code on `dev`, pushes and opens `dev`→`main` PR. Bind a new packet to the exact resulting SHA, green CI and its Vercel Preview deployment.
3. Verify deployed Preview uses the restricted Preview web login, fixture mode is off, and Picks/Results/Performance/matchup routes meet the real-data acceptance criteria.
4. Re-capture refs, deployment, source hashes, complete game set, venue diff, designation/grants and serving fingerprints. Review whether a timestamp-only venue upsert is needed; do not infer authority to skip or apply it.
5. Obtain separate venue-publication and main-promotion decisions only after all gates pass. User executes both operations. Retain the source pins and all before payloads.

## Update after push: committed candidate and CI (2026-10-07, 15:12Z)

The "no final candidate commit exists" statement above is superseded; the earlier text is kept as the record of the capture state. This update does not change the hold.

- **Candidate:** `dev` head `0cd0a3c0` (PR #2, `dev`→`main`, open and mergeable). Commits on the Track 1 commit `a600748f`: `66c71de8` (ruff formatting, Python only), `9042b087` (CI split), `aaf0ca0b` (CI: full-history checkout, 6B flow as its own job), `c6e82848` (freeze: missed deadline recorded before the decision-ref check), `fc57facb` (web: Performance sections load independently), `d100d15e` (audit evidence and log), `0cd0a3c0` (format and lint of the audit scripts; `d100d15e` had failed the formatting check).
- **CI:** run `37641359773` on `0cd0a3c0`: all four jobs succeeded. Lint and contracts 28s; Web 1m54s; Python tests 10m21s (parallel 1,987 passed and 2 skipped; rating publication 7 passed; PostgreSQL 23 passed; coverage gate "Required test coverage of 60.0% reached. Total coverage: 65.96%"); 6B rebuild flow 34 passed in 9m52s. Details: [session log 03](../../../session_logs/2026-10-07/03-pre-week6-audit.md).
- **Vercel Preview:** the GitHub check for PR head `0cd0a3c0` is `SUCCESS`: [inspect URL](https://vercel.com/connorkitchings-projects/c-ks-picks-cfb/4QA4B4HxvHmUSDrhUCtvbMV6XJFd). That is the inspect link GitHub reports; the `dpl_` deployment ID and the deployed URL were not captured, and the deployment was not opened. A successful build is not route verification.
- **Web code added after this packet's review:** `web/src/app/performance/page.tsx`, `web/src/lib/performance-sections.ts` (new), `web/src/lib/performance-sections.test.ts` (new) and `web/package.json` (test registration). The 19-file web review and `track1-evidence/candidate-files.json` predate these four files and do not cover them. Local checks that did run: web lint, typecheck, 139 publication tests (1 skipped), and the Performance Playwright spec (5 passed, fixture mode). No test renders the prospective-unavailable card; it shows a fixed message only.
- **Pipeline code in the candidate that is not part of the web deployment:** `scripts/pipeline/freeze_week.py`, `Makefile` (`freeze-week` forwards `DECISION_REF`), and a message fix in `select_v5_intended_update_batch.py`.

**Gates still open, unchanged:** (3) real-data verification of the deployed Preview with the restricted Preview web login and fixture mode off, including `/performance`, now carrying the web change above; (4) recapture of refs, deployment, source hashes, venue diff, grants and serving fingerprints; (5) the separate venue-publication and main-promotion decisions. Production registration provenance (who ran the Week 5 registration, and when) is also unresolved. The packet remains **HOLD**; `candidate-files.json` should be regenerated against `0cd0a3c0` when the packet is re-bound.

## Rollback procedure retained for later review

If the separately authorized future promotion fails, restore traffic to the captured immediately previous Production deployment using Vercel's [documented rollback procedure](https://vercel.com/docs/deployments/rollback-production-deployment): user-run `vercel rollback https://c-ks-picks-32ixekgj0-connorkitchings-projects.vercel.app`, followed by deployment/status and affected route/health verification. Confirm the target remains the immediately previous deployment (Hobby plan constraint) when approval is requested. Reconcile branch/deployed state through a separately reviewed user-run Git correction. No rollback was performed.

A deployment rollback does not restore database venues. Compare the retained before payload and obtain a separate venue repair decision if an approved future write is wrong. Do not invoke Stage 7B serving rollback. Evidence is checksummed in [the manifest](track1-evidence/checksums.json); sources and serving state must be recaptured before any later approval.
