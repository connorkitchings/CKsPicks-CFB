# Mobile and Week 8 Production release

- **Status:** In Progress — Production migrations and release authorized
- **Created:** 2026-10-19
- **Authorization:** Owner requested pushing all completed changes to Production, including Week 8. This authorizes integration/deployment and Week 8 activation, superseding the earlier owner-only Git execution preference for this release. Earlier withholding of chart schema promotion remains a material conflict requiring the explicit amendment below.
- **Implementation log:** `session_logs/2026-10-19/01-production-release-preflight.md`

## Goal and observable completion

Ship the completed mobile web implementation and activate the verified Week 8 slate with Week 7 results in Production. Keep `CFB_CHARTS_ENABLED` unset or `0`; `/charts` must return 404 and no Charts navigation may appear. Preserve existing production publication mode and serving credentials.

## Verified baseline and material conflict

The mobile implementation is complete in the isolated managed `mobile-web-plan` worktree at `b57fabe9` with uncommitted changes and passing final validation. The primary checkout is clean on `dev`. Remote state was fetched. Production Vercel project is `c-ks-picks-cfb`, team `connorkitchings-projects`, root `web/`, deployed from `main`. Its Production variables do not include the Charts flag, which defaults off.

Read-only database inspection on October 19 confirms Preview has migrations through 0026 and Production through 0025. Current `release.py` stages only `charts_v2` candidates; it rejects the retained Week 8 `charts_v1` candidate. New staging therefore needs migration 0027 on Preview and migrations 0026/0027 on Production. Active release IDs and scoreboard remain authoritative only in `docs/status.md`.

## Owner amendment and remaining decision

On 2026-10-19 the owner explicitly approved the migration on Preview and required Charts to remain hidden. This authorizes 0027 on Preview only. Perform this isolated schema step before integration/prepare; do not apply 0026/0027 on Production without its separate explicit approval. Production activation/deployment remain pending the schema prerequisite.

### Remaining Production amendment

Authorize applying the existing reviewed additive migrations `0026_team_chart_tables.sql` and `0027_team_game_yardage.sql` to Production, and 0027 to Preview. This installs serving projection tables while the public Charts feature stays disabled. Do not bypass the staging-set guard or modify migrations/release policy. A missing credential, checksum discrepancy or unexpected schema difference stops the release.

## Ordered execution after amendment approval

1. Inspect the exact mobile diff and existing migration checksums/grants. Verify intended database identities and migration ledgers using read-only queries and the documented Keychain wrappers. Verify R2 backend and required Preview/source credentials are present without printing values before any data I/O.
2. Record owner amendment authorization in this contract. Preserve separate planning/mobile implementation commits, create a `codex/` release branch in the existing isolated worktree, and commit only reviewed changes. Integrate via `dev` before `main`; do not force-push or discard unrelated work.
3. Verify schema backups/recovery availability and apply only pending checksummed migrations using the sanctioned migrator against the verified Preview and Production targets. Read back table constraints, grants and migration checksums. Keep existing active releases untouched at this step. Existing rollback retains the prior release; additive tables need not be dropped.
4. Recheck the full 56-game Week 8 schedule and fresh spread/total coverage, recording capture time, missing IDs, next refresh and release gates. Do not infer current provider absence from retained nulls. Use the weekly runbook for any required refresh/revision rebuild. Preserve historical grading and forecast provenance. Compare the rebuilt core projections with the accepted Preview snapshot at the same cutoff; if newly captured inputs legitimately change the candidate, document and independently verify those changes rather than claiming parity.
5. Commit final pinned manifest/exception inputs before prepare. Run appropriate contracts, Python release/projection tests and web checks on the actual combined code. Prepare from a clean tree using `make season-prepare`, valid nonfuture cutoff before first kickoff, exact exceptions, and the existing model. Require all `charts_v2` verification checks. No commit may occur between prepare and the last release.
6. Activate the candidate on Preview with operator-pinned payload SHA and expected previous release. Verify independent read-only Preview proof and real-data Picks, Results, Ratings, Performance and Matchup behavior with mobile layouts and Charts off. Fixture validation does not substitute for this readback.
7. Activate the exact same candidate/commit on Production via `make season-release ENV=production`, with freshly read expected previous release. Verify active release, full slate, completed-week results and cumulative record by read-only readback. Do not use direct legacy publication/current-week writes.
8. Fast-forward `dev` then `main`, push under the owner's release authorization, and monitor GitHub/Vercel until the exact deployed commit is Ready. Preserve Charts off and existing publication settings. Validate live core routes and `/api/health`, mobile first-card clearance and disabled `/charts`.
9. Update `docs/status.md` to the verified actual state, remove stale pending-week narratives, finish release log and contract/index, validate docs and whitespace, and commit/push post-release documentation. Record any failed or partial step plainly.

