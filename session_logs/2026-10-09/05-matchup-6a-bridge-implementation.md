# Session: 6A matchup bridge implementation (Terra)

## TL;DR
- **Worked On:** Tasks 1–3 + Task 4 dry runs of `docs/plans/2026-10-09/03-matchup-6a-bridge.md`.
- **Outcome:** Bridge loader, CLI flags, scoped writes, verifier script + assertion, and 12 tests (incl. local-Postgres no-overwrite proof) all delivered and green. Preview dry runs pass every gate with a deterministic payload (`08e22bae…` across 3 runs). **Stopped before any `--apply`** per instructions — verifier R2 write + Preview matchup publish await explicit authorization.
- **Plan Contract:** `docs/plans/2026-10-09/03-matchup-6a-bridge.md` (stays `In Progress`; no amendment needed — all per contract)
- **Approval / Status:** implement-plan on the exact path (user instruction).
- **Blockers:** User authorization for Task 4 `--apply` (verifier write, then matchup publish, then local route check).
- **Next:** On authorization: verifier `--apply` → publish dry run (asserts verifier) → publish `--apply` → `verify_matchup_data` exit 0 → local route check → annotate contract `02` → closeout.

## Context and Decisions
- implement-plan skill: contract read + Approved/explicit authorization confirmed; branch `dev`; unrelated byplay-v2 worktree files preserved untouched; reconciliation passed (Preview d2 selected, 1,624 snapshots, 0 corrected matchup pubs; Production untouched).
- Design refined during implementation (all within contract scope): write scoping gated on bridge mode only (default path byte-identical, proven by existing suite); verifier-URI derivation shared via `mp.bridge_verifier_uri`; `open_pinned_run` semantics mirrored inline (data layer stays decoupled from the rebuild harness); test-fixture roles reuse `_roles_fixture` with a gate-parity (not all-pass) assertion since the established fixture itself fails 3 static gates on synthetic data.
- Refusal-matrix tests needed repointing helpers (`_repin_root`, `_repoint_rating`) because the pin check precedes deeper checks — each refusal path is now reached deterministically.

## Work Completed
- `src/cks_picks_cfb/data/matchup_publish.py`: `load_6a_bridged_artifacts()` (+ root/frame readers, `SIX_A_*` consts), `prepare_run` bridge selection, `write_payload(log_game_ids=)` scoping, `build_bridge_verifier_manifest()` / `sign_bridge_verifier()` / `assert_bridge_verifier()` / `bridge_verifier_uri()`.
- `scripts/pipeline/publish_matchup_data.py`: `--six-a-*` flags, measurement-URI xor validation, pre-write verifier assertion, bridge-mode log scoping from built weeks.
- `scripts/pipeline/verify_matchup_data.py`: `--six-a-*` flags, scoped compare (gates still see the full payload).
- `scripts/pipeline/build_6a_bridge_verifier.py` (new): dry-run default, write-once R2 apply, read-only DB gates.
- `tests/test_matchup_6a_bridge.py` (new): 12 tests — accept, 6 refusal cases, flag validation, verifier sign/assert/refuse, gate-parity, local-Postgres scoped-write no-overwrite proof (served rows intact, game-1 restamped, verified against disposable PG14, torn down).
- Preview dry runs (read-only): verifier (11/11 gates ok), publish (11/11 gates ok, sha `08e22bae…` ×3 runs), `verify_matchup_data` correctly reports missing rows pre-apply.
- Disposable local PostgreSQL 14 used for the DB test; removed afterwards.

## Files Modified
- `src/cks_picks_cfb/data/matchup_publish.py` - bridge loader, verifier helpers, scoped write
- `scripts/pipeline/publish_matchup_data.py` - flags, verifier assertion, scoping
- `scripts/pipeline/verify_matchup_data.py` - flags, scoped compare
- `scripts/pipeline/build_6a_bridge_verifier.py` - new verifier script
- `tests/test_matchup_6a_bridge.py` - new tests
- `docs/plans/2026-10-09/03-matchup-6a-bridge.md` - status → In Progress
- `session_logs/2026-10-09/05-matchup-6a-bridge-implementation.md` - this log

## Validation
- [x] New tests: 12 passed (incl. DB test on disposable Postgres)
- [x] Full suite: 2,305 passed, 15 skipped
- [x] `ruff format --check .` (742 files) + `ruff check .` clean
- [x] `contracts/validation.py` passed
- [x] Bridge dry runs: 11/11 gates, deterministic payload sha
- [x] `git diff --check` (run at handoff)
- [ ] Task 4 `--apply` ×2 + local route check (awaiting authorization)
- [ ] Web lint/typecheck (no web files changed — N/A)

