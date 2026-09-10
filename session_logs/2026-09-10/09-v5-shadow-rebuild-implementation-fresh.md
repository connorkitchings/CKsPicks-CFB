# Session: v5 Shadow Rebuild Implementation — FRESH RUN, STOPPED on Task 2 parity gate (code drift)

## TL;DR
- **Worked On:** Fresh Terra implementation of `docs/plans/2026-09-10/2026-v5-shadow-rebuild-diagnostic.md` (Amendment 1 + user re-approval 2026-09-10, Amendment 1). Executed Task 1 verification (PASS) and Task 2 W0 parity reassembly (FAIL → whole-diagnostic stop per contract stop rule).
- **Outcome:** STOPPED. W0 assembler parity rerun from byte-identical immutable parents produced content SHA `cc6b1a03…` vs prod `1f32fc0f…`. Diagnosis (read-only record comparison): **code drift in the assembler/attach path**, not nondeterminism and not provider revisions. No v5 work attempted for any week. Zero serving writes in either database; official record intact.
- **Plan Contract:** `docs/plans/2026-09-10/2026-v5-shadow-rebuild-diagnostic.md` (now `In Progress — STOPPED`, awaiting Sol revision)
- **Approval / Status:** Approved (user re-approval 2026-09-10, Amendment 1) → In Progress → STOPPED on Task 2 stop rule.
- **Blockers:** Task 2 parity gate failed (code drift). Needs Sol revision; Terra did not redesign.
- **Next:** Sol revises (recommended: column-scoped parity on model-input columns, or pinned-code rerun at `63f0458`); then a fresh Terra task resumes from Task 2.

## Context and Decisions
- Followed `.agent/skills/implement-plan/SKILL.md` §1–§4: read the full amended plan + planning log (06), stopped-run evidence (07, read-only), amendment log (08) before any writes; authorized the exact Draft path (Approved, approval source recorded); marked In Progress with this new log path; reconciled worktree (preserved `M docs/ops/production_runbook.md` and `?? .opencode/` untouched; no git add/commit).
- Storage: `CFB_STORAGE_BACKEND='r2'` (from `.env`; key lengths verified, values never printed). Preview ops via `zsh scripts/ops/with_preview_env.sh`. Production Neon: read-only SELECTs only. No `./data/` writes (`data/` is gitignored pre-existing working output).
- Never invoked `publish_to_db.py`, `freeze_week.py`, or `score_to_db.py`.
- Prior session scripts reused from `/var/folders/.../T/opencode/` (outside repo, no worktree pollution).

## Work Completed

### Authorization + reconciliation
1. Plan Draft + Amendment 1 → Approved (approval source "user re-approval 2026-09-10, Amendment 1") → In Progress with this log path. `docs/plans/index.md` entry tracks status.
2. Tooling reconciled: all four scripts present; assembler `_ref()` requires 5-key DatasetRef JSON ref-files (manifest JSON is a superset → strict `DatasetRef(**…)` would fail, so W0 needed purpose-built ref-files); `build_regime_features._ref()` picks 5 keys (tolerant).
3. Regression-guard baselines captured BEFORE any write (SELECTs only) — identical before/after:
   - prod: runs=50, preds=2377, grades=4476, `current_week`=(2026,2,`2026w2-43b25511a100` frozen)
   - preview: runs=19, preds=821, grades=1524, `current_week`=(2025,16,`v4replay-2025-w16`)
4. Official record reconciled (matches contract §1): W0 `2026w0-55de0317120d` scored (+`2026w0-79ec2aebcb00` published), W1 `2026w1-b2c739321e5d` scored, W2 `2026w2-43b25511a100` frozen. Prod `input_dataset_refs` re-read: matchups SHAs `1f32fc0f…`/`2f7566f8…`/`64393952…`, markets (`07336aaa`/`e3f984c4`, `b273e83d`, `459c80d0`+quotes `ede4a9a7`), games `5dabf61a` — all match the contract.

