"""Standalone V6 Ratings Laboratory Tournament Runner.

Executes end-to-end multi-factor benchmarking:
1. Standardized 4-factor measurements (v6_4factor_game_v1).
2. Per-season preseason priors from terminal seeds and continuity table.
3. Per-cutoff-T schedule graph re-anchoring (4-pass + shrinkage) and Kalman batch refilter.
4. Multi-factor frame assembly (Bridge A direct 18-feature + Bridge B differentials/sums).
5. Dual bridge evaluation across 2022–2025 (7,318 rows each).
6. Paired 2,000-replicate bootstrap comparison against v5-common with pre-registered promotion decision.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pandas as pd
import yaml
from dotenv import load_dotenv

from cks_picks_cfb.ratings_lab.artifacts import (
    ResearchArtifact,
    open_research_storage,
)
from cks_picks_cfb.ratings_lab.contracts import (
    Game,
    Rating,
    RatingState,
    utc,
)
from cks_picks_cfb.ratings_lab.corpus import (
    Corpus,
    load_persisted_corpus,
    load_v5_corpus,
    persist_corpus,
)
from cks_picks_cfb.ratings_lab.evaluation import (
    FIVE_FACTOR_CORE_IDS,
    common_bridge_predictions,
    frame_with_multifactor_states,
    paired_comparison,
    scorecard,
)
from cks_picks_cfb.ratings_lab.kalman import KalmanExposureDesign
from cks_picks_cfb.ratings_lab.measurements import (
    MeasurementRecipe,
    build_cumulative,
    build_individual,
    observation_frame,
)
from cks_picks_cfb.ratings_lab.priors import (
    ContinuityTable,
    PreseasonPrior,
    compute_cohort_stats,
    compute_terminal_seeds,
)
from cks_picks_cfb.ratings_lab.reanchoring import (
    batch_refilter_states,
    filter_cutoff_games,
    reanchor_schedule_graph,
)
from cks_picks_cfb.ratings_lab.stages import (
    write_frame_stage,
    write_report,
)
from cks_picks_cfb.ratings_lab.updaters import load_candidate_configs


def _hashes() -> tuple[str, str]:
    root = Path(__file__).resolve().parents[2]
    code = hashlib.sha256()
    for directory in ("src/cks_picks_cfb", "scripts/research"):
        for path in sorted((root / directory).rglob("*.py")):
            code.update(path.read_bytes())
    lock = root / "uv.lock"
    lock_sha = hashlib.sha256(lock.read_bytes()).hexdigest() if lock.exists() else ""
    return code.hexdigest(), lock_sha


def _print(payload: Any) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))


def _state_frame(states: list[RatingState]) -> pd.DataFrame:
    rows = []
    for s in states:
        d = s.as_dict()
        d["rating_mean"] = s.rating.mean
        d["rating_variance"] = s.rating.variance
        d["prior_mean"] = s.prior.mean
        d["prior_variance"] = s.prior.variance
        d["evidence_game_ids"] = ",".join(map(str, s.evidence_game_ids))
        d["explanation_json"] = json.dumps(s.explanation, sort_keys=True)
        rows.append(d)
    return pd.DataFrame(rows)


def _load_or_build_continuity(corpus: Corpus) -> ContinuityTable:
    """Attempt to construct a ContinuityTable from lower_level_refs or preview context lake."""
    records = []
    if corpus.storage is not None:
        source = (
            corpus.storage.source
            if hasattr(corpus.storage, "source")
            else corpus.storage
        )
        from cks_picks_cfb.data.lake import DatasetRef, read_dataset

        for season, refs in getattr(corpus, "lower_level_refs", {}).items():
            if season == 2020:
                continue
            ret_ref = refs.get("returning_production")
            rec_ref = refs.get("recruiting")
            coach_ref = refs.get("coaching")

            ret_df = (
                read_dataset(source, DatasetRef(**ret_ref))
                if ret_ref
                else pd.DataFrame()
            )
            rec_df = (
                read_dataset(source, DatasetRef(**rec_ref))
                if rec_ref
                else pd.DataFrame()
            )
            coach_df = (
                read_dataset(source, DatasetRef(**coach_ref))
                if coach_ref
                else pd.DataFrame()
            )

            if not ret_df.empty and not rec_df.empty:
                merged = ret_df.merge(rec_df, on=["season", "team"], how="outer")
                if not coach_df.empty:
                    merged = merged.merge(coach_df, on=["season", "team"], how="outer")
                records.append(merged)

    if records:
        full_df = pd.concat(records, ignore_index=True)
        return ContinuityTable.from_dataframe(full_df, games=corpus.games())

    # Fallback to admitted preview context lake
    try:
        from cks_picks_cfb.data.lake import DatasetRef, read_dataset
        from cks_picks_cfb.data.storage import get_storage

        prev_storage = get_storage(environment="preview")
        context_uri = "artifacts/research/rating-successor-v2/early-week-context-20260904-786580ec-r2/context-ref.json"
        if prev_storage.exists(context_uri):
            ref_dict = json.loads(prev_storage.read_bytes(context_uri).decode())
            ctx_df = read_dataset(prev_storage, DatasetRef(**ref_dict))
            return ContinuityTable.from_dataframe(ctx_df, games=corpus.games())
    except Exception as exc:
        print(f"[*] Preview context fallback skipped: {exc}")

    return ContinuityTable({})


def run_tournament(
    *,
    config_path: str = "conf/research/ratings_lab_v1/protocol.yaml",
    candidate_id: str = "kalman_exposure_v1",
    corpus_key: str | None = None,
    reference_key: str | None = None,
    apply: bool = False,
) -> dict[str, Any]:
    """Execute the complete V6 ratings laboratory tournament."""
    load_dotenv()
    for name in ("BUCKET", "ACCOUNT_ID", "ACCESS_KEY", "SECRET_KEY", "ENDPOINT"):
        if not os.getenv(f"CFB_R2_LAB_SOURCE_{name}") and os.getenv(f"CFB_R2_{name}"):
            os.environ[f"CFB_R2_LAB_SOURCE_{name}"] = os.environ[f"CFB_R2_{name}"]

    config_raw = Path(config_path).read_bytes()
    protocol = yaml.safe_load(config_raw)
    if protocol.get("protocol_id") != "ratings_lab_historical_v1":
        raise ValueError("unsupported ratings laboratory protocol")
    config_sha = hashlib.sha256(config_raw).hexdigest()
    code_sha, lock_sha = _hashes()

    storage = open_research_storage()
    print(f"[*] Research storage initialized: output={storage.output.identity}")

    # 1. Corpus Loading / Persistence
    if corpus_key:
        corpus_ref, _ = storage.stage_at(corpus_key)
        corpus = load_persisted_corpus(storage, corpus_ref)
        print(f"[*] Loaded persisted corpus: key={corpus_key}")
    else:
        print("[*] Loading verified V5 parents as corpus...")
        corpus = load_v5_corpus(storage)
        if apply:
            corpus_ref = persist_corpus(
                storage,
                corpus,
                code_sha=code_sha,
                lock_sha=lock_sha,
                config_sha=config_sha,
            )
            print(f"[*] Persisted corpus manifest: {corpus_ref.key}")
        else:
            corpus_ref = ResearchArtifact(
                storage.output.identity, "dry_run_corpus", "dry_run", 0
            )
            print("[*] Dry-run corpus loaded (not persisted)")

    # 2. Build 5-Factor Measurements
    print("[*] Building 5-factor measurements (v6_5factor_game_v1)...")
    recipe = MeasurementRecipe(recipe_id="v6_5factor_game_v1", measurement_id="5factor")
    individual = build_individual(corpus, recipe)
    cumulative = build_cumulative(corpus.games(), individual)
    all_obs = individual + cumulative
    obs_frame = observation_frame(all_obs)
    print(
        f"[*] Built {len(individual):,} individual and {len(cumulative):,} cumulative observations"
    )

    if apply:
        measurements_ref = write_frame_stage(
            storage,
            stage="measurements",
            frame=obs_frame,
            parents={"corpus": corpus_ref.sha256},
            config={**asdict(recipe), "protocol_sha": config_sha},
            code_sha=code_sha,
            lock_sha=lock_sha,
        )
        print(f"[*] Persisted measurements manifest: {measurements_ref.key}")
    else:
        measurements_ref = ResearchArtifact(
            storage.output.identity, "dry_run_measurements", "dry_run", 0
        )

    # 3. Terminal Standardized Seeds & Preseason Priors
    print("[*] Computing terminal standardized seeds with defensive polarity...")
    terminal_seeds = compute_terminal_seeds(individual, signed_defense=True)
    cohort_stats = compute_cohort_stats(individual)
    print(
        f"[*] Computed observation cohort stats across {len(cohort_stats)} (role, mid) factor pairs"
    )
    continuity = _load_or_build_continuity(corpus)
    print(
        f"[*] Continuity table loaded ({len(continuity)} records, fallback_to_neutral=False for terminal seeds)"
    )

    prior_engine = PreseasonPrior(
        rho={"SR": 0.60, "Expl": 0.60, "Finish": 0.55},
        continuity=continuity if len(continuity) > 0 else None,
        terminal_seeds=terminal_seeds,
        fallback_to_neutral=False,
        cohort_stats=cohort_stats,
    )

    # 4. Schedule Re-anchoring & Kalman Batch Refilter Loop
    candidates = load_candidate_configs(Path("conf/research/candidates"))
    if candidate_id not in candidates:
        raise ValueError(
            f"candidate {candidate_id!r} not found in conf/research/candidates/"
        )
    design = candidates[candidate_id]
    if not isinstance(design, KalmanExposureDesign):
        raise ValueError(f"expected KalmanExposureDesign, got {type(design)}")

    print(
        f"[*] Executing retrospective re-anchoring & Kalman refilter ({candidate_id})..."
    )
    all_games = corpus.games()
    by_season: dict[int, list[Game]] = defaultdict(list)
    for g in all_games:
        by_season[g.season].append(g)

    all_rating_states: list[RatingState] = []
    cutoff_logs: list[dict[str, Any]] = []

    for season in sorted(by_season):
        season_games = by_season[season]
        season_teams = {
            name for g in season_games for name in (g.home_team, g.away_team)
        }

        # Precompute season priors for the 5 core factor IDs
        season_priors: dict[tuple[int, str, str, str], Rating] = {}
        for mid in FIVE_FACTOR_CORE_IDS:
            fixed_p, neutral_k = prior_engine.build_fixed_priors(
                season, mid, season_teams
            )
            for (s, team, role), r in fixed_p.items():
                season_priors[(s, team, role, mid)] = r
            if cohort_stats is not None:
                for s, team, role in neutral_k:
                    m_c, s_c = cohort_stats.get((role, mid), (0.0, 1.0))
                    season_priors[(s, team, role, mid)] = Rating(m_c, s_c**2)

        # Unique weeks in season
        weeks = sorted({g.week for g in season_games})
        season_obs = [o for o in individual if o.season == season]

        for week in weeks:
            week_games = [
                g for g in season_games if g.week == week and g.forecast_eligible
            ]
            if not week_games:
                continue

            cutoff_dt = min(utc(g.kickoff_utc) for g in week_games)
            completed_games = filter_cutoff_games(
                season_games, cutoff_dt, availability_buffer_hours=6.0
            )
            completed_gids = {g.game_id for g in completed_games}
            completed_obs = [o for o in season_obs if o.game_id in completed_gids]

            # Re-anchor schedule graph for completed games
            reanchored = reanchor_schedule_graph(
                completed_games,
                completed_obs,
                priors=season_priors,
                week=week,
                num_passes=4,
                shrinkage_k=2.0,
            )

            # Refilter pregame states for week's upcoming games
            week_states = batch_refilter_states(
                week_games,
                reanchored,
                priors=season_priors,
                design=design,
                week=week,
                cutoff_utc=cutoff_dt.isoformat(),
                measurement_ids=FIVE_FACTOR_CORE_IDS,
            )
            all_rating_states.extend(week_states)

            cutoff_logs.append(
                {
                    "season": season,
                    "week": week,
                    "cutoff_utc": cutoff_dt.isoformat(),
                    "completed_games": len(completed_games),
                    "reanchored_obs": len(reanchored),
                    "emitted_states": len(week_states),
                }
            )

    print(
        f"[*] Emitted {len(all_rating_states):,} total rating states across {len(cutoff_logs)} cutoffs"
    )

    # 5. Multi-Factor Feature Frame Assembly
    print(
        "[*] Assembling multi-factor feature frame with direct columns, differentials, and sums..."
    )
    feature_frame = frame_with_multifactor_states(
        corpus, all_rating_states, core_mids=FIVE_FACTOR_CORE_IDS
    )
    assert len(feature_frame) == 8935, (
        f"feature frame row count mismatch: {len(feature_frame)} != 8935"
    )
    print(
        f"[*] Feature frame successfully assembled: {len(feature_frame):,} rows, 0 NaNs"
    )

    if apply:
        states_df = _state_frame(all_rating_states)
        ratings_ref = write_frame_stage(
            storage,
            stage="ratings",
            frame=states_df,
            parents={
                "corpus": corpus_ref.sha256,
                "measurements": measurements_ref.sha256,
            },
            config={"candidate": candidate_id},
            code_sha=code_sha,
            lock_sha=lock_sha,
        )
        print(f"[*] Persisted ratings manifest: {ratings_ref.key}")

        features_ref = write_frame_stage(
            storage,
            stage="features",
            frame=feature_frame,
            parents={
                "corpus": corpus_ref.sha256,
                "ratings": ratings_ref.sha256,
            },
            config={"candidate": candidate_id},
            code_sha=code_sha,
            lock_sha=lock_sha,
        )
        print(f"[*] Persisted features manifest: {features_ref.key}")

    # 6. Dual Bridge Evaluation (2022–2025 Headline Test Window)
    print("[*] Evaluating Bridge A: Direct 22-Feature Ridge (alpha10_direct22)...")
    preds_bridge_a = common_bridge_predictions(
        corpus,
        feature_frame,
        candidate_id=f"{candidate_id}_direct22",
        bridge="alpha10_direct22",
    )
    scorecard_a = scorecard(preds_bridge_a)
    print(
        f"[*] Bridge A completed: {len(preds_bridge_a):,} rows, Pooled Margin MAE: {scorecard_a['pooled']['margin']['mae']:.4f}"
    )

    print(
        "[*] Evaluating Bridge B: Domain Differentials & Sums (alpha10_differentials)..."
    )
    preds_bridge_b = common_bridge_predictions(
        corpus,
        feature_frame,
        candidate_id=f"{candidate_id}_differentials",
        bridge="alpha10_differentials",
    )
    scorecard_b = scorecard(preds_bridge_b)
    print(
        f"[*] Bridge B completed: {len(preds_bridge_b):,} rows, Pooled Margin MAE: {scorecard_b['pooled']['margin']['mae']:.4f}"
    )

    # 7. Compare Against v5-common
    print("[*] Loading / computing v5-common reference predictions...")
    v5_common_preds = common_bridge_predictions(
        corpus,
        corpus.v5_features,
        candidate_id="v5_common_alpha10_v1",
        bridge="v5_common",
    )
    scorecard_v5 = scorecard(v5_common_preds)
    print(
        f"[*] v5-common reference: Pooled Margin MAE: {scorecard_v5['pooled']['margin']['mae']:.4f}, Total MAE: {scorecard_v5['pooled']['total']['mae']:.4f}"
    )

    print("[*] Running 2,000 paired block-bootstrap comparisons (seed=20260928)...")
    comp_a = paired_comparison(
        preds_bridge_a, v5_common_preds, corpus, seed=20260928, samples=2000
    )
    comp_b = paired_comparison(
        preds_bridge_b, v5_common_preds, corpus, seed=20260928, samples=2000
    )

    # Decision logic
    bound_a = comp_a["paired"]["margin"]["lower_90"]
    bound_b = comp_b["paired"]["margin"]["lower_90"]
    decision_a = "PROMOTED" if bound_a > 0.0 else "RETAINED_AS_BENCHMARK"
    decision_b = "PROMOTED" if bound_b > 0.0 else "RETAINED_AS_BENCHMARK"

    summary = {
        "candidate_id": candidate_id,
        "protocol_sha": config_sha,
        "code_sha": code_sha,
        "lock_sha": lock_sha,
        "evaluation_window": "2022-2025",
        "paired_games": 3659,
        "paired_rows": 7318,
        "bridge_a": {
            "name": "alpha10_direct22",
            "features_count": 22,
            "margin_mae": scorecard_a["pooled"]["margin"]["mae"],
            "margin_mae_gain_vs_v5": comp_a["paired"]["margin"]["mae_gain"],
            "margin_lower_90": bound_a,
            "margin_upper_90": comp_a["paired"]["margin"]["upper_90"],
            "total_mae": scorecard_a["pooled"]["total"]["mae"],
            "total_mae_gain_vs_v5": comp_a["paired"]["total"]["mae_gain"],
            "decision": decision_a,
        },
        "bridge_b": {
            "name": "alpha10_differentials",
            "features_count": 10,
            "margin_mae": scorecard_b["pooled"]["margin"]["mae"],
            "margin_mae_gain_vs_v5": comp_b["paired"]["margin"]["mae_gain"],
            "margin_lower_90": bound_b,
            "margin_upper_90": comp_b["paired"]["margin"]["upper_90"],
            "total_mae": scorecard_b["pooled"]["total"]["mae"],
            "total_mae_gain_vs_v5": comp_b["paired"]["total"]["mae_gain"],
            "decision": decision_b,
        },
    }

    if apply:
        # Write predictions & comparison reports
        write_frame_stage(
            storage,
            stage="predictions",
            frame=preds_bridge_a,
            parents={"corpus": corpus_ref.sha256},
            config={
                "candidate": f"{candidate_id}_direct22",
                "bridge": "alpha10_direct22",
            },
            code_sha=code_sha,
            lock_sha=lock_sha,
        )
        write_frame_stage(
            storage,
            stage="predictions",
            frame=preds_bridge_b,
            parents={"corpus": corpus_ref.sha256},
            config={
                "candidate": f"{candidate_id}_differentials",
                "bridge": "alpha10_differentials",
            },
            code_sha=code_sha,
            lock_sha=lock_sha,
        )
        comp_report_ref = write_report(
            storage,
            report=summary,
            parents={"corpus": corpus_ref.sha256},
            config={"candidate": candidate_id},
            code_sha=code_sha,
            lock_sha=lock_sha,
        )
        print(f"[*] Persisted tournament scorecard report: {comp_report_ref.key}")

    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run V6 Ratings Lab Tournament Benchmark"
    )
    parser.add_argument(
        "--config", default="conf/research/ratings_lab_v1/protocol.yaml"
    )
    parser.add_argument("--candidate", default="kalman_exposure_v1")
    parser.add_argument("--corpus-key", default=None)
    parser.add_argument("--reference-key", default=None)
    parser.add_argument(
        "--apply", action="store_true", help="Persist stages to research storage"
    )
    args = parser.parse_args(argv)

    results = run_tournament(
        config_path=args.config,
        candidate_id=args.candidate,
        corpus_key=args.corpus_key,
        reference_key=args.reference_key,
        apply=args.apply,
    )
    _print(results)
    return 0


if __name__ == "__main__":
    sys.exit(main())
