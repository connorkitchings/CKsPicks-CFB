"""Point-in-time preseason data, features, models, and early-season routing.

The module deliberately has no dependency on betting lines.  All inputs are
either prior-season team results or preseason provider data captured in an
immutable snapshot.  That makes a historical Week 1 row reproducible even if
the provider later revises a roster or recruiting record.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from runpy import run_path
from typing import Any, Iterable, Mapping, Sequence

import joblib
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from cks_picks_cfb.data.storage import Partition, StorageBackend

TEAM_LOGO_MAP = run_path(
    Path(__file__).resolve().parents[2] / "contracts" / "teams.py"
)["TEAM_LOGO_MAP"]

SNAPSHOT_SCHEMA_VERSION = "preseason_v1"
REQUIRED_SNAPSHOT_SOURCES = (
    "returning_production",
    "transfers",
    "recruiting",
    "coaches",
    "talent",
)

TEAM_FEATURES = (
    "prior_adj_off_epa_pp",
    "prior_adj_def_epa_pp",
    "prior_adj_off_sr",
    "prior_adj_def_sr",
    "prior_plays_per_game",
    "return_total_ppa",
    "return_passing_ppa",
    "return_rushing_ppa",
    "return_receiving_ppa",
    "return_percent_ppa",
    "return_passing_usage",
    "return_rushing_usage",
    "transfer_in_count",
    "transfer_out_count",
    "transfer_net_rating",
    "transfer_in_qb",
    "transfer_out_qb",
    "talent",
    "recruiting_4yr",
    "recruiting_current",
    "recruiting_trend",
    "coach_tenure",
    "coach_new",
)
MATCHUP_CONTEXT_FEATURES = ("neutral_site", "same_conference")
PRESEASON_FEATURES = tuple(
    [f"{side}_{feature}" for side in ("home", "away") for feature in TEAM_FEATURES]
    + [
        f"{side}_{feature}_missing"
        for side in ("home", "away")
        for feature in TEAM_FEATURES
    ]
    + list(MATCHUP_CONTEXT_FEATURES)
)
PRIOR_QUALITY_FEATURES = tuple(
    [f"{side}_{feature}" for side in ("home", "away") for feature in TEAM_FEATURES[:5]]
    + list(MATCHUP_CONTEXT_FEATURES)
)


def canonical_team(team: object) -> str | None:
    """Return the project canonical team name, preserving unknown provider names."""
    if team is None or (isinstance(team, float) and np.isnan(team)):
        return None
    value = str(team).strip()
    return TEAM_LOGO_MAP.get(value, value)


def _as_dict(value: Any) -> dict[str, Any]:
    """Convert CFBD model objects (including nested models) to plain records."""
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    if hasattr(value, "to_dict"):
        return {key: _plain(item) for key, item in value.to_dict().items()}
    raise TypeError(f"Cannot serialize snapshot record of type {type(value)!r}")


def _plain(value: Any) -> Any:
    if hasattr(value, "to_dict"):
        return _as_dict(value)
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_plain(item) for item in value]
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _snapshot_partition(year: int, as_of: str) -> Partition:
    # Do not reuse provider field names such as ``year`` or ``season`` here.
    # PyArrow hive reads otherwise see a data-column/partition-column conflict.
    return Partition({"snapshot_year": str(year), "as_of": as_of})


def write_snapshot_source(
    storage: StorageBackend,
    *,
    year: int,
    as_of: str,
    source: str,
    records: Sequence[Mapping[str, Any]],
) -> int:
    """Persist one immutable source and a queryable manifest record.

    Storage's default manifest is intentionally not edited.  A separate
    manifest entity is portable across LocalStorage, R2, and S3 and records
    the source-level row count required for promotion checks.
    """
    partition = _snapshot_partition(year, as_of)
    entity = f"raw/preseason/{source}"
    manifest_entity = f"raw/preseason_manifest/{source}"
    if storage.partition_exists(entity, partition):
        raise FileExistsError(
            f"Immutable preseason snapshot already exists: {entity}/{partition.path_suffix()}"
        )

    row_count = storage.write(entity, list(records), partition, overwrite=False)
    manifest = {
        "season": year,
        "source": source,
        "rows": row_count,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
    }
    storage.write(manifest_entity, [manifest], partition, overwrite=False)
    return row_count


def snapshot_is_complete(storage: StorageBackend, year: int, as_of: str) -> bool:
    """Return whether every required source exists and contains data."""
    partition = _snapshot_partition(year, as_of)
    for source in REQUIRED_SNAPSHOT_SOURCES:
        records = storage.read_index(
            f"raw/preseason_manifest/{source}", partition.values
        )
        if not records or int(records[0].get("rows", 0)) <= 0:
            return False
    return True


class PreseasonSnapshotIngester:
    """Fetch provider preseason sources and save them as immutable snapshots."""

    def __init__(self, year: int, as_of: str, storage: StorageBackend, cfbd_config):
        self.year = year
        self.as_of = as_of
        self.storage = storage
        self.cfbd_config = cfbd_config

    def fetch(self, source: str) -> list[dict[str, Any]]:
        """Fetch one normalized source. Recruiting includes the full four-year window."""
        import cfbd

        client = cfbd.ApiClient(self.cfbd_config)
        if source == "returning_production":
            records = cfbd.PlayersApi(client).get_returning_production(year=self.year)
        elif source == "transfers":
            records = cfbd.PlayersApi(client).get_transfer_portal(year=self.year)
        elif source == "talent":
            records = cfbd.TeamsApi(client).get_talent(year=self.year)
        elif source == "coaches":
            records = cfbd.CoachesApi(client).get_coaches(year=self.year)
        elif source == "recruiting":
            api = cfbd.RecruitingApi(client)
            records = []
            for recruit_year in range(self.year - 3, self.year + 1):
                records.extend(api.get_team_recruiting_rankings(year=recruit_year))
        else:
            raise ValueError(f"Unknown preseason source: {source}")
        return [_as_dict(record) for record in records]

    def run(self, sources: Iterable[str] = REQUIRED_SNAPSHOT_SOURCES) -> dict[str, int]:
        counts: dict[str, int] = {}
        for source in sources:
            counts[source] = write_snapshot_source(
                self.storage,
                year=self.year,
                as_of=self.as_of,
                source=source,
                records=self.fetch(source),
            )
        return counts


def _records(
    storage: StorageBackend, entity: str, filters: Mapping[str, Any]
) -> pd.DataFrame:
    records = storage.read_index(entity, filters)
    return pd.DataFrame.from_records(records) if records else pd.DataFrame()


def _numeric_column(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df:
        return pd.Series(np.nan, index=df.index, dtype=float)
    return pd.to_numeric(df[column], errors="coerce")


def _snapshot_source(
    storage: StorageBackend, year: int, as_of: str, source: str
) -> pd.DataFrame:
    return _records(
        storage, f"raw/preseason/{source}", _snapshot_partition(year, as_of).values
    )


def _prior_quality(storage: StorageBackend, year: int) -> pd.DataFrame:
    prior = _records(storage, "processed/team_week_adj", {"year": year - 1})
    columns = [
        "team",
        *[feature.removeprefix("prior_") for feature in TEAM_FEATURES[:5]],
    ]
    if prior.empty or "team" not in prior:
        return pd.DataFrame(columns=columns)
    if "iteration" in prior:
        prior = prior[prior["iteration"] == prior["iteration"].max()]
    if "week" in prior:
        prior = (
            prior.sort_values(["team", "week"]).groupby("team", as_index=False).tail(1)
        )
    result = pd.DataFrame({"team": prior["team"].map(canonical_team)})
    for target in columns[1:]:
        result[f"prior_{target}"] = _numeric_column(prior, target)
    return result.drop_duplicates("team")


def _returning_production(df: pd.DataFrame) -> pd.DataFrame:
    targets = [feature for feature in TEAM_FEATURES if feature.startswith("return_")]
    if df.empty or "team" not in df:
        return pd.DataFrame(columns=["team", *targets])
    result = pd.DataFrame({"team": df["team"].map(canonical_team)})
    mapping = {
        "return_total_ppa": "total_ppa",
        "return_passing_ppa": "total_passing_ppa",
        "return_rushing_ppa": "total_rushing_ppa",
        "return_receiving_ppa": "total_receiving_ppa",
        "return_percent_ppa": "percent_ppa",
        "return_passing_usage": "passing_usage",
        "return_rushing_usage": "rushing_usage",
    }
    for target, source in mapping.items():
        result[target] = _numeric_column(df, source)
    return result.drop_duplicates("team")


def _transfer_features(df: pd.DataFrame) -> pd.DataFrame:
    targets = [feature for feature in TEAM_FEATURES if feature.startswith("transfer_")]
    if df.empty:
        return pd.DataFrame(columns=["team", *targets])
    transfers = df.copy()
    transfers["rating"] = _numeric_column(transfers, "rating").fillna(0.0)
    transfers["position"] = transfers["position"] if "position" in transfers else ""
    transfers["position"] = transfers["position"].fillna("").astype(str).str.upper()

    def aggregate(team_column: str, prefix: str) -> pd.DataFrame:
        subset = transfers.dropna(subset=[team_column]).copy()
        subset["team"] = subset[team_column].map(canonical_team)
        grouped = subset.groupby("team", as_index=False).agg(
            **{
                f"transfer_{prefix}_count": ("team", "size"),
                f"transfer_{prefix}_rating": ("rating", "sum"),
                f"transfer_{prefix}_qb": (
                    "position",
                    lambda value: int((value == "QB").sum()),
                ),
            }
        )
        return grouped

    incoming = aggregate("destination", "in")
    outgoing = aggregate("origin", "out")
    result = incoming.merge(outgoing, on="team", how="outer").fillna(0.0)
    result["transfer_net_rating"] = (
        result["transfer_in_rating"] - result["transfer_out_rating"]
    )
    result = result.drop(columns=["transfer_in_rating", "transfer_out_rating"])
    for target in targets:
        if target not in result:
            result[target] = 0.0
    return result[["team", *targets]]


def _recruiting_features(df: pd.DataFrame, year: int) -> pd.DataFrame:
    targets = ["recruiting_4yr", "recruiting_current", "recruiting_trend"]
    if df.empty or "team" not in df:
        return pd.DataFrame(columns=["team", *targets])
    recruiting = df.copy()
    recruiting["team"] = recruiting["team"].map(canonical_team)
    recruiting["points"] = _numeric_column(recruiting, "points")
    recruiting["year"] = _numeric_column(recruiting, "year")
    window = recruiting[recruiting["year"].between(year - 3, year)]
    result = (
        window.groupby("team", as_index=False)["points"]
        .mean()
        .rename(columns={"points": "recruiting_4yr"})
    )
    current = recruiting[recruiting["year"] == year][["team", "points"]].rename(
        columns={"points": "recruiting_current"}
    )
    result = result.merge(current, on="team", how="outer")
    result["recruiting_trend"] = result["recruiting_current"] - result["recruiting_4yr"]
    return result


def _talent_features(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "team" not in df:
        return pd.DataFrame(columns=["team", "talent"])
    return pd.DataFrame(
        {
            "team": df["team"].map(canonical_team),
            "talent": _numeric_column(df, "talent"),
        }
    ).drop_duplicates("team")


def _coach_features(df: pd.DataFrame, year: int) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for coach in df.to_dict(orient="records") if not df.empty else []:
        seasons = coach.get("seasons") or []
        normalized = [
            item if isinstance(item, dict) else _as_dict(item) for item in seasons
        ]
        current = [item for item in normalized if int(item.get("year", -1)) == year]
        for season in current:
            school = canonical_team(season.get("school"))
            prior_years = sorted(
                int(item["year"])
                for item in normalized
                if canonical_team(item.get("school")) == school
                and item.get("year") is not None
            )
            tenure = 0
            expected = year
            for observed in reversed(prior_years):
                if observed != expected:
                    break
                tenure += 1
                expected -= 1
            rows.append(
                {"team": school, "coach_tenure": tenure, "coach_new": int(tenure == 1)}
            )
    if not rows:
        return pd.DataFrame(columns=["team", "coach_tenure", "coach_new"])
    return (
        pd.DataFrame(rows)
        .sort_values("coach_tenure", ascending=False)
        .drop_duplicates("team")
    )


def _schedule(
    storage: StorageBackend, year: int, include_targets: bool
) -> pd.DataFrame:
    games = _records(storage, "raw/games", {"year": year})
    if games.empty:
        return games
    games = games.rename(columns={"id": "game_id", "start_date": "start_date"}).copy()
    games["week"] = pd.to_numeric(games.get("week"), errors="coerce")
    games = games[games["week"].between(0, 3)].copy()
    for side in ("home", "away"):
        games[f"{side}_team"] = games[f"{side}_team"].map(canonical_team)
    teams = _records(storage, "raw/teams", {"year": year})
    if {"school", "classification"}.issubset(teams.columns):
        fbs_teams = set(
            teams.loc[
                teams["classification"].astype(str).str.lower() == "fbs", "school"
            ].map(canonical_team)
        )
        if fbs_teams:
            games = games[
                games["home_team"].isin(fbs_teams) & games["away_team"].isin(fbs_teams)
            ].copy()
    neutral_site = (
        games["neutral_site"]
        if "neutral_site" in games
        else pd.Series(False, index=games.index)
    )
    games["neutral_site"] = neutral_site.fillna(False).astype(int)
    home_conf = games.get("home_conference")
    away_conf = games.get("away_conference")
    games["same_conference"] = (
        (
            home_conf.notna() & away_conf.notna() & (home_conf == away_conf)
            if home_conf is not None and away_conf is not None
            else 0
        ).astype(int)
        if isinstance(home_conf, pd.Series) and isinstance(away_conf, pd.Series)
        else 0
    )
    if include_targets and {"home_points", "away_points"}.issubset(games.columns):
        games["spread_target"] = pd.to_numeric(
            games["home_points"], errors="coerce"
        ) - pd.to_numeric(games["away_points"], errors="coerce")
        games["total_target"] = pd.to_numeric(
            games["home_points"], errors="coerce"
        ) + pd.to_numeric(games["away_points"], errors="coerce")
    return games


def _merge_side(
    matchups: pd.DataFrame, team_features: pd.DataFrame, side: str
) -> pd.DataFrame:
    renamed = team_features.rename(
        columns={
            "team": f"_{side}_team",
            **{
                column: f"{side}_{column}"
                for column in team_features.columns
                if column != "team"
            },
        }
    )
    result = matchups.merge(
        renamed, left_on=f"{side}_team", right_on=f"_{side}_team", how="left"
    )
    return result.drop(columns=[f"_{side}_team"], errors="ignore")


def build_preseason_matchups(
    storage: StorageBackend,
    *,
    year: int,
    as_of: str,
    include_targets: bool,
    require_complete_snapshot: bool = True,
) -> pd.DataFrame:
    """Build Week 0-3 matchup features from one immutable preseason snapshot."""
    if require_complete_snapshot and not snapshot_is_complete(storage, year, as_of):
        raise RuntimeError(f"Preseason snapshot {year}/{as_of} is incomplete")

    tables = [
        _prior_quality(storage, year),
        _returning_production(
            _snapshot_source(storage, year, as_of, "returning_production")
        ),
        _transfer_features(_snapshot_source(storage, year, as_of, "transfers")),
        _recruiting_features(
            _snapshot_source(storage, year, as_of, "recruiting"), year
        ),
        _talent_features(_snapshot_source(storage, year, as_of, "talent")),
        _coach_features(_snapshot_source(storage, year, as_of, "coaches"), year),
    ]
    team_features: pd.DataFrame | None = None
    for table in tables:
        if table.empty:
            continue
        team_features = (
            table
            if team_features is None
            else team_features.merge(table, on="team", how="outer")
        )
    if team_features is None:
        team_features = pd.DataFrame(columns=["team", *TEAM_FEATURES])
    for feature in TEAM_FEATURES:
        if feature not in team_features:
            team_features[feature] = np.nan

    matchups = _schedule(storage, year, include_targets)
    if matchups.empty:
        return matchups
    for side in ("home", "away"):
        matchups = _merge_side(matchups, team_features[["team", *TEAM_FEATURES]], side)
        for feature in TEAM_FEATURES:
            column = f"{side}_{feature}"
            matchups[f"{column}_missing"] = matchups[column].isna().astype(int)
    for feature in PRESEASON_FEATURES:
        if feature not in matchups:
            matchups[feature] = 0 if feature in MATCHUP_CONTEXT_FEATURES else np.nan
    return matchups


def _fit_models(
    train_df: pd.DataFrame, features: Sequence[str], alpha: float
) -> dict[str, Any]:
    """Fit separately regularized spread and total models with train-only imputation."""
    bundle: dict[str, Any] = {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "features": list(features),
        "models": {},
    }
    for target in ("spread_target", "total_target"):
        rows = train_df.dropna(subset=[target])
        if rows.empty:
            raise ValueError(f"No training rows for {target}")
        model = Pipeline(
            [
                ("imputer", SimpleImputer(strategy="median", add_indicator=True)),
                ("scaler", StandardScaler()),
                ("ridge", Ridge(alpha=alpha)),
            ]
        )
        model.fit(rows[list(features)], rows[target])
        bundle["models"][target] = model
    return bundle


def fit_preseason_models(
    train_df: pd.DataFrame, *, alpha: float = 10.0
) -> dict[str, Any]:
    """Fit the separate spread and total models with the complete feature set."""
    return _fit_models(train_df, PRESEASON_FEATURES, alpha)


def save_preseason_models(bundle: Mapping[str, Any], path: Path | str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(dict(bundle), path)


def load_preseason_models(path: Path | str) -> dict[str, Any]:
    bundle = joblib.load(path)
    if bundle.get("schema_version") != SNAPSHOT_SCHEMA_VERSION:
        raise ValueError("Unsupported preseason model schema")
    return bundle


def predict_preseason(
    bundle: Mapping[str, Any], matchups: pd.DataFrame
) -> tuple[np.ndarray, np.ndarray]:
    features = list(bundle["features"])
    missing = [feature for feature in features if feature not in matchups]
    if missing:
        raise ValueError(f"Preseason matchup schema missing features: {missing}")
    x = matchups[features]
    return (
        bundle["models"]["spread_target"].predict(x),
        bundle["models"]["total_target"].predict(x),
    )


def evaluate_preseason_predictions(
    df: pd.DataFrame, spread_predictions: np.ndarray, total_predictions: np.ndarray
) -> dict[str, float]:
    """Return line-free prediction metrics for a completed validation season."""
    metrics: dict[str, float] = {}
    for target, predictions, label in (
        ("spread_target", spread_predictions, "spread"),
        ("total_target", total_predictions, "total"),
    ):
        valid = df[target].notna()
        rows = df.loc[valid].reset_index(drop=True)
        actual = rows[target].to_numpy()
        pred = np.asarray(predictions)[valid.to_numpy()]
        metrics[f"{label}_mae"] = float(mean_absolute_error(actual, pred))
        metrics[f"{label}_rmse"] = float(mean_squared_error(actual, pred) ** 0.5)
        metrics[f"{label}_calibration_bias"] = float(np.mean(pred - actual))
    return metrics


def evaluate_preseason_candidate(
    train_df: pd.DataFrame,
    holdout_df: pd.DataFrame,
    shadow_df: pd.DataFrame | None = None,
    *,
    alpha: float = 10.0,
    max_shadow_mae_regression: float = 0.25,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Apply the locked-holdout promotion gate against prior-quality models."""
    candidate = fit_preseason_models(train_df, alpha=alpha)
    baseline = _fit_models(train_df, PRIOR_QUALITY_FEATURES, alpha)

    def score(frame: pd.DataFrame, bundle: Mapping[str, Any]) -> dict[str, float]:
        spread, total = predict_preseason(bundle, frame)
        return evaluate_preseason_predictions(frame, spread, total)

    candidate_holdout = score(holdout_df, candidate)
    baseline_holdout = score(holdout_df, baseline)
    holdout_pass = all(
        candidate_holdout[f"{target}_mae"] < baseline_holdout[f"{target}_mae"]
        for target in ("spread", "total")
    )
    result: dict[str, Any] = {
        "candidate_holdout": candidate_holdout,
        "baseline_holdout": baseline_holdout,
        "holdout_pass": holdout_pass,
        "shadow_pass": None,
        "promotion_pass": False,
    }
    if shadow_df is not None:
        candidate_shadow = score(shadow_df, candidate)
        baseline_shadow = score(shadow_df, baseline)
        shadow_pass = all(
            candidate_shadow[f"{target}_mae"]
            <= baseline_shadow[f"{target}_mae"] + max_shadow_mae_regression
            for target in ("spread", "total")
        )
        result.update(
            {
                "candidate_shadow": candidate_shadow,
                "baseline_shadow": baseline_shadow,
                "shadow_pass": shadow_pass,
            }
        )
    result["promotion_pass"] = bool(result["holdout_pass"]) and (
        result["shadow_pass"] is not False
    )
    candidate["validation"] = result
    return candidate, result


