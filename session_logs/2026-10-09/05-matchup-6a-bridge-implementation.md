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

## Handoff Notes
- **Resume at:** user authorizes → verifier `--apply` → publish `--apply` → verify exit 0 → `run_web_local.sh preview` route check (W6 `ready`, W0–5 unchanged) → annotate contract `02` (payload sha, verifier URI, select-before-matchup ordering fix) → contract `Implemented` → commit proposal.
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
