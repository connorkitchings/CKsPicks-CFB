# Session: V5 Week 4 replay apply checkpoint

## TL;DR

- **Worked On:** Applied the immutable Week 4 late-publication replay run after the frozen-manifest fix.
- **Outcome:** `v5-week4-replay-20260925` frozen and independently verified in Preview R2 (58 games / 116 targets, `evidence_class: replay`, `late_publication: true`). Task 1 of the replay-cutover plan is complete.
- **Plan Contract:** `docs/plans/2026-09-25/02-v5-week4-replay-site-cutover.md` (Approved), Task 1.
- **Approval / Status:** Approved plan; no production or selection writes. Git operations remain user-controlled.
- **Blockers:** None for Task 1. Task 2 (replay admission lane) is next.
- **Next:** Migration 0015 + replay authorization admission in publisher/selection with the negative-test battery; then Preview migration rehearsal.

## Context and Decisions

- A first `--apply` attempt exposed a manifest-assembly bug: the dry-run `state` leaked through the dict spread into the frozen manifest. The script's own inline verifier rejected the receipt (`identity or policy differs`), so nothing was published or referenced. Fixed by extracting `_manifest()` (drops evidence `state`) plus a regression test.
- The two unreferenced staging files from the rejected apply were removed (audited below); the prefix was empty before the successful apply. Rewritten `predictions.csv` is byte-identical to the removed staging copy (deterministic compute).
- Run identity: `v5-week4-replay-20260925`; source cutoff = certified W0–3 measurement `as_of` 2026-09-22T14:58:00Z (< first W4 kickoff 2026-09-24 23:30Z); schedule = pinned Silver games `e3ead581...` (proven identical to the frozen 58-game W4 slate); actual creation 2026-09-25T16:06:25Z recorded as `created_at_utc`.

## Work Completed

- Fixed the frozen-manifest bug, added `test_week4_replay_manifest_freezes_without_dry_run_state`, re-ran unit tests (10 passed) and a fresh reviewed preflight under the new HEAD.
- Removed rejected staging objects (never receipted, never referenced):
  - `…/v5-week4-replay-20260925/predictions.csv` — sha `63c2f03890571401d730e9657e54a5fd44b7a5baeda76c49f4fcc7c4ed4aa6b06d48b984a2a658d51e1aff2f18f0d`
  - `…/v5-week4-replay-20260925/week4-replay-manifest.json` (`state: dry_run`) — sha `598466f1141c35a49f3754616b3a8e9c65028bd817dcec2898576eedb4d8d54c`
- Applied the immutable run and independently verified it in the same invocation; read back all three objects and re-checked every binding.

## Files Modified

- `scripts/pipeline/build_v5_week4_replay.py` - `_manifest()` helper; `main()` uses it.
- `tests/test_v5_week4_replay.py` - frozen-manifest regression test.

## Validation

- [x] 10 focused tests pass; ruff check + format clean.
- [x] Fresh reviewed preflight under committed HEAD matched the apply (`reviewed != evidence` gate passed).
- [x] Apply output: manifest `v5_week4_replay_manifest_v1`/`frozen`/`replay`/`late_publication: true`; predictions digest matches; receipt `v5_week4_replay_verification_v1`/`verified` 58/116 bound to manifest bytes.
- [x] Session 09's suggested fix commit landed (`9e39d1a`); worktree clean before apply.

## Amendments and Blockers

None beyond the fixed bug. Task-1 acceptance (58 unique games, 116 paired rows, exact SHAs, independent equality, late-publication finding) is met.

## Handoff Notes

- **Resume at:** Task 2 — migration 0015 (append-only replay authorization lane) + admission checks in publisher/selection + shared contract sync + negative-test battery, then Preview migration rehearsal.
- **Watch out for:** Keep the live 09/05 authorization semantics untouched; replay must never satisfy readiness or prospective gates. The W0–3 frozen replay bytes stay immutable; the Week 5 live path keeps priority at the finals gate.

**Suggested commit message:** `Freeze verified V5 Week 4 late replay run`

**tags:** ["v5", "replay", "week4", "checkpoint"]
