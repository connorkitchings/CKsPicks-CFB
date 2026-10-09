# Stage 7B preflight hold — 2026-10-06

- **Status:** In Progress (Evidence packet; historical hold record, preserved unchanged. Execution authority is the [Stage 7B contract](02-stage7b-exact-release-and-cutover.md))

Authority: [approved Stage 7B contract](02-stage7b-exact-release-and-cutover.md), execution sequence 1–2 and stop conditions. This is an evidence report, not a release packet, authorization, or amendment.

Implementation baseline: `dev`, clean at `d8bbe5b28f342cb91d5305bc620ea137b5d19921`. The plan and Stage 7A close-out are committed. No implementation files were changed. Backend `r2` and required credentials for each environment were verified present without printing credentials.

## Fresh database observations

Read-only transactions used the approved Keychain wrappers. Capture times are 2026-10-06 20:26:05Z (Preview) and 20:26:06Z (Production), approximately 4:26 p.m. Eastern. Production initially timed out with an additional connection-startup setting; retry with the working read-only startup setting succeeded. Connectivity is not an outstanding blocker.

| Observation | Preview | Production |
| --- | --- | --- |
| `session_user` and `current_user` | Both `cks_preview_pipeline` | Both `cks_prod_pipeline` |
| Applied migration ledger | Through 0024; every recorded raw checksum matches repository bytes | Through 0022; every recorded raw checksum matches repository bytes |
| `current_week` | Season 2026, Week 6, no active run | Season 2026, Week 6, no active run |
| Public selections | Six, covering Weeks 0–5 | Six, covering Weeks 0–5 |
| Prospective records | Table present; zero rows | Table absent |
| Revocations | Table present; zero rows | Table absent |
| Effective approval/authorization privileges of pipeline login | SELECT only; INSERT/UPDATE/DELETE denied | SELECT only; INSERT/UPDATE/DELETE denied |

Production's unapplied 0023/0024 migrations are the expected Stage 7A handoff, not unexplained ledger drift. They require a separately authorized migration operation and real grant/schema readback before release. No migration or role membership was applied here. Authorizer/web effective-grant verification and a full release preflight remain pending; these pipeline reads do not certify all role identities.

Both snapshots retain current selections, run records, selection history, activation history, pipeline definitions/steps, existing authorization records and stored schedule. Live run identities remain in [status](../../status.md); raw audit snapshots retain the exact records locally. No concrete `N` was chosen. Fresh provider schedule/quotes, completed-week stabilization and corrected pending-run eligibility were not certified after the evidence stop, so these snapshots cannot support packet authorization.

## Original Week 5 evidence

The Production database retains the original live run, its pre-kickoff public selection at 2026-09-30 03:28:26.132104Z, and its freeze at **2026-09-30 12:34:06.200521Z**. The same-slate minimum kickoff across 56 predictions is **2026-10-02 00:00:00Z**. The original freeze activation contains `freeze_coverage_complete=true`. Its operator pipeline and freeze step are succeeded, with one attempt and no error. The step's `output_refs` contains the command arguments and return code 0; it contains no signed freeze receipt URI/hash or retained freeze payload.

Preview retains its own earlier freeze at 2026-09-29 20:43:53.376950Z and separate rehearsal/rollback selection history. This is environment-specific evidence and cannot be substituted for the Production freeze.

Read-only R2 inventories found:

- Zero objects under the prospective Week 5 receipt prefix in either environment.
- Zero objects under the original Production freeze pipeline's artifact prefix in either environment.
- The original Week 5 prediction manifest and CSV in both environment-specific prediction prefixes. These prediction manifests have no `manifest_sha256` content signature and no original freeze receipt; they are not signed freeze evidence.
- Original Preview prediction-manifest raw SHA-256 `d74262fe5a51d7510bcce80ab82f7f116730ac00d3765242c005d56aaf551c0f`, matching the Stage 6B source pin. Production prediction-manifest raw SHA-256 `490c09b4cb67b6161a91e5920bd6091dae28619a08edc5247ea5ebb033c6bc8d`.

The historical freeze implementation at `acbd9c6` updates the run and activation ledger and commits; it does not persist a signed immutable freeze receipt. The historical subprocess step records only command/return code. Current `register_prospective_freeze` creates a new receipt, and direct freeze returns early for an already frozen/scored run. Neither is a verified import route for the missing original receipt. Creating a newly signed object using the old freeze time would not recover original signed bytes and is not authorized by this contract.

This bounded search establishes **receipt provenance unresolved**, not proof that no authentic receipt exists anywhere. Database timestamps, selection history, current grades and unsigned manifests are useful corroboration; they cannot silently replace the contract's original signed receipt prerequisite.

## Independent corrected-foundation readback

The Preview Stage 6B root was fetched and its existing canonical-content checksum verified. Its **raw-byte SHA-256** is `6fb59797e35c05a6657219e4e41e0b3834187f1ee88971b1d78045c96c78e6cf`; its internal **`manifest_sha256`** is `32105bbe8dbc97328557406347cbf5c55c727ad38d186a352089fe0d5aaf8d45`. The close-out record's `32105bbe…` describes the internal checksum, not the raw-byte hash. Packet artifact refs must use the raw hash. This distinction is not evidence of changed root bytes. The verified root carries build/publisher `eca6871d727060adf8612bd7d8769c29d5243579` and verification checksum `e462ae05408999c4e7d7fa61519b134f97a074dc8acb4d714680d6048b525aaa`.

No complete source certification or release eligibility is claimed from this single-root readback. The full root/object/catalog checks belong to the eventual fresh packet preflight.

## Gate decision and smallest resolution

**Hold before release packet preparation, historical registration, authorization and serving operations.** The expected prerequisite is an authenticated original signed Week 5 freeze receipt and a valid registration route. The actual retained evidence checked here has the original pre-kickoff database history and prediction artifacts but no original signed freeze receipt. Stage 7B remains In Progress; all release definition-of-done items remain open.

Resume only with either:

1. The authentic original receipt's exact immutable location and hash, followed by verification of its bytes/content checksum, original run, environment, selection history, timestamp and kickoff, plus a contract-conformant operator registration route; or
2. A Sol/Contract 04 amendment explicitly adjudicating legacy evidence and defining a historical registration route if the original signed receipt did not exist. Any new audit attestation must retain its actual creation time and exact contemporaneous source records; it must not masquerade as an original receipt or rewrite the original freeze. This changes an acceptance prerequisite and cannot be approved mechanically by this implementation task.

After that resolution, complete the separately authorized Production schema/grant prerequisite, refresh provider schedule and both quote types, determine eligible `N`, and build/review distinct Preview and Production packets. Existing implementation approval grants none of those live write authorizations.

## Retained local evidence

These files contain exact audit records and no credentials; `/private/tmp` is temporary and must be retained or re-captured before a future packet. Their digests are recorded here for comparison, not as release approvals.

| Local file | Raw SHA-256 |
| --- | --- |
| `/private/tmp/cks-stage7b-preview-preflight.json` | `6b52343072b0d9e3a1f2ecf1e21d2ccb263e414239df0c28265f1b74cd8f2180` |
| `/private/tmp/cks-stage7b-production-preflight.json` | `49faff2a031508010d72aaa9645bdfad3f8dd32474b1ba5390c11e0944402e67` |

R2 inventories and copied manifests are in `/private/tmp/cks-stage7b-evidence/`. Read-only helper scripts are `/private/tmp/cks-stage7b-preflight.py` and `/private/tmp/cks-stage7b-r2-evidence.py`; they are investigation aids, not production tools.
