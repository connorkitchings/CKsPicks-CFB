# Session: V5 replay production packet (Task 4)

## TL;DR

- **Worked On:** Read-only packet validator replay mode, five production candidate artifacts, per-week byte-bound authorization packets, and production precondition checks.
- **Outcome:** All five replay packets (`W0–W4`) validate; production candidates are byte-identical to the reviewed Preview builds. Presented for the separate approval decision. No authorizations, migrations, publications, or selections performed.
- **Plan Contract:** `docs/plans/2026-09-25/02-v5-week4-replay-site-cutover.md` (Approved), Task 4.
- **Approval / Status:** Awaiting the user's explicit packet decision. Production V5 activation remains separate.
- **Blockers:** None in the packet. Execution needs the approval decision first.
- **Next:** On approval: production 0015 migration → policy seed → admin authorization inserts → publish/score/select (W0–3 first, W4 when finals certify).

## Context and Decisions

- Production candidates were prepared in the production R2 namespace (R2 writes only; no Neon, selection, or authorization) following the live-path `prepare` precedent. Their prediction bytes are identical to the reviewed Preview builds (same SHAs), so the packet binds exact reviewable bytes.
- The packet validator reads the production serving manifest and the record's own URIs throughout; no byte-location overrides exist in the release path.
- Precondition finding: production `v5_release_policy` has no row (Preview's row covers the same model/bundle with first-live 2026 Week 5). The publisher's model-identity gate requires it, so seeding the identical row is a listed admin precondition of the release execution — part of the approval decision, not done in advance.
- Production is at migration 0014 (0015 pending), has zero V5 rows, zero replay authorizations, and the V4 Week 4 run frozen at 58/58. `cks_prod_pipeline` exists; its replay-table grants verify after 0015 lands.

## Work Completed

- Extended `validate_v5_release_packet.py` with `--kind live|replay` (live default unchanged).
- Built 5 production candidates (8/43/49/57/58 rows; SHAs match Preview builds).
- Assembled and validated 5 replay authorization packets (tmp JSONs): auth IDs `v5-replay-2026w{0..4}-<artifact-8>`; replay manifests `3e32a091…` (W0–3) and `2ba06bb0…` (W4); verifiers `1cfc7d43…` / `12c6ff30…`; serving configs `95033294…` / `7f58ea7c…`; decision ref `v5-replay-cutover-review-2026-09-25` (proposed).
- Read-only production precondition readback (policy absent, 0014 latest, no V5 rows, V4 frozen, role present).

## Files Modified

- `scripts/pipeline/validate_v5_release_packet.py` - replay packet mode.
- `src/cks_picks_cfb/ops/v5_release.py` - docstring only (reviewable-candidate requirement).

## Validation

- [x] All 5 packets `{"valid": true}` via the read-only validator.
- [x] `uv run pytest tests/test_v5_release.py` (45 passed); ruff check + format clean.
- [x] Production read-only preconditions recorded.
- [x] `git diff --check`; strict MkDocs unaffected (rerun at commit).

## Amendments and Blockers

None. The decision itself is the pending gate.

## Handoff Notes

- **Resume at:** User decision on the packet (approve all five weeks / subset / defer). On approval, execute in order: (1) production 0015 migration + grant/zero-row verification, (2) seed `v5_release_policy` row (production decision ref), (3) admin inserts of the approved authorization rows only, (4) pipeline-role publish → score → select per approved week (W0–3 first; W4 publish now, score/select when its 58 finals certify; W4 market grades vs the frozen quotes staged on Preview), (5) verify V4 frozen run untouched + serving health.
- **Watch out for:** Never insert rows for unapproved weeks; never reuse these packets for a different run/week/environment; the Week 5 live path keeps priority at the finals gate.

**Suggested commit message:** `Prepare V5 replay production release packet`

**tags:** ["v5", "replay", "release", "packet"]