### Task 1 — PASS (read-only; no stop triggered)
- All 15 refs resolve in R2 with matching content SHAs: W0 core `d1c5efd8` (`a381de33…`), W0 baselines `ec13aef8` (`d41e40a9…`), W0 matchups `74ffdbbf` (`1f32fc0f…`, as_of 2026-08-15T14:42Z, parents `[d1c5efd8, ec13aef8]`, schema v4), W1 team `6d6f4da2` + matchups `30ac8b5d` (`2f7566f8…`, as_of 2026-09-03T04:00Z, schema v3), W2 team `bda6032a` + matchups `9b7bc478` (`64393952…`, as_of 2026-09-08T15:35Z, schema v3), baselines `0e6403e2` (as_of 08-09), preseason `8c47f6d5` (coverage `feature_track=strict`, `activation_eligible=true`, `validation.excludes_2020=true`, `strict_track_activation_eligible=true`, as_of 08-17), games `5dabf61a`, all five market/quote refs.
- Cutoff audit PASS: every input `as_of` ≤ first kickoff (W0 ≤ 08-29 incl. market scored 08-20T13:19Z; W1 04:00/05:00Z ≤ Thu-evening kickoff; W2 09-08 ≤ 09-11; baselines/games 08-09; preseason 08-17 precedes all three publish cutoffs).
- Builder argv recovered from Preview `ops.pipeline_steps` (W1 prepare `c9b80bf1…` step 13, W2 prepare `3eb4c566…` step 15): exact `build_regime_features.py --matchups-ref-uri …/temporal_matchups_ref.json --schedule-ref-uri …/schedule_2021_2026_ref.json --baselines-ref-uri artifacts/preview/refs/history/baselines-selection.json --as-of <cutoff> --environment preview`. Temporal parents confirmed: W1 `ef3380e0` + schedule `70aef191`; W2 `ace30e9c` + schedule `9432081e`. `baselines-selection.json` → `0e6403e2` (verified).
- `git diff --check` clean (no worktree changes from verification).

### Task 2 — W0 parity FAIL (stop rule tripped)
- Wrote 3 purpose-built 5-key ref-files under `artifacts/preview/shadow-2026-v5/refs/` (Preview R2, shadow prefix, immutable discipline — write-if-absent, assert-identical-if-present): `w0-core-d1c5efd8.json`, `w0-baselines-ec13aef8.json`, `preseason-8c47f6d5.json` (for Task 3, unused). Backing `data.parquet` existence verified first.
- Ran (Preview env): `assemble_model_ready_features.py --core-ref-uri …/w0-core-d1c5efd8.json --baselines-ref-uri …/w0-baselines-ec13aef8.json --as-of 2026-08-15T14:42:00Z --output-ref-uri artifacts/preview/shadow-2026-v5/w0-parity-point_in_time_matchups_ref.json --environment preview` (no preseason, no markets — exact Task-2 prescription).
- Result: new version `c89b4567b164123d048999fe`, content SHA `cc6b1a03…` ≠ prod `1f32fc0f…`. **PARITY FAILED.** New version_id differs inherently (identity hashes `code_sha` 63f0458→41d1a2d); the gate compares content SHA, so this is a genuine payload difference.
- Per stop rule ("any week that fails parity stops the whole diagnostic"), did NOT run W1/W2 reruns, path-equivalence, or any Task 3–5 work.