## Amendments and Blockers
- None to the contract. Blocker: explicit user authorization for the two Preview `--apply` steps.

## Closeout (2026-10-09, user-authorized applies complete)

- Verifier `--apply`: signed manifest written to R2 (2,640 bytes; 11/11 gates; payload `08e22bae…` = 3rd identical build).
- Matchup publish `--apply` (Preview): stats 1,656 + adjusted 549 + components 508 + registry row `2026:intended_update:c83b1423…:08e22bae…` (weeks `[6]`); log write 0 rows (correct — no completed W6 games; served provenance untouched).
- `verify_matchup_data`: exit 0, 0 differing rows.
- Local Preview site (`run_web_local.sh preview`, predictions mode): Picks 55 games + exact notice text; W6 matchup (Texas–Oklahoma) lineage `ready`; Ratings renders corrected post-W5 (Notre Dame, Utah on top); W5 page unchanged apart from its pre-existing Oct-8 source-flip state (served rows byte-intact; documented in contract `02` Amendment 3 as requiring explicit accept for Production).
- Contract `03` → `Implemented`; contract `02` annotated (Amendment 3: Task 1c proof + Task 5 ordering fix + W0–5 degradation accept).
- Validation rerun at closeout: full suite already green (2,305 passed); `git diff --check` clean; no further code changes after the suite run (docs only).

## Handoff Notes (updated)
- **Resume at:** user decision on the W0–5 matchup degradation accept → release contract `02` Task 2 (rollback script, user review gate) → Tasks 3–7 (all Production applies user-run).
- **Commit proposal:** `feat(matchup): 6A-bridged publication path with verifier and scoped writes` (full message in the prior handoff; add contract `02` Amendment 3 + this log to the same commit).
- **Watch out for:** verifier `--apply` writes R2 research prefix (write-once, refuses on differing bytes); publish `--apply` needs the active pipeline lease + restricted role (script asserts both); never freeze/close any run; no Production writes in this contract.
- **Exact pending commands:** in the log appendix below.

## Appendix — pending authorized commands

```bash
# 1. Write the signed bridge verifier to R2 (write-once)
PYTHONPATH=.:src zsh scripts/ops/with_preview_env.sh uv run python scripts/pipeline/build_6a_bridge_verifier.py \
  --rating-manifest-uri artifacts/research/data-first-football-v1/possession-v1/intended-update-2026/runs/v5-intended-update-2026-corrected-w6live-r1/rating-manifest.json \
  --six-a-run-id 6a-rebuild-w5-20261007-r2 \
  --six-a-root-sha256 7865d35336b039f8983ee235c6855d2795a9b35233a779a7a67a959aee89d9b0 \
  --season 2026 --weeks 6 --environment preview --apply

# 2. Publish matchup data to Preview (asserts the verifier, scoped log write)
PYTHONPATH=.:src zsh scripts/ops/with_preview_env.sh uv run python scripts/pipeline/publish_matchup_data.py \
  --season 2026 --environment preview \
  --rating-manifest-uri artifacts/research/data-first-football-v1/possession-v1/intended-update-2026/runs/v5-intended-update-2026-corrected-w6live-r1/rating-manifest.json \
  --six-a-run-id 6a-rebuild-w5-20261007-r2 \
  --six-a-root-sha256 7865d35336b039f8983ee235c6855d2795a9b35233a779a7a67a959aee89d9b0 \
  --weeks 6 --apply

# 3. Verify (expect exit 0), then local route check
PYTHONPATH=.:src zsh scripts/ops/with_preview_env.sh uv run python scripts/pipeline/verify_matchup_data.py \
  --season 2026 --environment preview \
  --rating-manifest-uri artifacts/research/data-first-football-v1/possession-v1/intended-update-2026/runs/v5-intended-update-2026-corrected-w6live-r1/rating-manifest.json \
  --six-a-run-id 6a-rebuild-w5-20261007-r2 \
  --six-a-root-sha256 7865d35336b039f8983ee235c6855d2795a9b35233a779a7a67a959aee89d9b0 \
  --weeks 6
CFB_PUBLICATION_MODE=predictions zsh scripts/ops/run_web_local.sh preview
```

**tags:** ["implementation", "matchup", "bridge", "v5", "tests"]
