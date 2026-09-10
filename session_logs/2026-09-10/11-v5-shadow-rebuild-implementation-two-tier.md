# Session: v5 Shadow Rebuild — Two-Tier Gate Execution (Terra, BLOCKED on W2 finals)

## TL;DR
- **Worked On:** Fresh Terra implementation of `docs/plans/2026-09-10/2026-v5-shadow-rebuild-diagnostic.md` (Approved: user re-approval 2026-09-10, Amendment 2). Executed Tasks 1–4 fully and Task 5 partially under the Amendment-2 two-tier gate.
- **Outcome:** ALL Tier 1 + Tier 2 gates PASS (W0/W1/W2); three v5 Gold assemblies + three shadow prediction artifacts produced in Preview R2; W0/W1 shadows scored. **BLOCKED:** W2 finals do not exist (first kickoff Fri 2026-09-11 23:30 UTC, verified; today 2026-09-10), so the pooled-W1+W2 verdict + kill criterion cannot execute yet. W2 shadow stands frozen pre-kickoff for post-close scoring. Kill criterion NOT applied.
- **Plan Contract:** `docs/plans/2026-09-10/2026-v5-shadow-rebuild-diagnostic.md` (now `In Progress — BLOCKED on W2 finals`; Amendment 3 appended for a minor tooling recovery)
- **Approval / Status:** Approved (user re-approval 2026-09-10, Amendment 2) → In Progress → In Progress BLOCKED (material timing gap in Task 5, no redesign).
- **Blockers:** (1) W2 finals pending 09-11 kickoff + Week 2 close (scheduled, external). (2) Resolved in-run: missing executable catalog schema for `point_in_time_matchups_core_v1` at HEAD → Amendment 3 ref-minting (bytes authoritative, no code changes).
- **Next:** After the Week 2 close, score `shadow-2026-v5-w2` with the Week 2 close `game_outcomes_ref.json`, render the pooled W1+W2 table, apply the kill criterion (see Handoff Notes for exact commands).

## Context and Decisions
- Followed `.agent/skills/implement-plan/SKILL.md` §1–§4: read the full amended plan + planning log (06), stopped-run evidence (07, 09, read-only), amendment logs (08, 10) before any writes; authorized the exact Draft path (Approved, approval source "user re-approval 2026-09-10, Amendment 2"); marked In Progress with this new log path (`11-…`); reconciled worktree vs contract with zero material conflicts before executing.
- Preserved unrelated worktree state throughout: `M docs/ops/production_runbook.md` and `?? .opencode/` untouched (verified each stage via read-only `git status`). No git add/commit/push (user-controlled). No `./data/` writes (`data/` is gitignored pre-existing working output; all ephemeral CSVs went to OS temp via `CFB_WORK_ROOT` default).
- Storage: `CFB_STORAGE_BACKEND='r2'` (from `.env`; key lengths only, values never printed). Preview ops via `zsh scripts/ops/with_preview_env.sh` (Keychain); explicit `get_storage(environment="preview")` for R2 writes. Production Neon: read-only SELECTs only (via `.env` `DATABASE_URL`). Never invoked `publish_to_db.py`, `freeze_week.py`, or `score_to_db.py`.
- Reused prior-session read-only scripts from `/var/folders/.../T/opencode/` (`task1_verify.py`, `guard_counts.py`, `prod_runs.py`, `steps_detail.py`, `diag_parity.py`); new scripts written there too (`tier1_w0.py`, `tier2_*`, `mint_refs.py`, `verdict_interim.py`, `shadow_drift.py`, `prod_pipe_runs.py`). Nothing written inside the repo except the plan + this log.
- Verified inference-loader mechanics from source (not assumed): `model_bundle_v3.py:179-202` (`_predict_ref` reads only listed `ref.features`, missing → fail-closed) and `regime_training.py:36-44` (`_model_values` selects `frame.loc[:, list(features)]`) — extra columns are never read.
- Contract figure "329 features" independently reproduced: recursive walk of the bundle manifest over `direct` + blend `current`/`prior` slots → union exactly 329 (my first flat enumeration found 277; corrected before asserting).

## Work Completed

