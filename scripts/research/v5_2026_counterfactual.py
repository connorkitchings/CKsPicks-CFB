"""Research-only 2026 rating repair and paired forecast replay.

Inputs are local copies of certified, read-only V5 parents. The source extractor
uses Preview R2 reads only; this command writes solely to --output outside ./data.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from cks_picks_cfb.forecast.heads import _fit_one
from cks_picks_cfb.ratings_lab.adjusted_game import CutoffAdjustment
from cks_picks_cfb.ratings_lab.artifacts import canonical_json, sha256
from cks_picks_cfb.ratings_lab.contracts import Game, Observation, Rating
from cks_picks_cfb.ratings_lab.corpus import PINS, Corpus
from cks_picks_cfb.ratings_lab.replay import replay
from cks_picks_cfb.ratings_lab.updaters import V5_GAME_AT_CUTOFF

HISTORICAL_NAMES = (
    "population",
    "observations",
    "terminal",
    "outcomes",
    "v5_predictions",
    "v5_features",
)
LIVE_NAMES = (
    "schedule",
    "population",
    "live_features",
    "replay_features",
    "live_frozen_predictions",
    "live_control_predictions",
    "replay_control_predictions",
    "live_measurement_observations",
    "live_rating_priors",
)
RATING_COLUMNS = ("home_offense", "home_defense", "away_offense", "away_defense")


def _read(root: Path, name: str) -> pd.DataFrame:
    return pd.read_parquet(root / f"{name}.parquet")


def _historical_frame(root: Path, repaired_states: Path | None = None) -> pd.DataFrame:
    frame = _read(root, "v5_features")
    if repaired_states is None:
        return frame
    states = pd.read_parquet(repaired_states)
    if states.duplicated(["season", "game_id", "team", "role"]).any():
        raise ValueError("historical repaired states contain duplicate keys")
    for side in ("home", "away"):
        for role in ("offense", "defense"):
            key = f"{side}_{role}"
            part = states.loc[
                states.role.eq(role), ["season", "game_id", "team", "mean"]
            ]
            part = part.rename(columns={"team": f"{side}_team", "mean": key})
            frame = frame.drop(columns=key).merge(
                part,
                on=["season", "game_id", f"{side}_team"],
                how="left",
                validate="one_to_one",
            )
    if frame[list(RATING_COLUMNS)].isna().any().any():
        raise ValueError("historical repaired states do not cover the bridge")
    return frame


def _predict(train: pd.DataFrame, target: pd.DataFrame) -> pd.DataFrame:
    if set(train.season.astype(int)) != {
        2015,
        2016,
        2017,
        2018,
        2019,
        2021,
        2022,
        2023,
        2024,
        2025,
    }:
        raise ValueError("bridge training season boundary changed")
    if target.season.ne(2026).any() or target.duplicated(["season", "game_id"]).any():
        raise ValueError("2026 application keys are invalid")
    result = []
    for kind in ("margin", "total"):
        fitted, _ = _fit_one(train, target, target=kind, alpha=10.0, floor=0.05)
        part = target[["season", "week", "game_id", "completed_game_stage"]].copy()
        part["target"] = kind
        part["mean"] = fitted + target[f"offset_{kind}"].to_numpy(float)
        result.append(part)
    return (
        pd.concat(result, ignore_index=True)
        .sort_values(["week", "game_id", "target"])
        .reset_index(drop=True)
    )


def _swap(
    features: pd.DataFrame, schedule: pd.DataFrame, states: pd.DataFrame
) -> pd.DataFrame:
    names = schedule[["season", "game_id", "home_team", "away_team"]]
    frame = features.merge(names, on=["season", "game_id"], validate="one_to_one")
    for side in ("home", "away"):
        for role in ("offense", "defense"):
            key = f"{side}_{role}"
            part = states.loc[
                states.role.eq(role), ["season", "game_id", "team", "mean"]
            ]
            part = part.rename(columns={"team": f"{side}_team", "mean": key})
            frame = frame.drop(columns=key).merge(
                part,
                on=["season", "game_id", f"{side}_team"],
                how="left",
                validate="one_to_one",
            )
    if frame[list(RATING_COLUMNS)].isna().any().any():
        raise ValueError("2026 repaired states do not cover every forecast game")
    return frame.drop(columns=["home_team", "away_team"])


def _score(frame: pd.DataFrame) -> dict[str, float | int]:
    err = frame["actual"].to_numpy(float) - frame["mean"].to_numpy(float)
    return {
        "games": len(frame),
        "mae": float(np.mean(abs(err))),
        "rmse": float(np.sqrt(np.mean(np.square(err)))),
        "bias": float(np.mean(err)),
    }


def _paired_bootstrap(scored: pd.DataFrame) -> dict[str, object]:
    """Resample paired games within each completed week, preserving arm keys."""
    rng = np.random.default_rng(20260928)
    result = {}
    for target, rows in scored.groupby("target"):
        pivot = rows.pivot(
            index=["week", "game_id", "actual"], columns="arm", values="mean"
        ).reset_index()
        if pivot[["v5_control", "rating_only", "repaired"]].isna().any().any():
            raise ValueError("paired bootstrap has incomplete arm keys")
        controls = abs(pivot.actual.to_numpy(float) - pivot.v5_control.to_numpy(float))
        weeks = pivot.week.to_numpy(int)
        for arm in ("rating_only", "repaired"):
            candidate = abs(pivot.actual.to_numpy(float) - pivot[arm].to_numpy(float))
            gains = controls - candidate
            indices = [np.flatnonzero(weeks == week) for week in sorted(set(weeks))]
            samples = np.empty(2000)
            for iteration in range(2000):
                selected = np.concatenate(
                    [
                        rng.choice(group, size=len(group), replace=True)
                        for group in indices
                    ]
                )
                samples[iteration] = float(np.mean(gains[selected]))
            result[f"{target}:{arm}"] = {
                "v5_minus_candidate_mae": float(np.mean(gains)),
                "game_stratified_week_bootstrap_90pct": [
                    float(x) for x in np.quantile(samples, [0.05, 0.95])
                ],
                "replicates": 2000,
            }
    return result


def run(
    historical: Path, live: Path, repaired_states: Path, output: Path
) -> dict[str, object]:
    forbidden = Path(__file__).resolve().parents[2] / "data"
    if output.resolve() == forbidden or forbidden in output.resolve().parents:
        raise ValueError("research output cannot be repository ./data")
    output.mkdir(parents=True, exist_ok=True)
    schedule = _read(live, "schedule")
    population = _read(live, "population")
    replay_features = _read(live, "replay_features")
    live_features = _read(live, "live_features")
    game_ids = set(replay_features.game_id.astype(int)) | set(
        live_features.game_id.astype(int)
    )
    games_frame = schedule[schedule.game_id.isin(game_ids)].copy()
    if len(games_frame) != len(game_ids) or games_frame.duplicated("game_id").any():
        raise ValueError("2026 certified forecast schedule mismatch")
    if len(replay_features) != 215 or len(live_features) != 56:
        raise ValueError("expected 215 completed and 56 Week 5 forecast games")
    games = [
        Game(
            2026,
            int(row.week),
            int(row.game_id),
            pd.Timestamp(row.kickoff_utc).isoformat(),
            str(row.home_team),
            str(row.away_team),
        )
        for row in games_frame.itertuples(index=False)
    ]
    obs_frame = _read(live, "live_measurement_observations")
    obs_frame = obs_frame[obs_frame.measurement_id.eq("ppp")]
    if set(obs_frame.game_id.astype(int)) != set(population.game_id.astype(int)):
        raise ValueError("2026 PPP source games differ from certified population")
    observations = []
    for row in obs_frame.itertuples(index=False):
        valid = (
            row.coverage_status == "observed"
            and pd.notna(row.raw_value)
            and float(row.denominator) > 0
        )
        observations.append(
            Observation(
                2026,
                int(row.week),
                int(row.game_id),
                str(row.team),
                str(row.unit_role),
                "ppp",
                float(row.raw_value) if valid else None,
                float(row.denominator) if pd.notna(row.denominator) else 0.0,
                (pd.Timestamp(row.kickoff_utc) + pd.Timedelta(hours=6)).isoformat(),
                "live",
                missing_reason=None
                if valid
                else str(row.missing_reason or row.coverage_status),
            )
        )
    priors_frame = _read(live, "live_rating_priors")
    priors = {
        (2026, str(row.team), str(row.unit_role)): Rating(
            float(row.prior_mean), float(row.prior_variance)
        )
        for row in priors_frame.itertuples(index=False)
    }
    if len(priors) != len(priors_frame):
        raise ValueError("duplicate certified 2026 priors")
    corpus = Corpus(
        population,
        obs_frame,
        pd.DataFrame(),
        _read(historical, "terminal"),
        pd.DataFrame(),
        pd.DataFrame(),
        pd.DataFrame(),
        {
            "measurement": {
                "sha256": "c43f66206973e94b27c6cb23fcc5462aff2fc00b7c1f0eaa1a20fdeaace20a4f"
            }
        },
        {},
    )
    adjuster = CutoffAdjustment(corpus, extra_scale_seasons=(2026,))
    states = replay(
        games,
        observations,
        design=V5_GAME_AT_CUTOFF,
        measurement_id="ppp_adj_game_at_cutoff_v1",
        timing_class="live",
        fixed_priors=priors,
        cutoff_evidence=adjuster.game_evidence,
    )
    state_frame = pd.DataFrame(
        [
            {
                "season": state.season,
                "week": state.week,
                "game_id": state.game_id,
                "cutoff_utc": state.cutoff_utc,
                "team": state.team,
                "role": state.role,
                "mean": state.rating.mean,
                "variance": state.rating.variance,
                "prior_mean": state.prior.mean,
                "prior_variance": state.prior.variance,
                "usable_exposure": state.usable_exposure,
                "evidence_game_ids": json.dumps(state.evidence_game_ids),
                "explanation": canonical_json(state.explanation).decode(),
            }
            for state in states
        ]
    )
    if len(state_frame) != 4 * len(game_ids):
        raise ValueError("repaired rating states lack a game/team/role")
    state_frame.to_parquet(
        output / "repaired_2026_pregame_ratings.parquet", index=False
    )
    v5_train = _historical_frame(historical)
    repair_train = _historical_frame(historical, repaired_states)
    control_week5 = _predict(v5_train, live_features)
    frozen = _read(live, "live_frozen_predictions")
    parity = control_week5.merge(
        frozen[["season", "week", "game_id", "target", "mean"]],
        on=["season", "week", "game_id", "target"],
        suffixes=("_control", "_frozen"),
        validate="one_to_one",
    )
    if (
        len(parity) != 112
        or (parity.mean_control - parity.mean_frozen).abs().max() > 1e-9
    ):
        raise ValueError("historical control refit does not reproduce frozen Week 5")
    control_early = _predict(v5_train, replay_features)
    exported_early = _read(live, "replay_control_predictions")
    early_parity = control_early.merge(
        exported_early[["season", "week", "game_id", "target", "mean"]],
        on=["season", "week", "game_id", "target"],
        suffixes=("_control", "_exported"),
        validate="one_to_one",
    )
    if (
        len(early_parity) != 430
        or (early_parity.mean_control - early_parity.mean_exported).abs().max() > 1e-9
    ):
        raise ValueError(
            "historical control refit does not reproduce exported 2026 replay"
        )
    repaired_early_features = _swap(replay_features, games_frame, state_frame)
    repaired_week5_features = _swap(live_features, games_frame, state_frame)
    rating_only_early = _predict(v5_train, repaired_early_features)
    rating_only_week5 = _predict(v5_train, repaired_week5_features)
    repaired_early = _predict(repair_train, repaired_early_features)
    repaired_week5 = _predict(repair_train, repaired_week5_features)
    keys = ["season", "week", "game_id", "target"]
    predictions = pd.concat(
        [
            control_early.assign(arm="v5_control", evaluation="retrospective"),
            rating_only_early.assign(arm="rating_only", evaluation="retrospective"),
            repaired_early.assign(arm="repaired", evaluation="retrospective"),
            control_week5.assign(arm="v5_control", evaluation="week5_unscored"),
            rating_only_week5.assign(arm="rating_only", evaluation="week5_unscored"),
            repaired_week5.assign(arm="repaired", evaluation="week5_unscored"),
        ],
        ignore_index=True,
    )
    predictions.to_parquet(output / "paired_2026_predictions.parquet", index=False)
    outcomes = games_frame[
        ["season", "week", "game_id", "home_points", "away_points", "completed"]
    ].copy()
    outcomes["actual_margin"] = outcomes.home_points - outcomes.away_points
    outcomes["actual_total"] = outcomes.home_points + outcomes.away_points
    scored = predictions[predictions.evaluation.eq("retrospective")].merge(
        outcomes, on=["season", "week", "game_id"], validate="many_to_one"
    )
    if (
        len(scored) != 1290
        or not scored.completed.all()
        or scored[["actual_margin", "actual_total"]].isna().any().any()
    ):
        raise ValueError("completed Week 0-4 game outcomes are incomplete")
    scored["actual"] = np.where(
        scored.target.eq("margin"), scored.actual_margin, scored.actual_total
    )
    metrics = {
        arm: {target: _score(part) for target, part in group.groupby("target")}
        for arm, group in scored.groupby("arm")
    }
    weekly = {
        arm: {
            str(week): {
                target: _score(part) for target, part in week_rows.groupby("target")
            }
            for week, week_rows in group.groupby("week")
        }
        for arm, group in scored.groupby("arm")
    }
    paired = predictions.pivot(index=keys, columns="arm", values="mean").reset_index()
    paired["repair_minus_v5"] = paired.repaired - paired.v5_control
    paired["rating_only_minus_v5"] = paired.rating_only - paired.v5_control
    paired.to_parquet(output / "paired_2026_forecast_deltas.parquet", index=False)
    report = {
        "schema_version": "v5_2026_repaired_counterfactual_v1",
        "status": "research_only_no_production_change",
        "week5_control_max_abs_difference": float(
            (parity.mean_control - parity.mean_frozen).abs().max()
        ),
        "completed_control_max_abs_difference": float(
            (early_parity.mean_control - early_parity.mean_exported).abs().max()
        ),
        "rating_states": len(state_frame),
        "completed_games": 215,
        "week5_games": 56,
        "completed_metrics": metrics,
        "completed_weekly_metrics": weekly,
        "paired_game_bootstrap": _paired_bootstrap(scored),
        "forecast_delta_by_target": {
            target: {
                "mean": float(part.repair_minus_v5.mean()),
                "mean_absolute": float(part.repair_minus_v5.abs().mean()),
                "max_absolute": float(part.repair_minus_v5.abs().max()),
                "rating_only_mean_absolute": float(
                    part.rating_only_minus_v5.abs().mean()
                ),
            }
            for target, part in paired.groupby("target")
        },
        "source_sha256": {
            f"historical/{name}": sha256((historical / f"{name}.parquet").read_bytes())
            for name in HISTORICAL_NAMES
        }
        | {
            f"live/{name}": sha256((live / f"{name}.parquet").read_bytes())
            for name in LIVE_NAMES
        },
        "pinned_historical_parents": {
            name: digest for name, (_, digest) in PINS.items()
        },
        "historical_repaired_states_sha256": sha256(repaired_states.read_bytes()),
        "pinned_2026_measurement": "c43f66206973e94b27c6cb23fcc5462aff2fc00b7c1f0eaa1a20fdeaace20a4f",
        "pinned_2026_rating": "75e016e1b9876c940cdc98d70aebcc01472b9b1fd160ca6e8e1358d87208cae0",
    }
    (output / "report.json").write_bytes(canonical_json(report))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--historical-cache", type=Path, required=True)
    parser.add_argument("--live-cache", type=Path, required=True)
    parser.add_argument("--repaired-historical-states", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(
        args.historical_cache,
        args.live_cache,
        args.repaired_historical_states,
        args.output,
    )
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "week5_control_max_abs_difference",
                    "completed_metrics",
                    "forecast_delta_by_target",
                )
            },
            indent=2,
        )
    )
