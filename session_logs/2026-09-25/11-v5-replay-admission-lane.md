# Session: V5 replay admission lane (Task 2)

## TL;DR

- **Worked On:** Migration 0015 (append-only replay authorization lane) plus replay admission checks in publisher/selection with contract sync and the negative-test battery.
- **Outcome:** Replay publication/selection in production now requires an exact replay authorization plus the dual-role guard; the live 09/05 lane is untouched. Migration 0015 rehearsed on Preview (0 rows, pipeline SELECT-only, web blocked). Full suite 1391 passed.
- **Plan Contract:** `docs/plans/2026-09-25/02-v5-week4-replay-site-cutover.md` (Approved), Task 2.
- **Approval / Status:** Approved plan + Amendment 1. No authorization rows created; no production migration or selection performed.
- **Blockers:** None.
- **Next:** Commit this chunk, then Task 3 (Preview history W1–3 + W4 rehearsal + web labels).

## Context and Decisions

- The replay authorization binds one slate/run to exact replay manifest, verifier receipt, serving config, prediction artifact, model, and bundle bytes. It never satisfies prospective, readiness, or live gates — a separate lane, not a relabeled live path.
- The W0 serving manifest field names (`v5_replay_manifest_uri/sha`, `replay_verification_sha256`, `config_sha`, `inference_bundle_sha256`) are the binding surface; the Week 4 serving artifacts (Task 3) will use the same field names pointing at the new W4 manifest.
- Field assumptions were verified against the real certified W0–3 manifest and verifier receipt before wiring (frozen/replay/act=False; receipt `verified` key absent → default-True acceptance; manifest+records SHA bindings confirmed).
- Import-time `ruff check` on `.ts` files reports bogus Python-syntax errors (263/file); ruff does not apply to TypeScript — Python files pass, TS diffs verified by inspection.

## Work Completed

- Added `contracts/migrations/0015_v5_replay_release_authorization.sql`; synced `contracts/schema.sql` (table + grants), `contracts/schema.ts`, `web/src/lib/schema.ts`.
- Added `validate_replay_release_record` / `require_replay_release_record` (+ replay manifest/verifier byte-check helpers) in `src/cks_picks_cfb/ops/v5_release.py`.
- `publish_to_db.py`: production admits `pending` (live, existing) and `replay` (new, with exact authorization); all other evidence classes still fail closed. `public_selection.py`: production `replay` selection requires the replay authorization; pending/live flow unchanged.
- Tests: 16 replay-record cases (validation, identity fields, unfrozen/dry-run rejection, live-manifest rejection, absent-record zero-write), production replay publisher negative (+731→ verified replay-auth-table query, zero writes), production replay selection negative (no writes).
- Applied 0015 to Preview via the standard migrator path; verified version row, 0 authorization rows, pipeline SELECT true/INSERT false, web SELECT false, migrator ownership.

## Files Modified

- `contracts/migrations/0015_v5_replay_release_authorization.sql` - new replay authorization table.
- `contracts/schema.sql`, `contracts/schema.ts`, `web/src/lib/schema.ts` - replay table sync + grants.
- `src/cks_picks_cfb/ops/v5_release.py` - replay record validation + require functions.
- `scripts/pipeline/publish_to_db.py`, `src/cks_picks_cfb/ops/public_selection.py` - replay admission.
- `tests/test_v5_release.py`, `tests/test_publish_to_db.py`, `tests/test_public_selection.py` - replay battery.

## Validation

- [x] Full pytest: 1391 passed, 2 skipped.
- [x] Ruff check + format on touched Python files; `uv run python contracts/validation.py`; `make contracts-check`.
- [x] Web typecheck + lint via Nx.
- [x] Preview 0015 rehearsal with grant/zero-row readback.
- [x] Strict MkDocs build; `git diff --check`.

## Amendments and Blockers

None. The replay packet validator (`validate_v5_release_packet.py`) replay mode is deferred to Task 4.

## Handoff Notes

- **Resume at:** Commit this chunk, then Task 3 — convert the verified W0–3 replay into per-week Preview serving artifacts (Weeks 1–3), build the Week 4 serving artifact (needs a W4-aware replay-source branch in `generate_v5_replay_weekly_bets.py`, which currently requires `v5_replay_manifest_v1`), publish/score/select on Preview, web replay labels, V4 rollback rehearsal.
- **Watch out for:** `verify_v5_replay_source` hard-checks the W0–3 manifest schema; the W4 manifest schema differs. Keep live authorization semantics untouched. Preview 0015 is applied; production 0015 waits for the reviewed migration commit (Task 4 packet decision does not include authorization rows — those need the later exact-packet approval).

**Suggested commit message:** `Add V5 replay release authorization lane`

**tags:** ["v5", "replay", "release", "migration"]