### Authorization + reconciliation (skill §1)
1. Plan Draft(+A1+A2) → Approved → In Progress→ `In Progress — BLOCKED on W2 finals`; implementation log path updated to this file.
2. Official record reconciled (matches contract §1): W0 `2026w0-55de0317120d` scored (+`2026w0-79ec2aebcb00` published), W1 `2026w1-b2c739321e5d` scored, W2 `2026w2-43b25511a100` frozen. Prod `input_dataset_refs` re-read: matchups `1f32fc0f…`/`2f7566f8…`/`64393952…`, markets (`07336aaa`/`e3f984c4`, `b273e83d`, `459c80d0`+quotes `ede4a9a7`), games `5dabf61a` — all match.
3. Regression-guard baselines captured BEFORE any write and re-verified after every stage (identical throughout): prod runs=50/preds=2377/grades=4476/`current_week`=(2026,2,`2026w2-43b25511a100`); preview runs=19/preds=821/grades=1524/`current_week`=(2025,16,`v4replay-2025-w16`).
4. Shadow artifacts from stopped runs verified reusable in R2 (no rebuild): `w0-parity-point_in_time_matchups_ref.json` (`c89b4567`, content `cc6b1a03…`) + 3 ref-files under `artifacts/preview/shadow-2026-v5/refs/`.

### Task 1 — PASS (read-only)
- All 15 refs resolve in R2 with matching content SHAs (W0 core `a381de33`, baselines `d41e40a9`, matchups `1f32fc0f`; W1 team `6e8cf241` + matchups `2f7566f8`; W2 team `415d6150` + matchups `64393952`; baselines `cf852153`; preseason `6bc8f8c1` strict/eligible/excludes_2020; games `22ed8686`; all five market/quote refs).
- Cutoff audit PASS: every input `as_of` ≤ first kickoff (W0 ≤ 08-29; W1 04:00/05:00Z ≤ Thu-evening kickoff; W2 09-08 ≤ Fri 09-11 23:30Z kickoff, verified in games Silver).

### Task 2 — ALL TIERS PASS (all three weeks)
- **W0 Tier 1** (`tier1_w0.py` vs full 329-feature union): same 4491 rows/keys/parents `[d1c5efd8, ec13aef8]`; 5 rerun-only cols disjoint from union + all-null in 2026 slice; 16 differing common cols all-missing in BOTH frames, None(object)→NaN(float64) only. PASS.
- **W0 Tier 2** (`shadow-2026-v5-w0-v4control`, as-of 2026-08-20T13:19:14Z): Spread/Total Prediction value-identical (max diff 0.0, string-identical) on all 8 games vs official `2026w0-55de0317120d`. PASS.
- **W1 exact rerun** (`7ceff06b`): content SHA `2f7566f8…` byte-identical to prod; team parent content-identical to `6d6f4da2` (`6e8cf241`). Tier 1 PASS by identity.
- **W1 Tier 2** (`shadow-2026-v5-w1-v4control`, as-of 2026-09-03T05:00:00Z): exact on all 43 games. PASS.
- **W1 path-equivalence** (assembler, no preseason → `7210bd9a`): content `2f7566f8…` byte-identical. Tier 1 PASS; **Tier 2 on assembly** (`shadow-2026-v5-w1-asm-v4control`): exact on 43/43. PASS. Task-3 W1 inputs proven clean.
- **W2 exact rerun** (`29c894cd`): content `64393952…` byte-identical; team parent content-identical to `bda6032a` (`415d6150`). Tier 1 PASS.
- **W2 Tier 2** (`shadow-2026-v5-w2-v4control`, as-of 2026-09-08T17:50:00Z): exact on all 49 games. PASS.
- **W2 path-equivalence** (assembler → `90398ae9`): content `64393952…` byte-identical. Tier 1 PASS; **Tier 2 on assembly** (`shadow-2026-v5-w2-asm-v4control`): exact on 49/49. PASS.
- Code-effect confounding is therefore zero for all three weeks: the Task-4/5 shadow-vs-official comparison isolates the feature effect alone.

