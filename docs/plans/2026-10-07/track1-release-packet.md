# Track 1 release preparation packet — PROMOTED 2026-10-07 (see the final section; earlier text below is the pre-promotion record)

- **Status:** Implemented (Evidence packet; promoted 2026-10-07. Execution authority is [01-track1-production-promotion.md](01-track1-production-promotion.md))

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
- **CI:** run `37641359773` on `0cd0a3c0`: all four jobs succeeded. Lint and contracts 28s; Web 1m54s; Python tests 10m21s (parallel 1,987 passed and 2 skipped; rating publication 7 passed; PostgreSQL 23 passed; coverage gate "Required test coverage of 60.0% reached. Total coverage: 65.96%"); 6B rebuild flow 34 passed in 9m52s. Details: `session_logs/2026-10-07/03-pre-week6-audit.md`.
- **Vercel Preview:** the GitHub check for PR head `0cd0a3c0` is `SUCCESS`: [inspect URL](https://vercel.com/connorkitchings-projects/c-ks-picks-cfb/4QA4B4HxvHmUSDrhUCtvbMV6XJFd). That is the inspect link GitHub reports; the `dpl_` deployment ID and the deployed URL were not captured, and the deployment was not opened. A successful build is not route verification.
- **Web code added after this packet's review:** `web/src/app/performance/page.tsx`, `web/src/lib/performance-sections.ts` (new), `web/src/lib/performance-sections.test.ts` (new) and `web/package.json` (test registration). The 19-file web review and `track1-evidence/candidate-files.json` predate these four files and do not cover them. Local checks that did run: web lint, typecheck, 139 publication tests (1 skipped), and the Performance Playwright spec (5 passed, fixture mode). No test renders the prospective-unavailable card; it shows a fixed message only.
- **Pipeline code in the candidate that is not part of the web deployment:** `scripts/pipeline/freeze_week.py`, `Makefile` (`freeze-week` forwards `DECISION_REF`), and a message fix in `select_v5_intended_update_batch.py`.

**Gates still open, unchanged:** (3) real-data verification of the deployed Preview with the restricted Preview web login and fixture mode off, including `/performance`, now carrying the web change above; (4) recapture of refs, deployment, source hashes, venue diff, grants and serving fingerprints; (5) the separate venue-publication and main-promotion decisions. Production registration provenance (who ran the Week 5 registration, and when) is also unresolved. The packet remains **HOLD**; `candidate-files.json` should be regenerated against `0cd0a3c0` when the packet is re-bound.

## Update after Preview verification and recapture (2026-10-07, 16:15Z)

Full detail and evidence: [`track1-recapture-0cd0a3c0/summary.md`](track1-recapture-0cd0a3c0/summary.md). The packet binds to the code SHA `0cd0a3c0`; docs-only commits after it change no shipped file (user-accepted binding). The hold is unchanged.

- **Deployment:** GitHub deployment `6913424276` (Preview, sha `0cd0a3c0`, success) at `https://c-ks-picks-8s2lcbd0y-connorkitchings-projects.vercel.app`; no deployment protection. The `dpl_` ID is still not captured (user-run `vercel inspect`).
- **Gate 3, real-data routes: passed at the HTML level, identity not verified.** `/api/health`, `/`, `/results`, `/performance`, `/ratings` and `/matchup/401856819` returned 200 and their figures match the audit (Week 5 28-27-1 spreads and 25-30-1 totals, 56 graded; replay Weeks 0-4 100-112-3 and 112-102-0; the prospective section shows Week 5 only, labeled retrospectively attested, with no latest-run fallback). Fixture mode is off (observed). **The restricted `cks_preview_web` database login is not verified**: Preview and Production hold identical data, so the pages cannot show which database they read. Not checked: browser rendering, phone width, other matchups, a lineage-mismatch game, the unavailable card.
- **Gate 4, recapture: done.** New candidate hashes for `0cd0a3c0` (the original `candidate-files.json` is kept as history; 5 of its 6 hashes unchanged, `web/package.json` changed); serving fingerprints unchanged since 14:34Z in both environments; the pinned Production venue dry run reproduces the same inputs and 271/271 city coverage; Production `game_venues` still equals the captured before and proposed rows, so the business diff is empty (an apply would still rewrite `updated_at` on 271 rows); `main` is `562319aa` and its Production deployment URL still matches the rollback target (`dpl_` not re-read).
- **Production registration provenance: time known, operator unknown.** R2 wrote the Production attestation at 2026-10-07T03:22:45Z (23:22:45 EDT on 10-06), about 2.5 minutes after commit `491774c1`, which still called it a later gate. Who ran it and under what authorization is not recorded; the operator's statement is needed.

**Still open before Decisions A and B:** the Preview web database role and `dpl_` ID (user, from Vercel); optionally a browser pass at phone width and a lineage-mismatch matchup; the registration operator statement. Decision A (venue upsert) and Decision B (promote PR #2) remain the user's. Observation for Decision A: the apply changes no venue content.

## Update after Vercel inspection (2026-10-07, after 16:15Z)

Details in [`track1-recapture-0cd0a3c0/summary.md`](track1-recapture-0cd0a3c0/summary.md). The packet remains **HOLD**; the two decisions are the user's.

- **Agent-verified with the Vercel CLI (read-only):** Preview deployment `dpl_4QA4B4HxvHmUSDrhUCtvbMV6XJFd` (target preview, Ready, built from `0cd0a3c0`); the Preview environment has no `CFB_UI_TEST_MODE` variable (fixture mode unset) and `CFB_PUBLICATION_MODE=predictions`; the rollback target `dpl_FiycAhixbCrDsZK638CVXtdq9XNM` is a Ready production deployment from 2026-10-04 and matches the recorded URL.
- **Reported, not verified by the agent:** the user's message states the Preview `DATABASE_URL` is bound to `cks_preview_web`. `vercel env ls` shows only "Encrypted", so it cannot confirm this; the role must be read from the connection itself.
- **Production registration:** the user's message attributes it to a manual run by the repository owner after the Stage 7A validation pass, at 23:22:45 EDT on 2026-10-06 (the R2 write time). Recorded as reported; the user should confirm it in their own words.
- **Gate 3** is therefore passed at the HTML level with the database-role item still open; **gate 4** is done. Decision A observation: the apply changes no venue content and would rewrite `updated_at` on 271 rows. Decision B: a GitHub merge of PR #2 merges `origin/dev` (`0cd0a3c0`, the verified head); a local fast-forward of `main` to local `dev` would also publish the unpushed docs commit `119d7ae7` and any later local commits, whose CI has not run.

## User confirmations and decisions (2026-10-07)

Stated by the user in the first person; recorded here as the user's statements. This section supersedes the "reported" wording above for the registration operator. Nothing in this section was executed by the agent.

- **Production registration operator:** the user confirms they manually executed the Week 5 Production prospective registration on 2026-10-06 at about 23:22 EDT, following the Stage 7A validation pass, and asked that it be recorded as verified and authorized by them. The R2 write time (23:22:45 EDT) is consistent with this. No other record corroborates the operator; the confirmation is the user's own statement. The provenance item is closed on that basis.
- **Preview database role:** accepted by the user as an **unverified report**. No secret is to be pulled to disk. The user's stated basis for functional isolation is the observed non-fixture data and the matching audit numbers; as recorded above, those cannot show which database the Preview reads, so the role remains unverified and this packet does not claim otherwise.
- **Decision A, Production venue upsert: SKIP.** Production `game_venues` already holds all 271 games with cities and the business diff is empty; no write that only changes `updated_at` will be performed.
- **Decision B, promotion: PROMOTE via the GitHub PR #2 merge at head `0cd0a3c0`**, so that `main` receives the exact commit that passed CI run `37641359773`. The local unpushed docs commit(s) stay on `dev`. Checked at 16:30Z: PR #2 head `0cd0a3c0`, base `main`, state OPEN, mergeable, merge state CLEAN, all required-looking checks SUCCESS (Python lint and contracts, Python tests, 6B rebuild flow, Web, Vercel), `main` unprotected, `main` is an ancestor of `origin/dev`.
- **Execution notes for the user (not performed by the agent):** (1) Merge on GitHub **before** pushing any further commit to `dev`; a push changes the PR head and starts a new CI run. (2) GitHub's merge button creates a merge commit on `main` (a new SHA with the same tree as `0cd0a3c0`), so Vercel's Production deployment will report that merge SHA, not `0cd0a3c0`; "Rebase and merge" would rewrite the commits instead. To make `main` equal `0cd0a3c0` exactly, a user-run `git push origin 0cd0a3c0:main` fast-forwards it (PR #2 then shows as merged); this matches the AGENTS.md rule to fast-forward when possible. (3) After the deploy, check that Vercel's Production deployment reports the expected SHA, then `/api/health`, Picks, Results, Performance and a representative matchup on Production, and keep the rollback target `dpl_FiycAhixbCrDsZK638CVXtdq9XNM` (commit `562319aa`). A deployment rollback does not restore database venues; no venue write is planned.
- **Open after promotion:** the Preview database role remains unverified (accepted); the `dpl_` ID of the new Production deployment and post-deploy route results are to be recorded after the user promotes.

## Promotion executed and verified (2026-10-07)

User-run: `git push origin 0cd0a3c0:main` (fast-forward from `562319aa`); PR #2 shows MERGED. Verified afterwards by the agent, read-only (details and evidence in [`track1-recapture-0cd0a3c0/summary.md`](track1-recapture-0cd0a3c0/summary.md), section 7):

- `origin/main` is exactly `0cd0a3c0`; `origin/dev` is `8271bbdd` (docs-only commits on top, not part of the release).
- Production deployment `dpl_25cfxMwDLqXRkphiPQCvT9Db18sY`: target production, Ready, created 12:24:38 EDT, aliased `c-ks-picks-cfb.vercel.app`. Rollback target `dpl_FiycAhixbCrDsZK638CVXtdq9XNM` (`562319aa`) retained.
- Live routes return 200 and match the audited Week 5 and replay numbers; the Performance page has the same 270 graded-pick records as the verified Preview. Production matchup pages show the documented pre-fix team stats (PPA/play dash; some rates differ).
- Decision A (venue upsert) was skipped; no database, R2 or serving write took place in this release. The Preview database role stays an accepted unverified report.
- No rollback was needed or performed. Status: this packet is no longer on HOLD; remaining items are the Production team-stats republish (Window 1, separate) and the unverified Preview role.

## Rollback procedure retained for later review

If the separately authorized future promotion fails, restore traffic to the captured immediately previous Production deployment using Vercel's [documented rollback procedure](https://vercel.com/docs/deployments/rollback-production-deployment): user-run `vercel rollback https://c-ks-picks-32ixekgj0-connorkitchings-projects.vercel.app`, followed by deployment/status and affected route/health verification. Confirm the target remains the immediately previous deployment (Hobby plan constraint) when approval is requested. Reconcile branch/deployed state through a separately reviewed user-run Git correction. No rollback was performed.

A deployment rollback does not restore database venues. Compare the retained before payload and obtain a separate venue repair decision if an approved future write is wrong. Do not invoke Stage 7B serving rollback. Evidence is checksummed in [the manifest](track1-evidence/checksums.json); sources and serving state must be recaptured before any later approval.
