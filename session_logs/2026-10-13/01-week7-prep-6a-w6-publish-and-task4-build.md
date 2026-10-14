# Session: Week 7 prep — Week 6 6A publish, Task 4 build, helper branches

## TL;DR

- **Worked On:** Step 1 and the start of Step 2 of the Week 7 plan (2026-10-12): Week 6 6A rebuild verify and publish, three helper code/doc branches, and Task 4 for the Week 6 rebuild.
- **Outcome:** The Week 6 6A run `6a-rebuild-w6-20261012-r2` is published to Preview (root raw sha256 `9d218543eec7eda149bbb5ba446b5f73f33b8ae107d5a7da20bdbe00f8d007c3`). Task 4 `6a-task4-w6-r1` is preflighted and built at `26ab0b08` (stages attribution `f7417d8c…`, published_comparison `8cc6c4b0…`, receipt `68d87cc1…`); it is NOT verified or published. Three helper branches are committed but unmerged.
- **Plan Contract:** `N/A (fast path)`; plan: Week 7 next steps (2026-10-12), [fallback](../../docs/plans/2026-10-11/03-week7-standalone-fallback.md).
- **Approval / Status:** Each Preview write (verify, publish, preflight, build) had its own explicit user go-ahead in-session. Nothing in Production touched.
- **Blockers:** Task 4 verify and publish await go-ahead; the 14:00Z Tue pivot decision is unresolved at session end. Producers branch needs a rebase onto `dev`.
- **Next:** Task 4 `verify` at `26ab0b08`, then publish; then 6B Week 6 frames (Step 2.2).

**tags:** ["week7", "rebuild", "6a", "task4", "preview"]

## Context and Decisions

- `verify` at HEAD `f8848bfa` failed (stale preflight, made at build commit `30a12a6d`; the intervening commit was docs-only). Verify at `30a12a6d` then failed with `silver_2026: ppa changes are not exactly the nulled values`.
- Diagnosis (read-only): the Week 6 legacy comparison is already nullable (`legacy_zero_ppa 0`, `null_ppa 11045`, `value_differences {}`), so the check should compare to `legacy_zero_ppa`. Fix `2147c5fb`.
- Option 1 chosen: re-preflight at the fix commit. Staging is create-once, so the old `preflight.json` and failed `verify.json` were moved aside by the user (the auto-mode classifier blocked me doing it). Provenance consequence: the published root records code `2147c5fb` and preflight `eb3983ce…`; the 11 stage manifests still carry `30a12a6d` and `e2609793…`. Record in the repair contract.
- Publish was run with `rebuild_6a.py publish`, not the designed `scripts/pipeline/publish_6a.py`, so the root has `publisher_code_sha: null` and no catalog registration. The root is create-once, so this cannot be corrected. The user confirmed catalog registration is not required for the Week 7 chain. Task 4 receipt was made to render "none recorded".
- Task 4 build needs the Preview pipeline login (`with_preview_env.sh`, no `DATABASE_URL` override). Its gate required exactly one rating run in Preview `team_rating_components`; the two-run state (ratings-v1 weeks 0-5, `corrected-w6live-r1` week 6) is intended, so the stage now maps weeks to runs (`published_rating_runs` policy).

## Work Completed

- Week 6 6A verify (passed `046468cf…`) and publish to Preview: 236 objects + root, 237 writes, readback verified.
- Task 4 plan pinned to the root raw sha (`84e32383`).
- Task 4 preflight (`08dc6816…`) and build at `26ab0b08`: exit 0, three stages.
- Helper branches (worktree agents, no data I/O), all committed, none merged except as noted below.

## Files Modified

Merged to `dev` (fast-forward, local, not pushed):
- `2147c5fb` `src/cks_picks_cfb/rebuild/silver_2026.py`, `tests/test_rebuild_2026.py` — PPA diff check vs `legacy_zero_ppa`.
- `84e32383` `conf/rebuild/6a_task4_w6_v1.yaml` — root manifest sha pin.
- `a749044e` `src/cks_picks_cfb/rebuild/published_comparison.py`, `tests/test_published_comparison_scope.py`, `conf/rebuild/6a_task4_w6_v1.yaml` — two-run mapping.
- `26ab0b08` `src/cks_picks_cfb/rebuild/receipt.py`, `tests/test_rebuild_receipt.py` — null publisher rendering.

Unmerged branches:
- `worktree-agent-a1df455df071f526e` `6ce3a59b` — `scripts/pipeline/rollback_week_release.py` + tests (27 pass per agent). New receipt file `week_release_receipt_v1` has no generator yet.
- `worktree-agent-af2bc63a21dc98f6c` `22a369c1` — Advance-Mode producers (certify finals, prospective payloads, upload refs); based on `a0e9b450`, needs rebase onto `dev`. Open questions: `finals_stabilized_at` source, DB session timezone, receipt schema check, certification scope.
- `worktree-agent-a20a3a0697c9560c4` `e2ee0e80` — rewritten fallback doc, run-sheet steps 4-9, repair Amendment 15, plans index row. Not yet updated for Task 4/publish findings above.

Local only (gitignored): `artifacts/rebuild/6a-rebuild-w6-20261012-r2/{preflight.e2609793.json,verify.failed.json}`, `artifacts/rebuild/6a-task4-w6-r1/{preflight.*.json,stages.*}`.

## Validation

- [x] Verifier fix: `tests/test_rebuild_2026.py` 11 passed (agent-reported)
- [x] Comparison fix: 65 focused + 240 broader tests passed (agent-reported)
- [x] Receipt fix: `tests/test_rebuild_receipt.py` 4 passed (agent-reported)
- [x] 6A publish readback: 236 objects hash-checked, root raw sha read back independently
- [ ] Task 4 verify: not run
- [ ] Not independently re-run by me: agent test results; `git diff --check` on this log

## Amendments and Blockers

- Needed repair-contract amendment: build/verify/publish commit provenance split, null publisher on the -r2 root, skipped catalog registration, `published_rating_runs` policy and the now-incompatible older Task 4 plans (`6a_task4_w5_v1.yaml`, `6a_task4_v1.yaml`).
- The fallback doc (`e2ee0e80`) says `publish_6a.py` is the designed 6A publisher; future 6A publishes should use it with `--apply` and a clean tree.

## Handoff Notes

- **Resume at:** Task 4 `verify` (`PYTHONPATH=.:src uv run python scripts/pipeline/rebuild_6a.py verify --plan conf/rebuild/6a_task4_w6_v1.yaml --expected-code-sha 26ab0b08e570d82750b467ab1caf94fff3eba917`), then publish, then 6B Week 6 frames.
- **Watch out for:** Tue 22:00Z freeze deadline (first kickoff 23:00Z minus 1h; later marks the run `missed`); 14:00Z pivot to the standalone route; Week 7 market capture ~08:00Z; Task 4 plan hash changes if edited.