### Amendment 3 (minor/technical, appended to plan — no architecture/scope/acceptance change)
- At HEAD, `point_in_time_matchups_core_v1` has no executable catalog schema, so the no-baselines builder's trailing registration fails, and the assembler's registration then FK-fails on the unregistered core parent. Builder bytes + manifests are written before registration (verified via R2 listing), content-addressed and parent-linked.
- Recovery: output ref-files minted byte-faithfully from builder-written manifests (same 5-key `DatasetRef` JSON serialization) at the prescribed shadow paths (W1 core `fa0f7c34`, W1 assembly `7210bd9a`, W2 core `1906c44b`, W2 assembly `90398ae9`, W1 v5 `882f691f`, W2 v5 `4d89b391`). No source/script/bundle/contract code modified. Catalog rows for unregistered-parent versions remain absent (optional research metadata); every assertion ran against R2 bytes.

### Task 3 — v5 shadow Gold assembly (all manifests accepted)
- W0: core `d1c5efd8` + baselines `ec13aef8` + preseason `8c47f6d5`, strict, `--as-of 2026-08-20T13:19:14Z` → `db681cef` (content `71c88222…`).
- W1: Tier-2-cleared core `fa0f7c34` + `0e6403e2` + preseason, strict, `--as-of 2026-09-03T04:00:00Z` → `882f691f` (content `516833ce…`).
- W2: Tier-2-cleared core `1906c44b` + `0e6403e2` + preseason, strict, `--as-of 2026-09-08T15:35:00Z` → `4d89b391` (content `8813916d…`).
- Each manifest: `dataset`/`schema_version` = `point_in_time_matchups_v5`, parents = (core, baselines, preseason `8c47f6d5`), `config_sha` = sha256(`model_ready_gold=v5`, strict, eligible) verified, `excludes_2020=true`, strict activation eligible, unique game keys. (Note: `model_ready_gold` lives in the config_sha preimage per assembler source, not as a manifest field.)

### Task 4 — Shadow predictions (frozen market refs, original publish cutoffs)
- `shadow-2026-v5-w0` (as-of 2026-08-20T13:19:14Z): 8/8 games. `shadow-2026-v5-w1` (2026-09-03T05:00:00Z): 43/43. `shadow-2026-v5-w2` (2026-09-08T17:50:00Z): 49/49. All `--run-state preview`, all uploaded to Preview R2. `prediction_runs`/`predictions`/`prediction_grades` counts identical before/after in both DBs; `current_week` untouched.

### Task 5 — PARTIAL (W0/W1 scored; W2 blocked; NO verdict rendered)
- Scored with final close outcomes refs (prod pipeline runs, immutable reads): W0 shadow vs `8d2e78ab…/game_outcomes_ref.json` (v`4a08b8bb`); W1 shadow vs `edb91b15…/game_outcomes_ref.json` (v`258ac854`). Scored artifacts uploaded to Preview R2. `score_to_db.py` never invoked.
- Interim evidence (independently recomputed from scored artifacts + prod grades; kill criterion NOT applied):
  - W0 shadow ≡ official exactly: spread 2-6, total 5-3 (n=8, small-sample caveat per contract).
  - W1 shadow: spread 16-26-1, identical to official 16-26-1; totals 13-28 (+2 No Bet) vs official 14-29.
  - Value-drift analysis (`shadow_drift.py`): shadow vs official predictions are **bit-identical** (max abs drift 0.0000) for every Spread/Total Prediction and every bet selection across all 8 W0 + 43 W1 games. The 2-game totals delta is a grading-convention artifact, not a prediction difference: both games were edge-below-threshold Unders (edges 0.31, 0.85 < 1.5) that the official close graded directionally (1 win + 1 loss = the exact delta) while the artifact scorer marks No Bet.
  - Net interim finding: the v5 feature rebuild moves NOTHING in W0/W1 outputs. This leans against mismatch-as-cause but is NOT a verdict (verdict requires pooled W1+W2, n=92).
- **BLOCKER:** W2 finals do not exist — first kickoff Fri 2026-09-11 23:30 UTC (verified in games Silver `5dabf61a`; today 2026-09-10); no Week 2 close-week run exists in prod ops. Scoring `shadow-2026-v5-w2` and rendering the pooled table + kill criterion must wait for the Week 2 close. The W2 shadow artifact is frozen pre-kickoff and grading-ready.

