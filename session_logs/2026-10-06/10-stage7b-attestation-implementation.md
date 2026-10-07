# Session: Stage 7B legacy freeze attestation implementation

## TL;DR
- **Worked On:** Contract 04 Amendment 4 / Appendix B Week 5 legacy attestation, guarded registration, v2 verification and Performance provenance.
- **Outcome:** Local implementation delivered and tested. Fresh Preview source evidence fails the required successful freeze pipeline/step gate; Production full source re-derivation passes but lacks the prospective schema and separate registration decision. No live writes, executable packets or cutover N.
- **Plan Contract:** `docs/plans/2026-10-06/02-stage7b-exact-release-and-cutover.md`
- **Approval / Status:** Explicit fresh implementation handoff for this exact plan, covering implementation/tests/read-only evidence only. In Progress; live definition-of-done gates remain open.
- **Blockers:** Missing Preview original freeze pipeline/step evidence; separately authorized Production 0023/0024 migration and registration; full fresh provider release evidence; exact authorization/rehearsal/release/freeze/rollback decisions.
- **Next:** Recover Preview retained evidence or return to Contract 04 for its environment-specific conflict; do not register or prepare executable packets before that gate is resolved.

## Context and Decisions
- Started on clean `dev`, HEAD `f80ce990a3d36c30e8468bd8a02725d64dbd3f49`. No checkout, staging, commit or other Git mutation.
- Applied `.agent/skills/implement-plan/SKILL.md` and the React best-practices skill to the Performance audit label. Read AGENTS.md, status, the complete Stage 7B contract, Stage 7A authority/close-out, Contract 04 and Appendix B, recent October 4–6 context and the historical preflight hold.
- Verified the R2 backend and required environment credential presence without revealing secrets. Read-only connection startup flags and `ReadOnlyStorage` protected live reads. No repository `data/` path or local durable fallback.
- Re-captured Preview and Production independently. Exact restricted pipeline current/session identities match. Applied migration raw checksums match repository bytes. Preview is through 0024 with no prospective/revocation rows; Production is through 0022 and lacks those tables.
- Verified effective table grants across the actual available roles. Pipeline approval/authorization grants remain SELECT-only. Preview web cannot mutate prospective records or access revocations. Authorizer group revocation grants are SELECT/INSERT-only. Administrative owner privileges are recorded separately, not represented as a restricted authorizer-session certification.
- Preserved `stage7b-preflight-hold.md` unchanged. The current evidence is in `stage7b-attestation-implementation-evidence.md`; its capture times/hashes identify this new session.
- Preview original freeze activation exists but no matching successful original freeze pipeline/step is retained. The implemented actual dry run rejects it. This is the Appendix B source gate, not permission to relax its requirement. Production's pipeline evidence and full independent original source verification pass, but neither can replace Preview's source records.
- No N was selected. Provider schedule/quotes/finals stabilization and corrected pending-run eligibility were not certified after this prerequisite hold. Stored schedule reads and temporary source snapshots are not executable release approval.

## Work Completed
- Built actual-current-time, Week 5-only legacy attestations with explicit retrospective disclosures and canonical content checksum.
- Added independent live source re-derivation, immutable raw hash validation, original prediction identity checks, chronological public selection chain, exact freeze activation/pipeline/step checks and original games-v2 schedule comparison. Retained `kickoff_utc` and pre-freeze `__captured_at` must agree with the complete current original-run slate. Historical Git source bytes and commit time are verified locally.
- Added guarded user-run `register_v5_legacy_freeze_attestation.py`: dry-run/apply, environment/identity/storage/schema guards, bounded original-receipt search, content-addressed source snapshots, insert/readback, conflict rejection and exact zero-write retries. No apply was run.
- Extended v2 validation/preflight/apply to verify all receipt kinds and require live source verification for legacy attestations. Completed prospective Weeks 5 onward cannot be omitted when N advances. Existing ordinary freeze receipts remain supported and unknown URI/schema kinds fail closed.
- Added Performance query validation and explicit audit text for retrospectively attested evidence; no web cryptographic verification claim.
- Fixture tests exercise changed bytes, altered sources, wrong environment, incomplete schedule, missing/failed pipeline, backdating, caller-supplied creation time, registration insert/retry/conflict, unknown web kinds and later-N missing prospective history.
- Independently fetched original prediction manifest/CSV and pinned schedule bytes in both environments and reverified the corrected Preview 6B root. Full Production source verification succeeded without persisting a registration candidate.

