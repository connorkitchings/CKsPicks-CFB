# Stage 7B attestation implementation evidence — 2026-10-06

Authority: [Stage 7B](02-stage7b-exact-release-and-cutover.md), Contract 04 Amendment 4 and normative Appendix B. This is an implementation/evidence report, not a registration decision or executable release packet. The [historical preflight hold](stage7b-preflight-hold.md) is preserved unchanged.

## Delivered boundary

The Week 5-only builder creates the real current-time `v5_legacy_freeze_attestation_v1`; callers cannot supply its creation timestamp. The independent verifier re-reads original database records and immutable bytes, including the complete ordered selection timeline, exact freeze activation, successful freeze pipeline/step, prediction identities, contemporaneous games-v2 schedule and current slate schedule. It checks retained schedule capture time, historical Git source bytes, canonical content checksum, raw object hashes, environment and explicit evidence kind. This is content integrity, not cryptographic signer authentication.

The user-run registration command defaults to a read-only serializable dry run. Apply requires the exact environment's restricted pipeline identity, matching R2 configuration, an existing prospective schema and a distinct user registration decision. It retains content-addressed source snapshots and inserts only the Week 5 designation with readback. It does not update existing designations. Exact retries retain the original attestation creation time and perform zero remote writes. R2 objects can remain as unused audit evidence if the database transaction fails; no cross-storage atomicity is claimed.

V2 packet validation, preflight and locked apply verify every prospective object; legacy evidence requires a live cursor and source re-derivation. A later cutover requires all completed prospective weeks beginning at Week 5. Performance query validation rejects unknown URI kinds; audit cards disclose retrospective attestation and the absence of a contemporaneous receipt. The web label relies on constrained URI kind, not a claim of content or cryptographic verification by the web identity.

## Fresh environment evidence

Baseline: clean `dev`, `f80ce990a3d36c30e8468bd8a02725d64dbd3f49`. Evidence was re-captured using read-only database startup settings and read-only R2 storage; previous snapshots were not used as current authority. Credentials were verified present and were never printed. No repository `data/` directory was used.

- Database captures: 2026-10-06 22:46:04Z / 22:46:09Z (6:46 p.m. Eastern), Preview / Production respectively. Both current/session users match their exact restricted pipeline login. Both have six selected weeks and no active current-week run. These observations do not choose cutover N or update the status authority.
- All recorded migration checksums match repository bytes. Preview is through 0024, with no prospective or revocation rows. Production is through 0022; both new tables remain absent. No migrations were applied.
- Effective role privileges were read afresh at approximately 22:51:48Z / 22:51:52Z. Restricted pipeline identities have SELECT-only approval/authorization access; Preview pipeline has prospective SELECT/INSERT/UPDATE but no DELETE and read-only revocations; Preview web has read-only prospective access and no revocation access. The authorization group has SELECT/INSERT-only revocation grants. Administrative owners retain administrative privileges; this does not certify a restricted authorizer login session or Production schema parity.
- Production has no running/pending pipeline row. Preview has one retained running row with null lease owner/expiry, which is not evidence of an active valid release lease. No lease was acquired or modified.
- Fresh R2 reads reproduce the environment-specific original prediction manifest hashes and the corrected Preview 6B root raw hash in the historical hold report. Original prediction CSV and retained schedule bytes were additionally hashed in each environment. No remote object was created or changed.

## Evidence gate results

**Preview: held.** The original freeze activation and selection history are present, but the complete queried Week 5 pipeline ledger contains no successful matching `freeze-week` pipeline/step for its original freeze. The actual command's read-only dry run rejects this evidence. Appendix B requires that record; a direct freeze activation cannot silently substitute for it. Recover authentic retained evidence or return to Contract 04 for a precise decision on this environment-specific conflict. No attestation candidate is represented as registration-ready.

**Production: source re-derivation passes, registration still held.** The original pipeline/step, freeze activation, last pre-kickoff selection, original prediction hashes, pre-freeze schedule capture, current kickoff cross-check and historical freeze code were verified using the implemented full verifier against fresh read-only sources. Diagnostic source snapshots stayed in memory; no registration candidate was persisted or written remotely. Production still lacks migrations 0023/0024 and the separately authorized registration decision. Production evidence cannot substitute for Preview evidence.

**Release preparation: held.** No N was selected; no executable release/rollback packet or authorization was assembled. Fresh provider schedule/quote reconciliation, certified-finals stabilization, corrected pending-run eligibility, exact authorizer sessions, real web-query parity, and all live rehearsal/release/freeze/rollback operations remain pending. The next refresh is after the Week 5 evidence and schema prerequisites are resolved, immediately before packet preparation; capture the complete provider schedule and both quote types then. Stored schedule reads do not certify fresh quote availability. No migration, R2 publication, attestation/authorization registration, selection, current-week/stat change, or freeze occurred.

## Retained diagnostic files

These temporary files contain source audit records, not credentials. Re-capture before packet preparation; raw hashes identify this session only.

| File | Raw SHA-256 |
| --- | --- |
| `/private/tmp/cks-stage7b-preview-preflight.json` | `03ab108c3bbbb0f078370363ff1cc5ffe2839385f1e838aad086158545063fce` |
| `/private/tmp/cks-stage7b-production-preflight.json` | `a17f533b103080c63ac20ec129dd3bcd846a4e1494a5b1c1ca146a9487261421` |
| `/private/tmp/stage7b-preview-grants.json` | `4dac081f8f9ad60915d49417d946c0468382c74c47a3171c109f0f6fd706804b` |
| `/private/tmp/stage7b-production-grants.json` | `df2eb7fc748c0ac3cad88577fff82753f64df89b87a6fa1702891bbc23b8a206` |
| `/private/tmp/stage7b-preview-source-verification.json` | `040ea84ae86f5d6a4f908beb6571e6014ddf29ef154c2f50a65acfd563632ed2` |
| `/private/tmp/stage7b-production-source-verification.json` | `bce4c5a81399a8e9c45fab333a7159d8e51c25c6e6d7910cbf85ba2b0f1cc84f` |

Validation and the final implementation handoff are in the [session log](../../../session_logs/2026-10-06/10-stage7b-attestation-implementation.md). Stage 7B remains In Progress; its live definition-of-done gates are not satisfied.