## Rollback and stop conditions

Do not roll back automatically without owner authorization. An activation failure before transaction commit leaves prior selection intact. A post-activation defect requires the documented owner rollback path and prior verified release, or Vercel rollback for a deployment defect. Stop on numerical drift without explanation, incomplete verification, missing proof/credentials, unexpected migrations, dirty prepare, changed commit, build failure or mismatch between deployed and requested code. No model research, 2025 backfill, Charts publication or unrelated worktree integration is included.

## Validation and definition of done

The completed mobile contract already records lint/typecheck/build, 245 unit tests, 123 Chromium, 79 WebKit, 12 gates and 120 rendered combinations. Repeat affected checks if the combined source or configuration changes. Release-specific requirements are migration readback, all candidate checks, real Preview rehearsal, exact Production readback, deployment Ready, live core journeys/health and Charts refusal, documentation build and `git diff --check`. Mark Implemented only once all pass.


## Preview migration completion — 2026-10-19

Applied only migration 0027 through `migrate_db.py --database-env DATABASE_URL` under the verified Preview migrator wrapper. Historical checksums matched and 0027 was the sole pending migration. Retained a private dependency-schema dump and immutable-function definition before apply. A full schema dump was unavailable to the scoped migrator because an unrelated historical table denies SELECT; no permissions were expanded. Installed the compatible keg-only libpq 18 client to avoid the existing pg_dump 14/server 18 mismatch, without changing PATH.

Read-only readback passed: migration checksum/history, exact columns and nullability, both primary keys, release foreign key with DELETE RESTRICT, enabled immutable-projection trigger, effective web/pipeline permissions and absence of PUBLIC grants. Both new tables remain empty and the existing Preview active release is unchanged. No prepare, new candidate activation, Production mutation, commit/push or deployment occurred.

Charts verification: local fixture `/charts` returns HTTP 404. Current Production returns its 404/not-found content with no Charts link or chart content, but HTTP 200 under its existing streamed response; this is recorded accurately rather than claimed as a transport-level 404. This migration did not change the deployed app. The final release must verify the intended gate on the new deployment.

Production 0026/0027 remain pending explicit approval. Continue with the ordered release contract once that decision is supplied; do not treat Preview-only approval as Production schema authorization.


## Production authorization and credential blocker — 2026-10-19

Owner explicitly authorized proceeding with the Production migration in chat. This approves the existing additive migrations 0026/0027 while Charts remains hidden, in addition to the earlier mobile/Week 8 release authorization. No further migration approval is needed.

The sanctioned `with_production_owner_env.sh /usr/bin/true` preflight exited 66: Keychain item `ckspicks-cfb/production/owner-url`, account `cks_prod_owner`, is missing. No Production write occurred. Automatic approval review rejected checking local environment files for alternate credentials because that would bypass the documented owner-authentication boundary. Do not work around that rejection; resume through the sanctioned owner wrapper after the owner provisions the documented item. Existing Preview migration and mobile verification remain complete. Production migration, candidate preparation/activation and deployment are still pending.


## Credential provisioning follow-up — 2026-10-19

Owner provisioned the sanctioned Keychain item. Its hidden-input prompt stored only 128 characters, truncating the final `channel_binding` query option. A narrowly scoped repair restores only `ding=require`, after confirming the stored address matches the independently verified Production pipeline target and the reconstructed URL authenticates with an owner role. Native Keychain APIs avoid passwords in arguments or logs. No alternate credential sourcing is involved.

Execution checklist:
- [x] Owner authorization for Production 0026/0027 and full mobile/Week 8 release.
- [x] Production identity/checksum/backup preflight and schema apply/readback.
- [ ] Commit reviewed mobile and release documents in the isolated worktree.
- [ ] Fresh Week 8 schedule/market coverage and pinned revision inputs.
- [ ] Clean candidate preparation and all checks.
- [ ] Real Preview activation/rehearsal and exact Production activation/readback.
- [ ] dev/main integration, deployment and live verification.
- [ ] Final status/session documentation and validation.


## Production migration completion — 2026-10-19

The sanctioned owner credential now authenticates to the same endpoint/database as the restricted Production pipeline credential. Retained full schema backup and migration ledger under `/private/tmp/ckspicks-production-0026-0027/`; existing migration checksums matched and exactly 0026/0027 were pending. Applied both through the repository migration runner. Read-only readback passed all eight new table shapes against SQL column names, keys, foreign keys, enabled immutable triggers, effective base/Production web and pipeline permissions, absence of PUBLIC grants and empty new tables. The active Production release is unchanged. A diagnostic's initial manually counted column total was corrected to exact SQL-name comparison; no migration correction was needed. Charts settings remain untouched and hidden. Release integration/prepare/activation/deployment are next under existing authorization.
