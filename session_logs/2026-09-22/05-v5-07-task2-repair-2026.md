# Session: V5-07 Task 2 — Repair-2026 Extension Run (Terra)

## TL;DR
- **Worked On:** Terra execution of Contract 07 Task 2 — new Repair run covering 2026 completed games (W0–W3), anchored on certified Repair v2.
- **Outcome:** Task 2 **complete**. Certified Repair-2026 manifest in Preview R2: run `repair-2026-20260922T144500Z` (code `53e60ae…`), population 157/157/157 with 0 omission issues, independently verified by Repair verifier v3 (`verified`, zero producer imports), idempotent repeat refuses correctly. Zero provider calls; zero catalog writes; Repair v2 byte-identical; production untouched.
- **Plan Contract:** `docs/plans/2026-09-18/07-v5-2026-repair-and-measurement-extension.md` (Status: In Progress — Task 3 pending)
- **Approval / Status:** Re-review contract authorized execution 2026-09-22. No blockers.
- **Next:** Task 3 — 2026 possession measurement certification against this Repair-2026 parent.

## Context and Decisions
- Preflight (dry run, zero writes) reviewed before apply: identity binds the Repair v2 anchor + exact 2026 Silver inputs with scope `season_2026`; population 157/157/157; capture plan fully `existing_capture`.
- Two in-run corrections, both fail-closed behaviors working as designed:
  1. Anchor check first failed on `verify_parent` (asserts top-level seasons; repair manifests carry seasons inside identity) → rewrote `_verify_repair_v2_anchor` to validate raw/canonical SHAs, signature, schema, state, season set, env, and production flag directly (committed before apply per the runner's seal).
  2. First apply failed closed at catalog registration — `register_schema_version` correctly refused same-name drift on the amended schemas. Resolution: the 2026 extension writes R2 only (measurement-runner precedent), skipping catalog registration via an explicit `register` flag. This satisfies the no-Neon-writes DoD strictly; lineage lives in the repair manifest. Version IDs are content-derived, so the retry was byte-identical to the partial write.
  3. Retry with the same run-id refused correctly (identity.json from attempt 1 vs new code SHA) → fresh run-id `repair-2026-20260922T144500Z`. The superseded `...T145000Z` prefix holds only identity.json + capture-plan.json (no manifest) and stays as read-only stopped-run evidence.
- 2026 auxiliary families all `rejected (missing_or_constant_modeled_feature)`: the historical capture set has no 2026 preseason rows — genuine absence, recorded honestly with reasons (552 rows, 465 issues rows). Measurement consumes the population only; Contract 08 assembles priors through the preseason ingestion path directly.
- Preview-branch ingestion request-set header is the only Neon touch (capture resume bookkeeping, established mechanism); no serving-schema, production-branch, or web writes.

## Certified Evidence
- **Run ID:** `repair-2026-20260922T144500Z` (code SHA `53e60ae7cf798b716894414543930e4a71420587`, config = sealed default `repair_v2.yaml`)
- **Manifest:** `artifacts/research/data-first-football-v1/repair/v2/runs/repair-2026-20260922T144500Z/repair-manifest.json` (SHA `eeab3ccab5e88b4952f185b319eaaf575f68de088a72e3fc19d56814adfb69cf`)
- **State/timing:** `repaired_live_only` / `live`; `production_activation_authorized: false`
- **Population:** scheduled 157, forecast_eligible 157, measurement_usable 157, omission_issues 0
- **Outputs:** population 157, auxiliary 552, coverage 23, issues 465, capture_plan 2
- **Parents:** historical anchor Repair v2 (`b55af0dd…`/`2fefcb95…`) + 2026 Silver bundle `season-2026-w0-w3.json`
- **Verification:** v3 `--expected-state repaired_live_only` → `verified` (manifest raw `d4825ee3…`, 157 games, 0 forbidden-2020 rows, `producer_imports_present: false`)
- **Idempotent repeat:** re-apply refused with "run identity already exists" (immutability enforced)
- **Untouched proofs:** Repair v2 raw SHA still `b55af0dd…`; prod serving 52/2492/4657; preview serving 19/821/1524; preview catalog repair_* still 3 versions each (zero catalog writes)

## Work Completed
- Anchor-check fix + R2-only registration flag (committed pre-apply per runner seal).
- Preflight reviewed → apply (`applied`) → v3 verification (`verified`) → repeat refusal.
- Serving-table guards before/after in both databases; catalog write-absence verified.

## Files Modified
- `scripts/research/run_data_first_repair_v2.py` — anchor check rewrite, `register` flag (committed pre-apply as `53e60ae`)
- `docs/plans/2026-09-18/07-v5-2026-repair-and-measurement-extension.md` — Task 2 checkbox (this session)
- `session_logs/2026-09-22/05-v5-07-task2-repair-2026.md` — this log
- R2 (Preview research prefix): `repair/v2/runs/repair-2026-20260922T144500Z/` (manifest + 5 datasets + identity/capture-plan); lake Silver/Gold content-addressed versions

## Validation
- [x] Preflight dry run reviewed (157/157/157, existing captures, correct identity)
- [x] Apply exit 0 (`applied`)
- [x] Independent v3 verification (`verified`, zero producer imports)
- [x] Idempotent repeat refuses correctly
- [x] Repair v2 byte-identical; serving guards identical; zero catalog writes
- [x] `git diff --check` (contract/log only; code committed pre-apply)

## Amendments and Blockers
- None against the contract. Implementation notes above (anchor check shape, R2-only registration, auxiliary honesty) are within the contract's amendment allowances.

## Handoff Notes
- **Resume at:** Task 3 measurement preflight (dry run): measurement runner with `--repair-manifest-uri <Repair-2026 manifest> --run-id possession-2026-<ts> --expected-code-sha <HEAD> --environment preview --as-of <ts> --config conf/research/data_first_football_v1/possession_measurement_2026_v1.yaml`. Preflight cross-checks the config's 157/157 declaration against this manifest — expected to agree.
- **Watch out for:** Task 3 apply requires the committed evidence checkpoint for Task 2 first (runner seals). The `...T145000Z` prefix is stopped-run evidence, not a parent — never bind it.

**tags:** ["v5-07", "task-2", "repair-2026", "certified", "verified"]
