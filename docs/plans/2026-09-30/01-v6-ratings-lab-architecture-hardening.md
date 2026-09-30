# V6 Ratings Lab: Architecture Hardening

- **Status:** Implemented
- **Created:** 2026-09-30
- **Planner:** Sol (fast path — additive, no production or model change)
- **Approval source:** User accepted the proposed changes in session conversation 2026-09-30.
- **Implementation log:** `session_logs/2026-09-30/02-v6-lab-architecture-hardening.md`
- **Commit policy:** User executes git operations manually.

## Goal

Harden the `ratings_lab/` research platform before beginning V6 methodology
exploration. Specifically: (1) add a parameterized candidate factory with a
YAML registry for hyperparameter sweeps; (2) unlock the measurement recipe
layer so future non-PPP recipes can be registered without a code-gate change;
(3) document deferred architectural decisions so their rationale is preserved.
No production code, production data, V5 artifacts, Neon database, or public
site is changed.

## Context

The V5 ratings lab platform was built on 2026-09-28 and verified locally
end-to-end. Five architectural gaps were identified during a 2026-09-30
audit session:

| Gap | Decision |
|---|---|
| R2 research bucket | **Deferred** — local-only acceptable for research iteration; provision when a V6 candidate is worth long-term preservation (see §Deferred Decisions) |
| Parameterized candidate factory | **Implement now** — needed for efficient V6 hyperparameter sweeps |
| Measurement flexibility | **Implement now** — V6 may revisit what is being measured, gate removal unblocks future recipes |
| Opponent adjustment experimentation | **Deferred** — keep four-pass fixed; worth its own research contract later (see §Deferred Decisions) |
| Bridge experimentation | **Keep fixed by design** — common α=10 bridge isolates rating attribution; bridge research is a separate future contract |
| Batch orchestration | **Deferred** — add when manual per-candidate loop becomes friction |

## Scope

Changes are limited to:

- `src/cks_picks_cfb/ratings_lab/updaters.py` — parameterized factory + YAML loader
- `src/cks_picks_cfb/ratings_lab/measurements.py` — unlock recipe gate
- `scripts/research/ratings_lab.py` — YAML candidate loading at startup
- `conf/research/candidates/` — YAML candidate definitions (new directory)
- `tests/ratings_lab/test_platform.py` — new tests for factory and recipe gate
- `docs/research/ratings-lab-v1.md` — updated operator guide
- This plan and session log

No changes to: V5 production runners, `scripts/pipeline/`, `src/cks_picks_cfb/` outside
`ratings_lab/`, `contracts/`, `web/`, Neon, R2 artifacts.

## Ordered Implementation Tasks

### Task 1 — Parameterized Candidate Factory

Add `ParameterizedDesign` to `updaters.py`: a dataclass that accepts
`candidate_id`, `k` (equivalent exposure, float > 0), `rho` (carryover
decay, 0 < rho <= 1.0), and `mode` (`incremental` or `cumulative`).
`initialize` applies rho-carryover and `estimate` runs the existing
exposure-weighted Bayesian posterior.

Add a `load_candidate_configs` function that reads a directory of YAML files.
Each YAML file defines:

```yaml
candidate_id: exposure_k4_rho06_v1
type: parameterized_exposure   # only registered type for now
k: 4.0
rho: 0.60
mode: incremental
```

The loader validates required fields, `type` membership, and parameter
bounds, then returns a `dict[str, RatingDesign]` ready for `REGISTRY`.
No YAML file may redefine a name already in the code registry.

### Task 2 — CLI YAML Candidate Loading

Update `scripts/research/ratings_lab.py` to load candidate configs from
`conf/research/candidates/` at startup and register them into `REGISTRY`
before the command runs. The `--candidate` argument resolves from the
combined code + YAML registry as before. No change to existing command
signatures.

Add an initial set of YAML candidate files covering the V5 baseline
hyperparameters (k=8, rho=0.60) plus a small illustrative sweep:
`k4_rho06`, `k8_rho06` (V5 baseline), `k12_rho06`, `k8_rho05`, `k8_rho07`.

### Task 3 — Measurement Recipe Gate Removal

In `measurements.py`, remove the hard `recipe_id != "v5_raw_ppp_game_v1"`
check inside `build_individual`. Replace with a registry of known builder
functions keyed by `recipe_id`. The PPP builder is the only registered
entry for now; an unknown recipe raises `ValueError("unregistered
measurement recipe: {recipe_id}")`. `MeasurementRecipe` gains an optional
`description` field for documentation.

