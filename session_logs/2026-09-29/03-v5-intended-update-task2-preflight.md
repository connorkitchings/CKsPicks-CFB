# Session: Task 2 preflight — repaired historical ratings and refit bridge

## TL;DR
- **Worked On:** Task 2 of `docs/plans/2026-09-29/v5-intended-update-2026-production-repair.md` — repaired historical rating lineage and through-2025 bridge, preflight only.
- **Outcome:** Preflight build and independent verification both pass locally. No repo files changed; no R2 or Neon mutation. R2 immutable publication deferred (dirty worktree blocks `--apply` by design; publication belongs with the Task 6 Preview rehearsal after commit).
- **Plan Contract:** `docs/plans/2026-09-29/v5-intended-update-2026-production-repair.md` (`In Progress`).
- **Approval / Status:** User authorized this exact contract path on 2026-09-29 and said "go" in build mode. Exact production release remains a later packet-specific decision.
- **Blockers:** R2 `--apply` publication requires the expected clean committed checkout; current checkout is dirty by design (preserved research + Task 2–5 scaffolding). Sklearn `RuntimeWarning`s (overflow/invalid/divide-by-zero in matmul) appear during the verifier's independent refit; verification still passes — noted as follow-up, not a promotion stopper at preflight.
- **Next:** Task 3 (2026 rating generations) preflight, then Tasks 4–6 in sequence; commit order first.

## Context and Decisions
- Task 2 scaffolding already existed untracked (`possession_intended_update.py`, `intended_update_bundle.py`, `build_v5_intended_update_bundle.py`, `verify_v5_intended_update_bundle.py`, `test_possession_intended_update.py`). No code edits were needed; work was execution + verification.
- Preflight ran against read-only Preview R2 certified parents (backend `r2`, Preview credentials present). Output went to `/var/folders/b5/wrh935896v148pd_2rvkcbz00000gn/T/opencode/v5-intended-update/bundle-preflight` — never repository `./data/`.
- Run ID `v5-intended-update-2026-v1`, code SHA `962337b3a0ea6a691b901ced8c301ad1c5bfcadf` (current HEAD; dirty worktree recorded, not published).
- The build's embedded `manifest_sha256: 1bef8683…` is the inner signed-payload hash; the file-bytes SHA (`b1bef732…`) matches the verifier's `bridge_manifest_raw_sha256`. Not a mismatch — two different serializations.

## Work Completed
- Built repaired historical pregame states + alpha-10 refit bridge (preflight, no `--apply`).
- Independently verified the local artifact with `verify_v5_intended_update_bundle.py --local-output`.
- Ran focused + full ratings test suites, Ruff, and `git diff --check`.

## Files Modified
- None. All implementation files were pre-existing untracked scaffolding; this session changed no repo files.
- `session_logs/2026-09-29/03-v5-intended-update-task2-preflight.md` — this log.

## Validation
- [x] Preflight build: 35,740 historical states (expected population), training rows 8,935, seasons `[2015–2019, 2021–2025]` (no 2020, no 2026), calibration counts margin/total 7,192 each.
- [x] Accepted V5 control fidelity: max_abs_rating_mean `8.88e-16`, variance `2.22e-16`, exposure `0.0` (tolerance `1e-9`).
- [x] File SHAs: states `a4cbb786…`, bundle `30c4f1eb…`, manifest bytes `b1bef732…` — verifier agrees on all three.
- [x] Verifier state checks: 35,740 states, 170,337 source-game-role contributions, 378 FCS fallbacks; bundle coefficients + earlier-only interval variances match independent refit within tolerance.
- [x] `tests/ratings/test_possession_intended_update.py`: 5 passed. Full `tests/ratings/`: 261 passed.
- [x] Ruff format `--check` + `ruff check`: clean on all five Task 2 files.
- [x] `git diff --check`: clean.
- [ ] R2 immutable publication (`--apply` + verifier `--apply`) deferred to Task 6 rehearsal after commit.
- [ ] 215-game retrospective reconciliation against the 2026 counterfactual report belongs to Tasks 3–4 (needs 2026 generations + forecasts).

## Amendments and Blockers
- No architecture amendment. Preflight-only execution is within Task 2's acceptance sequence; R2 publication is explicitly deferred, not skipped.
- Follow-up: triage sklearn `RuntimeWarning`s in the verifier's calibration refit before the Task 6 rehearsal to confirm they are benign scaling artifacts.

## Handoff Notes
- **Resume at:** Task 3 preflight (`build_v5_intended_update_2026.py`) against the pinned source lockfile, then Task 4 forecasts/scores.
- **Watch out for:** Do not run any `--apply` until the commit-order decision is resolved and the checkout is clean at the expected SHA. Keep retrospective replay distinct from prospective predictions. Week 5 kickoff `2026-10-02T00:00Z` may force the live slate forward.

**tags:** ["ratings", "v5", "production", "implementation", "task2"]