## Files Modified
- `src/cks_picks_cfb/ops/prospective_records.py` — Legacy payload, source verifier, kind verifier, insert-only registration helper.
- `scripts/pipeline/register_v5_legacy_freeze_attestation.py` — Guarded separate user registration operation.
- `src/cks_picks_cfb/ops/v5_batch_selection_v2.py` — Receipt verification and completed prospective coverage gate.
- `tests/test_v5_legacy_freeze_attestation.py`, `tests/test_v5_batch_selection_v2.py` — Evidence, retry/conflict and moving-cutover regression tests.
- `web/src/lib/prospective-provenance.ts`, its test, `web/src/lib/v5.ts`, `web/src/components/PerformanceDashboard.tsx`, `web/package.json` — Fail-closed kind labeling and audit disclosure.
- Stage 7B plan and its new implementation evidence report — Current implementation state and open gates.
- This session log.

## Validation
- [x] Full Python runs: initial 2,026 passed / 12 skipped; final rerun 2,028 passed / 12 skipped in 286.87s. The final live-only builder rejection is additionally covered by the final focused run.
- [x] Final focused source/packet/migration/authorization/revocation tests against disposable local PostgreSQL: 31 passed (includes the two previously skipped v2 transaction/race tests).
- [x] Separate focused attestation/v2/authorization/revocation run: 20 passed, two database tests skipped in that non-DB run; isolated DB checks above cover those tests.
- [x] Full Ruff, `make contracts-check`, web lint/typecheck, publication tests (133 passed), fixture-mode build, Performance/matchup Playwright (24 passed).
- [x] Actual Preview read-only command rejects missing original freeze pipeline/step; full Production source re-derivation passes read-only.
- [x] MkDocs and `git diff --check` passed after documentation changes. Final full Ruff also passed. The disposable PostgreSQL cluster was stopped after focused validation.
- [ ] Live registration, schema parity, authorizer sessions, apply/freeze/repin/readback/rollback and actual web-query parity: not authorized/performed; fixtures do not satisfy those gates.

## Amendments and Blockers
- No policy amendment made. The missing Preview source record cannot be substituted with a direct freeze activation or Production evidence under the approved contract.
- Sandbox initially blocked uv cache/macOS configuration access, Turbopack local-port binding and Playwright's loopback server. Reviewed escalated read-only/local validation retries succeeded. No automatic approval rejection remains.
- No source-data/model/schema migration/serving identity changes. A final local guard also rejects replay-class runs; its regression is included in the 31-test final focused run. Existing ordinary receipts keep their historical URI convention; the new attestation URI includes environment and explicit kind.
- Temporary snapshots must be re-captured before packet preparation. No executable release/rollback packets, authorizations, registrations or live writes were made. Stage 7B remains In Progress.

## Handoff Notes
- **Resume at:** Resolve Preview's required original pipeline/step evidence with retained authentic records or a revised Contract 04 decision. Production schema and each environment's registration remain separate exact user decisions. Refresh full schedule, spread/total quotes, finals, deadlines, grants, lease and all sources before any dynamic N or packet.
- **Watch out for:** Actual attestation creation time is new; original selection/freeze/kickoff are separate facts. Exact retries use the prior attestation bytes and timestamp. A failed DB apply can leave unused immutable R2 audit objects; it never permits reassignment. Keep Preview and Production source evidence distinct. Do not alter the historical preflight report or `docs/status.md` before verified serving changes.
- **Proposed commit:** `feat(release): verify and guard Week 5 legacy freeze attestations` (user-run; no Git operations performed).

**tags:** ["release", "stage7b", "attestation", "prospective-evidence", "hold"]