The existing `availability_policy` guard in `MeasurementRecipe.__post_init__`
likewise becomes a registered set so a future policy can be added without
changing the dataclass.

### Task 4 — Tests

Add focused tests to `tests/ratings_lab/test_platform.py`:

- `test_parameterized_design_initialize_and_estimate` — verifies rho
  carryover, k-scaling, and explanation fields.
- `test_yaml_candidate_loading` — writes a minimal YAML to a tmp dir, loads
  it, confirms the resulting design is runnable through `replay`.
- `test_yaml_duplicate_rejection` — confirms a YAML that reuses a
  code-registry name raises `ValueError`.
- `test_measurement_recipe_extensible` — confirms an unknown recipe raises
  `ValueError("unregistered")` and the PPP recipe still works.

### Task 5 — Documentation

Update `docs/research/ratings-lab-v1.md`:

- Add a "Candidate definitions" section explaining the YAML schema and
  `conf/research/candidates/` directory.
- Add references to §Deferred Decisions below.

## Deferred Decisions

These are documented here so future sessions have the rationale without
re-auditing the architecture.

### R2 Research Bucket (deferred 2026-09-30)

A private Cloudflare R2 bucket (`cks-picks-cfb-research` or similar) with
scoped `CFB_R2_LAB_SOURCE_*` / `CFB_R2_LAB_*` credentials is the intended
durable storage backend. It was not provisioned during initial platform
implementation (2026-09-28) and remains absent. Local-only operation with
`LocalLabStore` is acceptable during early V6 research iteration — results
are reproducible from pinned SHA-256 parents.

**Provision when:** a V6 candidate reaches the stage where you want to
preserve its run identity for long-term comparison, or when running
experiments across multiple machines.

**Effort:** ~15 minutes. Code is already written in `artifacts.py`;
the CLI switches backends automatically on credential presence.

**Implementation contract:** V6 ratings research platform plan
(`docs/plans/2026-09-28/v6-ratings-research-platform.md`) Task 5 covers
the acceptance sequence.

### Opponent Adjustment Experimentation (deferred 2026-09-30)

The four-pass league-centered additive opponent adjustment (D6) is fixed
for V6. `CutoffAdjustment` imports directly from the V5 production
materializer. Experimenting with alternative adjustment strategies (e.g.,
recency-weighted passes, convergence criteria, opponent-role weighting)
would require either modifying `CutoffAdjustment` or introducing an
adjustment protocol analogous to `RatingDesign`.

**Consider when:** a V6 candidate's performance suggests the adjustment is
a meaningful source of error, or when football-measurement research provides
independent motivation for a different adjustment model.

**Effort:** medium refactor — extract an `AdjustmentDesign` protocol, move
`CutoffAdjustment` to one implementation, update `adjusted_game.py` and
`corpus.py` to accept the abstraction.

### Batch Candidate Orchestration (deferred 2026-09-30)

The CLI runs one candidate at a time. Sweeping N candidates requires N
separate `replay` + `evaluate` invocations sharing one corpus and
measurements stage.

**Add when:** manual looping across candidates becomes friction in practice
(likely once V6 has 5+ actively sweeping candidates).

**Effort:** ~30 minutes — a wrapper script that iterates `REGISTRY` or a
provided list, calls the existing CLI entry point per candidate, and
produces a combined comparison table.

## Validation and Definition of Done

- [ ] `uv run pytest tests/ratings_lab/ -q` — all existing + new tests pass.
- [ ] `uv run ruff check src/cks_picks_cfb/ratings_lab/ scripts/research/ratings_lab.py` — no errors.
- [ ] `uv run ruff format --check src/cks_picks_cfb/ratings_lab/ scripts/research/ratings_lab.py` — no diff.
- [ ] A YAML-defined candidate (e.g., `exposure_k4_rho06_v1`) runs through `replay` locally without error.
- [ ] `build_individual` with an unknown recipe ID raises `ValueError("unregistered")`.
- [ ] `uv run mkdocs build --quiet` — no new warnings.
- [ ] `git diff --check` — clean.
- [ ] No V5 artifact, production runner, Neon row, or public site changed.

## Risks and Amendment Rule

Additive changes only. No risk to V5 production or the active weekly
operating cadence. A material change to storage isolation, corpus
eligibility, evaluation folds, estimator semantics, or production boundaries
requires a separate approved amendment.
