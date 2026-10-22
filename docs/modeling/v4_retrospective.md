# V4 retrospective and recovery reference

> V4 “Trench Warfare” is a historical benchmark. V5 Blitzkrieg is the operational model. The V4 training and serving code was removed from the repository in the 2026-10-22 consolidation (commit `4c8b9a39`); this page preserves V4's method and evidence, and the recovery commit below restores the code if ever needed.

## Method and chronology

V4 combined early-season prior models with the established opponent-adjusted performance model. A matchup routes by its least-experienced team: `game_1` through `game_4` cover teams with 0–3 completed games, and `established` requires both teams to have completed at least four. Spread and total have independent selections, making ten bundle routes. Team exposure remains independent across uneven schedules and byes.

The sealed chronology used labeled years 2021–2025: expanding selection folds trained on 2021 for 2022, 2021–2022 for 2023, and 2021–2023 for 2024. One locked 2025 check trained on 2021–2024 after freezing the selection design. The unchanged 2026 production refit then used 2021–2025. The 2021 prior could use 2019; 2020 was excluded throughout. This V4 window differs from V5's expanded development years. See the [V4 modeling contract](../plans/2026-08-17/early-season-v4-modeling.md).

Selection minimized out-of-fold MAE with RMSE, bias, sample, season-stability and paired-bootstrap gates. Candidates included explicit baselines, direct Ridge/CatBoost, points-derived Ridge/CatBoost and frozen blends. Failed challengers retained their baseline; Game 4 challengers were compared with the established model by target. Historical bookmaker lines did not select features, routes or refits.

## Features and launch bundle

Strict references admitted prior performance and current-season empirical-Bayes shrinkage. Additive recruiting, coaches, roster, returning-production, ranking and talent families needed complete source-specific pre-kickoff evidence. They did not meet that requirement, so launch used `prior_core` only (`prior_only_fallback`). Later-backfilled preseason context remained a separate reconstructed, research-only reference.

Prior-core inputs included home/away prior offensive and defensive EPA per play and success rate, prior-season gap, neutral-site and conference-game context. The established `matchup_v1` family used home/away opponent-adjusted offensive/defensive EPA, success rate and rush/pass yards per play with recency alpha 0.3. Exact per-route features are authoritative in the immutable bundle, rather than inferred from a generic feature-family label. Bookmaker-derived features were prohibited.

The launch bundle was `week0-2026-v4-strict-20260818-r2`, manifest SHA-256 `72429375bfa8c434c7d6fcb455bb9e22333af8c929c0cc3e832f0b80787bf25c`. The historical config was `conf/weekly_bets/v4_2026.yaml`, using the durable `model_bundle_v3` interface. That config also retained V2 fallback settings; V4's feature-schema-v5 diagnostic is unrelated to the later V5 model.

## Results and 2025 holdout limits

The [launch execution record](../plans/2026-08-18/week0-launch-execution.md), Amendment 3, reports four of eight early-season challenger routes beating baseline on 2022–2024 OOF selection. Spread `game_1` direct CatBoost improved MAE by 1.43; total `game_2`–`game_4` blends improved MAE by about 0.5–1.5. All eight passed locked-2025 anti-regression; spread `game_1` regressed by 0.61 MAE within tolerance. Ten deployed routes include the two established routes, so eight evaluated challengers is not a coverage gap.

A research-only 2025 betting simulation on quarantined legacy lines reported +17.9 units and +3.1% ROI, +5.9 units over baseline. Those lines lacked authentic historical quote chronology; these are retrospective diagnostics, not point-in-time betting validation or a promotion gate.

The production refit trained through 2025 and cannot evaluate 2025 out of sample. The [2025 operational replay](../plans/2026-09-09/2025-v4-operational-replay.md) instead used `v4-locked-test-replay-20260909b`, trained only on 2021–2024, manifest SHA-256 `f1bb1f0a6d48001230ae6fc55034994c9777009427753c4451f67f33edbeade4`. Certified historical predictions covered 761 games; the replay included Army–Navy for 762 games over Weeks 1–16. Comprehensive frozen-line grading reported spread 380–366–16 and total 398–359–5. Weeks 15–16 quote capture times were reconstructed from Bronze manifest write time, so this replay also does not establish authentic point-in-time market execution. It must not be compared directly with V5's different 934-game 2025 evaluation as proof either model is superior.

## Verified recovery commit

Commit `2807e0871c53a659943c5c23e5def888e0be5fbc` is the verified recovery point containing the V4 operational code and configuration before it was removed. It is the Phase 1 safeguards commit, verified locally with `git cat-file -e 2807e0871c53a659943c5c23e5def888e0be5fbc:src/cks_picks_cfb/train.py`; V4 model configs and training policy were also inspected at that tree. It is a known recoverable commit, not a claim that no later commit contains V4. Recover files from this commit in an isolated worktree if needed; recovery is not authorization to operate or promote V4. Immutable bundle checksums and the historical contracts above preserve artifact identity independently of code removal.

## Historical training windows and routes

These rules describe V4 only; they are not the V5 design.

- Selection used expanding temporal folds validated in 2022-2024; the locked test trained on 2021-2024 and evaluated 2025 once; the production refit kept the design unchanged on 2021-2025 for 2026.
- V4 retained its sealed 2021-2025 lineage. V5 and successor research use 2015-2019 and 2021-2025; 2020 is skipped entirely in every boundary.
- Completed-game routes were `game_1`, `game_2`, `game_3`, `game_4` and `established` (four or more completed games); `established` was the main route.

## Early-season regime contract (folded in from the retired regime page)

- A matchup used the route of its least-experienced team, while each team kept its own completed-game count and shrinkage weight. Spread and total were selected independently.
- Safeguards: all feature evidence reproducible before kickoff; market prices never entered features or route selection; immutable artifact lineage, temporal validation, fail-closed publication and frozen-run rollback.
- V4's hard route switches solved sparse early evidence safely but left team quality implicit in features, priors and shrinkage. The successor direction (now V5) keeps those safeguards while letting credibility change smoothly through the season: preseason priors dominate before evidence exists, early performance enters with strong shrinkage, opponent-adjusted performance gains weight as exposure grows, and uncertainty contracts only as credible evidence accumulates. Schedule strength is adjusted once, at the measurement layer; see the [rating-system requirements](rating_system_requirements.md).
- Offseason-context families (returning production, transfers, recruiting, coaching, talent) could inform research only through an immutable admission report: football-only, complete for the team-season population, canonically mapped, with effective/retrieved provenance. Families lacking pre-kickoff evidence were `reconstructed` and could not select a bundle, run locked validation, refit or publish. The original page is preserved at `docs/archive/modeling/early_season_regimes.md`.
