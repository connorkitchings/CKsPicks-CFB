# V6 Ratings Lab: Phase 1 — Deterministic 4-Factor Measurement Recipe

- **Status:** Implemented
- **Created:** 2026-09-30
- **Planner:** Sol (with auditing review integration)
- **Approval source:** User handoff brief & explicit authorization on 2026-09-30.
- **Implementation log:** `session_logs/2026-09-30/03-v6-phase1-measurement-recipe.md`
- **Commit policy:** User executes git operations manually.

---

## 1. Goal

Implement the foundational measurement layer for V6 ratings research:
1. Deliver the **deterministic 4-factor measurement recipe** (`v6_4factor_game_v1`), computing Rush Success Rate, Rush Explosiveness, Pass Success Rate, and Pass Explosiveness across all 10 seasons (2015–2019, 2021–2025).
2. Wire CLI `--recipe` and `--measurement-id` flags in `scripts/research/ratings_lab.py` so the laboratory can execute non-PPP recipes end-to-end.
3. Resolve the 4 code-integrity fixes identified during the independent audit review (hardening candidate parsing, missing directory behavior, test registry teardown, and real-registry collision tests).
4. Enforce strict play taxonomy, goal-to-go rules, dual explosiveness metrics, and per-factor exposure invariants.

---

## 2. Locked Specifications & Mathematical Definitions

### A. Play Taxonomy & Eligibility
Operates strictly on non-garbage regulation plays (`quarter in {1, 2, 3, 4}` and `garbage == 0`), reusing the existing V5 garbage time definitions (Q3 lead $\ge 35$, Q4 lead $\ge 27$).

| Play Category | Included / Excluded | Classification | Rationale |
| :--- | :--- | :--- | :--- |
| **Rush** | Included | Rushing attempt | Standard run plays (tailback, QB design). |
| **Pass** (Completion / Incompletion / Interception) | Included | Passing attempt | Standard pass plays. Incompletions/INTs have yards=0, success=0. |
| **Sack** | Included | Passing attempt | CFB box score convention treats sack as rushing yards lost, but analytical convention treats it as a failed pass dropback. |
| **QB Scramble** | Included | Rushing attempt | Ball crosses line of scrimmage via rush. |
| **Spike / Clock-Kill** | Excluded | Dead play | Tactical clock stop; non-diagnostic of offensive ability. |
| **Kneel / Victory Formation** | Excluded | Dead play | End-of-half/game clock bleed; non-diagnostic. |
| **Penalties (No Play)** | Excluded | Pre-snap penalty | No official play occurred. |
| **Penalties (Declined / Accepted on play)** | Included | By play result | Yards gained and down converted per official outcome. |
| **2-Point Conversions** | Excluded | Untimed untracked | Untimed scoring event; not an 11-on-11 scrimmage drive play. |
| **Overtime Plays** | Excluded | Post-regulation | Untimed untargeted format; breaks standard possession metrics. |

### B. Success Criteria & Goal-to-Go
Let $Y$ be yards gained, $D$ be down, $YTF$ be yards to first down, and $YTG$ be yards to goal.
- If $YTF > 0$:
  - 1st Down: $S = 1$ if $Y \ge 0.50 \times YTF$, else 0.
  - 2nd Down: $S = 1$ if $Y \ge 0.70 \times YTF$, else 0.
  - 3rd & 4th Down: $S = 1$ if $Y \ge 1.00 \times YTF$, else 0.
- If $YTF == 0$ (or missing/goal-to-go where $YTG \le YTF$):
  - 1st Down: $S = 1$ if $Y \ge 0.50 \times YTG$, else 0.
  - 2nd Down: $S = 1$ if $Y \ge 0.70 \times YTG$, else 0.
  - 3rd & 4th Down: $S = 1$ if $Y \ge YTG$, else 0.

### C. The Four Factors & Dual Explosiveness
For each team-game-role (offense and defense):
1. **Rush Success Rate:**
   $$\text{Rush SR} = \frac{\sum_{i \in \text{Rushes}} S_i}{N_{\text{rush}}}, \quad \text{Exposure } n_{\text{rush\_sr}} = N_{\text{rush}}$$
2. **Rush Explosiveness:**
   - **Primary Metric (`rush_expl`):** Yards per successful rush:
     $$\text{Rush Expl} = \frac{\sum_{i \in \text{Rushes}, S_i=1} Y_i}{\sum_{i \in \text{Rushes}} S_i}$$
   - **Diagnostic Metric (`rush_expl_margin`):** Yards gained beyond needed success threshold per successful rush:
     $$\text{Rush Margin} = \frac{\sum_{i \in \text{Rushes}, S_i=1} (Y_i - \text{Threshold}_i)}{\sum_{i \in \text{Rushes}} S_i}$$
   - **Exposure:** $n_{\text{rush\_expl}} = \sum_{i \in \text{Rushes}} S_i$.
