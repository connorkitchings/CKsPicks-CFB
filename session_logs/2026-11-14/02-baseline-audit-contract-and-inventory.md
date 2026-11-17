# Session: V5 baseline audit contract and local inventory

## TL;DR

- **Worked On:** Planning how to analyse V5 before any V6 candidate; two rounds of owner review; a Draft contract and a local read-only inventory.
- **Outcome:** The Draft contract names three baselines (Historical V5, Operational V5, Closed V6), records a hash-checked inventory, sets a six-step work order and proposes five protocol amendments. Main finding: no historical replay of Operational V5 exists, and the retained repair experiment differs from the serving model in input lineage as well as bridge fitting.
- **Plan Contract:** [`docs/plans/2026-11-14/01-v5-baseline-audit-and-analysis-framework.md`](../../docs/plans/2026-11-14/01-v5-baseline-audit-and-analysis-framework.md)
- **Approval / Status:** Owner approved the Draft and the local inventory on 2026-11-14. Contract is `Draft`; each later step needs its own approval.
- **Blockers:** Step 2 needs a credentialed read-only retrieval of inputs that are not on this machine.
- **Next:** Owner decides whether to approve the next executable scope in the contract (retrieval into a hash-verified local cache; read the serving bridge manifest).

**tags:** ["planning", "model-research", "baseline-audit", "ratings-lab"]

## Context and Decisions

- The first framework draft was sent back with seven corrections, all confirmed against the code: the diagnostics describe Historical V5, not the serving model; the lab replays rating states from certified inputs and is not an end-to-end rebuild; hindsight and in-sample comparisons were over-interpreted; pace was asserted as the cause of flat totals without ruling out alternatives; 2022 to 2025 and 2026 are already examined; residual screens were over-interpreted; market use needed a firmer boundary.
- A second review added: separate historical reproduction from operational equivalence; state the temporal rule exactly and check the whole dependency chain; do not claim season/week resampling is stricter; make today's scope an explicit stopping point.
- Owner decisions this session: market comparison is reported only after football-based priorities are frozen; exploration and tuning use 2015 to 2019 and 2021, with no claim that this restores independence for 2022 to 2025; existing adoption thresholds stay until amendments are separately decided.

## Work Completed

- Hashed every child of the 30 local ratings-lab stage manifests: all match. One corpus stage (Historical V5) and 29 Closed V6 stages.
- Read the serving model manifest: bridge bundle `v5-intended-update-corrected-w5-r1`, and priors, terminal, population and events from `6a-rebuild-w6-20261012-r2`.
- Confirmed the repair experiment's parent hashes equal the corpus parents, and that its 12 row-level outputs are not on this machine.
- Wrote the Draft contract, listed it in the plans index, corrected the direction document, and added a baseline caveat to the diagnostics report and its generator.

## Files Modified

- `docs/plans/2026-11-14/01-v5-baseline-audit-and-analysis-framework.md` — new Draft contract
- `docs/plans/index.md` — contract listed
- `docs/planning/direction-2026-11-14.md` — corrected the reasoning and Phase 2 item 1
- `docs/modeling/prediction_error_diagnostics_2021_2025.md` — baseline caveat
- `scripts/research/run_prediction_error_diagnostics.py` — the same caveat in the generator text

## Validation

- [x] `uv run mkdocs build --strict`
- [x] `git diff --check`
- [x] `uv run ruff check` and `ruff format --check` on the edited script
- [ ] Byte-identity of the regenerated diagnostics report was not checked: the script was not run, because no scoring run is authorized by this task. The caveat text was added identically by hand in both places.

## Amendments and Blockers

- None to an approved contract. The five protocol amendments are proposed only.

## Handoff Notes

- **Resume at:** the "Next executable scope" section of the contract.
- **Watch out for:** `~/cfb_ratings_lab_v6/output/score-attribution/` holds 2026 play data and unverified 2021 to 2025 caches; research code must not use either as verified input. No pushes to `dev` during the Sunday and Monday weekly runs.
