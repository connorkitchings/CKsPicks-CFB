# Session: V6 Ratings Lab Architecture Hardening

## TL;DR
- **Worked On:** V6 ratings lab architectural hardening prior to methodology research. Implemented parameterized candidate factory, YAML candidate loader & registry, extensible measurement recipe registry, and documentation updates.
- **Outcome:** Hard PPP-only measurement gate removed in favor of extensible builder registry; `ParameterizedDesign` and YAML-based candidate loading in `conf/research/candidates/` implemented and hooked into lab CLI; 4 new unit tests added (all 19 tests pass); deferred architecture decisions documented. Completed V6 conceptual design and documented architecture and execution roadmap in `docs/research/v6-ratings-architecture-design.md`.
- **Plan Contract:** [`docs/plans/2026-09-30/01-v6-ratings-lab-architecture-hardening.md`](../../plans/2026-09-30/01-v6-ratings-lab-architecture-hardening.md)
- **Approval / Status:** User approved plan and authorized implementation; Implemented and validated. Conceptual design and 4-phase research roadmap finalized.
- **Blockers:** None.
- **Next:** Execute Phase 1 of V6 research roadmap: Implement deterministic 4-factor measurement recipe in `ratings_lab/measurements.py`.

## Context and Decisions
- **Gap Decisions:**
  1. *Dedicated R2 bucket:* Deferred. Local storage remains the research engine until bucket credentials are provisioned.
  2. *Parameterized Candidate Factory:* Implemented class-based `ParameterizedDesign` and YAML registry loader. Created initial hyperparameter sweep configs (k in [4, 8, 12], rho in [0.5, 0.6, 0.7]).
  3. *Measurement Recipe Extensibility:* Unlocked `MeasurementRecipe` with recipe and policy registries, removing hard PPP gate without introducing unverified measurement types yet.
  4. *Opponent Adjustment:* Kept fixed to V5 logic for initial candidate comparison; deferred to dedicated study.
  5. *Common Bridge:* Kept fixed to Ridge alpha-10 expanding bridge on strictly earlier seasons.
  6. *Batch Orchestration:* Deferred; single-candidate CLI preserved for now.
- **V6 Methodology Decisions:**
  1. *Decomposition:* Separate Offense & Defense ratings.
  2. *State Representation:* 4-Factor profile (Rush SR, Rush Explosiveness, Pass SR, Pass Explosiveness) computed deterministically from down, distance, and yards gained.
  3. *State Update:* Exposure-Weighted Kalman Filter ($\mathbf{R}_t = \boldsymbol{\Sigma}_{\text{noise}} / n_t$) with weekly process drift ($\mathbf{Q}$).
  4. *Opponent Adjustment:* Point-in-time retrospective schedule re-anchoring up to weekly cutoffs $T$; FCS opponents handled via Option B (synthetic baseline anchor with capped delta).
  5. *Preseason Priors:* Continuity-informed priors blending previous-season terminal state with returning production, recruiting composite, and coaching stability.
  6. *EPA Model:* Custom CFB EPA model deferred; using deterministic Success Rate & IsoPPP.

## Work Completed
- Created `conf/research/candidates/` with 5 initial YAML sweep configs and schema README.
- Implemented `ParameterizedDesign` and `load_candidate_configs()` in `src/cks_picks_cfb/ratings_lab/updaters.py`.
- Integrated `_load_yaml_candidates()` into `scripts/research/ratings_lab.py`.
- Replaced hard PPP gate in `src/cks_picks_cfb/ratings_lab/measurements.py` with `register_recipe` and `register_availability_policy`.
- Added 4 unit tests covering parameterized design math, YAML loading, duplicate ID rejection, and extensible measurement recipes in `tests/ratings_lab/test_platform.py`.
- Updated `docs/research/ratings-lab-v1.md` with YAML candidate schema and deferred decision links.
- Created `docs/research/v6-ratings-architecture-design.md` detailing the complete V6 architecture, deterministic formulas, policy invariants, and 4-phase research roadmap.

## Files Modified
- `docs/plans/2026-09-30/01-v6-ratings-lab-architecture-hardening.md` - Execution plan contract.
- `src/cks_picks_cfb/ratings_lab/updaters.py` - `ParameterizedDesign` and `load_candidate_configs`.
- `src/cks_picks_cfb/ratings_lab/measurements.py` - Extensible measurement recipes and builder registry.
- `scripts/research/ratings_lab.py` - YAML candidate loading on CLI entry.
- `conf/research/candidates/*.yaml` - Initial 5 candidate YAML definitions.
- `conf/research/candidates/README.md` - Documentation of candidate schema.
- `tests/ratings_lab/test_platform.py` - 4 unit tests for new functionality.
- `docs/research/ratings-lab-v1.md` - Documentation updates.
- `docs/research/v6-ratings-architecture-design.md` - V6 conceptual architecture, formulas, and execution roadmap.

## Validation
- [x] `uv run pytest tests/ratings_lab/ -q` (19 passed)
- [x] `uv run ruff check src/cks_picks_cfb/ratings_lab/ scripts/research/ratings_lab.py tests/ratings_lab/` (0 errors)
- [x] `uv run ruff format --check src/cks_picks_cfb/ratings_lab/ scripts/research/ratings_lab.py tests/ratings_lab/` (clean)
- [x] `uv run mkdocs build --quiet` (clean build)
- [x] `git diff --check` (clean)

## Amendments and Blockers
- None.

## Handoff Notes
- **Resume at:** Phase 1 of V6 research roadmap: Implement deterministic 4-factor measurement recipe in `ratings_lab/measurements.py`.
- **Watch out for:** Keep production pipelines and V5 artifacts untouched; all V6 research remains private in `ratings_lab/`.

**tags:** ["research", "ratings_lab", "v6", "architecture", "testing", "design", "roadmap"]