## Files Modified
- `docs/plans/2026-09-10/2026-v5-shadow-rebuild-diagnostic.md` — Approved → In Progress → `In Progress — BLOCKED on W2 finals`; new implementation log path; Amendment 3; Task-5 execution/blocker note (bookkeeping + minor amendment only; normative Tasks 1–4 untouched)
- `session_logs/2026-09-10/11-v5-shadow-rebuild-implementation-two-tier.md` — this log
- NOT touched: `docs/ops/production_runbook.md`, `.opencode/`, all source/scripts/configs/bundles/contracts, prod R2 prefixes, both serving tables

## Validation
- [x] Task 1: 15/15 refs resolve + SHA match; cutoff audit per week
- [x] Task 2: W0 Tier1 confinement (329-union) + Tier2 8/8 exact; W1 exact + Tier2 43/43 + assembly byte-identical + Tier2 43/43; W2 exact + Tier2 49/49 + assembly byte-identical + Tier2 49/49
- [x] Task 3: manifest assertions per week (dataset/schema/parents/config-preimage/excludes_2020/strict-eligible/unique-keys); assembler fail-closed gates passed unmodified
- [x] Task 4: 8/43/49 coverage + game-ID match; `prediction_runs` SELECT before/after identical in both DBs (19/821/1524 preview; 50/2377/4476 prod); `current_week` untouched
- [x] Task 5 (partial): W0/W1 scored artifacts uploaded; interim table independently recomputed from scored artifacts + prod grades; value-drift analysis confirms bit-identity
- [x] `git diff --check` clean (only plan + this log differ from HEAD apart from pre-existing unrelated work)
- [ ] Task 5 (remaining): W2 scoring + pooled W1+W2 verdict + kill criterion — blocked on Week 2 close (external, scheduled)

## Amendments and Blockers
- Amendment 3 (Terra, minor/technical): ref-minting recovery for the unregistered-core catalog gap — see Work Completed. Preserves architecture, interfaces, scope, acceptance criteria.
- Blocker (external): W2 finals pending 09-11 kickoff + Week 2 close. No contract redesign attempted; kill criterion deliberately not applied to a partial sample.

## Handoff Notes
- **Resume at (after the Week 2 close):**
  1. `zsh scripts/ops/with_preview_env.sh uv run python scripts/pipeline/score_weekly_bets.py --year 2026 --week 2 --run-id shadow-2026-v5-w2 --from-artifact --prediction-artifact-path artifacts/preview/predictions/year=2026/week=2/run_id=shadow-2026-v5-w2/predictions.csv --outcomes-ref-uri artifacts/production/pipeline-runs/<W2CLOSE_ID>/game_outcomes_ref.json --upload-artifact` (get `<W2CLOSE_ID>` from prod `ops.pipeline_runs` close-week 2026w2, as done for W0/W1).
  2. Recompute the pooled W1+W2 table from the three scored artifacts + prod grades (reuse `/var/folders/.../T/opencode/verdict_interim.py` + `shadow_drift.py` patterns), apply the kill criterion (≥50% shadow spread → confirmed; <45% → not confirmed; 45–50% → inconclusive), update plan to `Implemented`, write the closing log.
- **Watch out for:** never invoke publish/freeze/score-to-db; keep `M docs/ops/production_runbook.md` and `.opencode/` untouched; no git operations (user-controlled); Preview catalog lacks rows for `fa0f7c34`/`1906c44b`-parented versions (expected, Amendment 3); the W0 v5 `--as-of` is the publish cutoff (Amendment 2), not 08-15 — do not "fix" it.
- **Artifacts produced (all Preview R2, immutable):** Gold `db681cef`/`882f691f`/`4d89b391` (v5), `7ceff06b`/`29c894cd` (W1/W2 parity), `7210bd9a`/`90398ae9` (assemblies), cores `fa0f7c34`/`1906c44b`; refs under `artifacts/preview/shadow-2026-v5/` (incl. `refs/`); predictions `shadow-2026-v5-w{0,1,2}` + six `-v4control`/`-asm-v4control` controls; scored `shadow-2026-v5-w{0,1}`.

**tags:** ["v5-shadow", "diagnostic", "2026-season", "terra", "two-tier-gate", "blocked-w2-finals"]