3. **Pass Success Rate:**
   $$\text{Pass SR} = \frac{\sum_{i \in \text{Passes}} S_i}{N_{\text{pass}}}, \quad \text{Exposure } n_{\text{pass\_sr}} = N_{\text{pass}}$$
4. **Pass Explosiveness:**
   - **Primary Metric (`pass_expl`):** Yards per successful pass:
     $$\text{Pass Expl} = \frac{\sum_{i \in \text{Passes}, S_i=1} Y_i}{\sum_{i \in \text{Passes}} S_i}$$
   - **Diagnostic Metric (`pass_expl_margin`):** Yards gained beyond needed success threshold per successful pass:
     $$\text{Pass Margin} = \frac{\sum_{i \in \text{Passes}, S_i=1} (Y_i - \text{Threshold}_i)}{\sum_{i \in \text{Passes}} S_i}$$
   - **Exposure:** $n_{\text{pass\_expl}} = \sum_{i \in \text{Passes}} S_i$.

### D. Zero-Success and Missingness Invariants
- If $N_{\text{rush}} == 0$: Rush SR has `value=None`, `exposure=0.0`, `missing_reason="no_rush_attempts"`.
- If $\sum_{i \in \text{Rushes}} S_i == 0$: Rush Expl has `value=None`, `exposure=0.0`, `missing_reason="no_successful_plays"`.
- If $N_{\text{pass}} == 0$: Pass SR has `value=None`, `exposure=0.0`, `missing_reason="no_pass_attempts"`.
- If $\sum_{i \in \text{Passes}} S_i == 0$: Pass Expl has `value=None`, `exposure=0.0`, `missing_reason="no_successful_plays"`.

---

## 3. Ordered Implementation Tasks

### Task 1: Code Integrity Fixes
1. In `src/cks_picks_cfb/ratings_lab/updaters.py`:
   - Retire/remove dead `_CANDIDATE_SCHEMA`.
   - In `_parse_candidate`: reject extra unexpected keys, validate that `k` and `rho` are finite `float` instances (not NaN/Inf), ensure $k > 0$ and $0 < \rho \le 1.0$.
   - In `load_candidate_configs`: if `directory` does not exist or is not a directory, raise `FileNotFoundError` (or `ValueError`) rather than silently returning `{}`.
2. In `tests/ratings_lab/test_platform.py`:
   - Replace permanent global test registrations with a pytest fixture that cleans up `_RECIPE_BUILDERS` and `_REGISTERED_AVAILABILITY_POLICIES` post-test.
   - Update `test_yaml_duplicate_rejection` to test collision against real `REGISTRY` (`carryover_only_rho_0_60_v1`).

### Task 2: CLI Plumbing for Multi-Recipe / Multi-Measurement Support
In `scripts/research/ratings_lab.py`:
- Add `--recipe` flag to `build-measurements` (defaulting to `"v5_raw_ppp_game_v1"` for backwards compatibility).
- Add `--measurement-id` flag to `replay`, `evaluate`, and `build-measurements` (defaulting to `"ppp"`).
- Remove hardcoded `MeasurementRecipe()` and hardcoded `measurement_id="ppp"` calls, passing user-specified or recipe-specified parameters.

### Task 3: Implement Deterministic 4-Factor Measurement Recipe
In `src/cks_picks_cfb/ratings_lab/measurements.py`:
- Implement `_build_4factor(corpus: Corpus, recipe: MeasurementRecipe) -> list[Observation]`:
  - Iterates through corpus games and their play-by-play events.
  - Applies garbage time and play eligibility filters.
  - Computes Success Rate and dual Explosiveness (primary yards/success, secondary margin) per team-game-role.
  - Emits normalized `Observation` objects with per-factor exposure and explicit `missing_reason` on 0-attempt or 0-success games.
- Register recipe `v6_4factor_game_v1` using `register_recipe()`.

### Task 4: Unit Testing & Invariant Verification
In `tests/ratings_lab/test_platform.py`:
- Add test for `_parse_candidate` hardening (rejecting non-finite values, extra keys).
- Add test for `load_candidate_configs` raising on missing directory.
- Add test for 4-factor measurement calculation:
  - Verifies down-and-distance success thresholds (1st/2nd/3rd/4th down).
  - Verifies goal-to-go fallback.
  - Verifies zero-success edge case emits `value=None` with `missing_reason="no_successful_plays"`.
  - Verifies dual explosiveness columns.
  - Verifies CLI `--recipe` flag dispatch.

---

## 4. Definition of Done & Quality Gates

1. All 4 code integrity fixes verified.
2. `v6_4factor_game_v1` recipe registered and operational.
3. CLI correctly parses `--recipe` and `--measurement-id`.
4. `uv run pytest tests/ratings_lab/ -q` passes with all new and existing tests green.
5. `uv run ruff check` and `uv run ruff format --check` clean.
6. `uv run mkdocs build --quiet` succeeds.
7. `git diff --check` clean.
8. Implementation session log written to `session_logs/2026-09-30/03-v6-phase1-measurement-recipe.md`.