### Diagnosis (read-only record comparison, prod `74ffdbbf` vs rerun `c89b4567`)
- Same 4491 rows, same game_ids, same 2026 slice (761 rows), same parents `[d1c5efd8, ec13aef8]` (checksums verified on read — parents are immutable and intact).
- **5 extra columns in rerun** (`current_spread_prediction`, `current_total_prediction`, `preseason_spread_prediction`, `preseason_total_prediction`, `training_max_year`) — all-NaN in the 2026 slice. The immutable baselines parent is unchanged, so the current `attach_baseline_predictions` retains columns the 08-15 code dropped (or vice versa).
- **16 differing common columns** (`*_prior_*` weather/rest/neutral-site, e.g. `home_prior_weather_missing`): prod = all-`None` object dtype; rerun = all-`NaN` float64. This is exactly the assembler lines 156–164 missingness coercion (`pd.to_numeric` on `*_missing`/`*_neutral_site` object columns) — a deliberate post-08-15 code change. Semantically null (all-missing either way) but hash-relevant.
- Original manifest has `coverage={}` (older assembler wrote no coverage); rerun writes `{activation_eligible, feature_track, preseason_feature_ref}` — further code-drift confirmation. (Manifest differences don't affect content SHA.)
- **Implication verdict: code drift.** Deterministic given code (not nondeterminism); parents immutable + checksummed (not provider revisions). Lineage is trustworthy; the byte-parity gate is stale relative to HEAD.
- Inference impact (for Sol, NOT assumed): the 5 extra columns are all-null in 2026 and the 16-col diff is None↔NaN all-missing — plausibly inference-inert under `v4_2026.yaml` (`prior_only_fallback`), but that must be PROVEN by a column-scoped parity, not assumed.

## Files Modified
- `docs/plans/2026-09-10/2026-v5-shadow-rebuild-diagnostic.md` — Draft → Approved → In Progress → `In Progress — STOPPED` + approval source + new log path (bookkeeping only; normative content untouched, no new amendment)
- `docs/plans/index.md` — entry tracks the stop (bookkeeping only)
- `session_logs/2026-09-10/09-v5-shadow-rebuild-implementation-fresh.md` — this log
- NOT touched: `docs/ops/production_runbook.md`, `.opencode/`, all source/scripts, prod R2 prefixes, both serving tables

## Validation
- [x] Task 1: `storage.exists` + SHA match per ref (15/15); cutoff audit per week; `git diff --check`
- [x] Task 2 W0: SHA equality check recorded (`cc6b1a03…` ≠ `1f32fc0f…` → FAIL, stop invoked)
- [x] `prediction_runs`/`predictions`/`prediction_grades` counts identical before/after in BOTH databases (SELECTs only); `current_week` untouched (2026w2 frozen / 2025w16 replay)
- [x] `git diff --check` clean after all work
- [ ] Tasks 2 (W1/W2) –5: not executed (blocked by stop rule)
- R2 writes issued (Preview only, permitted research metadata — NOT serving state): 3 small ref JSONs under `artifacts/preview/shadow-2026-v5/refs/`, 1 parity output ref + 1 new Gold version `c89b4567` (+ Preview catalog registration). No production-prefix writes. No DB row writes.

## Amendments and Blockers
- No unilateral amendment (material deviation → stop per skill §3). Assembler `--as-of` note for Sol: Task 3's W0 v5 assembly at `--as-of 2026-08-15T14:42Z` would backdate the 08-17 preseason parent (assembler does not enforce parent recency; `as_of` is a label). A revised contract should pin the W0 v5 `as_of` to ≥ max parent recency (e.g. publish cutoff `2026-08-20T13:19:14Z`).
- Recommended Sol revisions (not executed): (a) column-scoped parity — compare only `v4_2026.yaml` model-input columns between prod Gold and rerun; if equal, lineage is inference-sound and Tasks 3–5 proceed; (b) alternative: pinned-code rerun at `63f0458` for byte parity. Either needs a contract amendment (Amendment 2).

## Handoff Notes
- **Resume at:** Sol writes Amendment 2 (column-scoped parity or pinned-code rerun + W0 v5 `as_of` pin); then a fresh Terra task executes the amended Task 2→5. Reusable artifacts already in place: shadow ref-files (`artifacts/preview/shadow-2026-v5/refs/`), W1/W2 builder argv + input refs (§Task 1), prod market/games refs, guard baselines above.
- **Watch out for:** never invoke publish/freeze/score-to-db; keep `M docs/ops/production_runbook.md` and `.opencode/` untouched; no git operations (user-controlled); Preview catalog now contains versions `c89b4567` (failed-parity rerun) — clearly labeled by its output ref path, must not be mistaken for a valid shadow input.

**tags:** ["v5-shadow", "diagnostic", "2026-season", "terra", "stopped", "parity-gate", "code-drift"]