def select_blend_weights(
    validation_df: pd.DataFrame,
    *,
    grid: Sequence[float] = tuple(np.linspace(0.0, 1.0, 21)),
) -> dict[int, float]:
    """Select frozen Week 2-3 weights from precomputed, training-only rows."""
    required = {
        "home_current_season_games",
        "away_current_season_games",
        "spread_target",
        "total_target",
        "preseason_spread",
        "recency_spread",
        "preseason_total",
        "recency_total",
    }
    missing = sorted(required - set(validation_df.columns))
    if missing:
        raise ValueError(f"Blend validation is missing columns: {missing}")
    counts = (
        pd.concat(
            [
                pd.to_numeric(
                    validation_df["home_current_season_games"], errors="coerce"
                ),
                pd.to_numeric(
                    validation_df["away_current_season_games"], errors="coerce"
                ),
            ],
            axis=1,
        )
        .min(axis=1)
        .fillna(0)
        .astype(int)
    )
    weights: dict[int, float] = {}
    for games in (1, 2):
        rows = validation_df[counts == games]
        if rows.empty:
            raise ValueError(
                f"Blend validation has no rows with {games} completed games"
            )
        best_weight = min(
            grid,
            key=lambda weight: (
                mean_absolute_error(
                    rows["spread_target"],
                    weight * rows["preseason_spread"]
                    + (1.0 - weight) * rows["recency_spread"],
                )
                + mean_absolute_error(
                    rows["total_target"],
                    weight * rows["preseason_total"]
                    + (1.0 - weight) * rows["recency_total"],
                )
            ),
        )
        weights[games] = float(best_weight)
    return weights


def preseason_blend_weight(
    min_current_games: int, weights: Mapping[int, float]
) -> float:
    """Use preseason alone at zero games and recency alone after three games."""
    if min_current_games <= 0:
        return 1.0
    if min_current_games >= 3:
        return 0.0
    return float(weights.get(min_current_games, 0.0))


def blend_early_season_predictions(
    preseason_predictions: np.ndarray,
    recency_predictions: np.ndarray,
    home_games: Sequence[Any],
    away_games: Sequence[Any],
    weights: Mapping[int, float],
) -> np.ndarray:
    """Blend two prediction arrays using the less-experienced team as the gate."""
    result = np.asarray(recency_predictions, dtype=float).copy()
    for index, (home, away) in enumerate(zip(home_games, away_games, strict=True)):
        home_count = pd.to_numeric(home, errors="coerce")
        away_count = pd.to_numeric(away, errors="coerce")
        home_count = 0 if pd.isna(home_count) else int(home_count)
        away_count = 0 if pd.isna(away_count) else int(away_count)
        min_games = min(home_count, away_count)
        weight = preseason_blend_weight(min_games, weights)
        result[index] = (
            weight * preseason_predictions[index] + (1.0 - weight) * result[index]
        )
    return result
