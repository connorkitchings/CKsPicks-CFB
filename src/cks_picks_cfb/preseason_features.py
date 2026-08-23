"""Immutable preseason snapshots and provider-neutral team feature builders."""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from runpy import run_path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd

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
OPTIONAL_V4_SNAPSHOT_SOURCES = ("talent",)
V4_REQUIRED_SNAPSHOT_SOURCES = tuple(
    source
    for source in REQUIRED_SNAPSHOT_SOURCES
    if source not in OPTIONAL_V4_SNAPSHOT_SOURCES
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
    return Partition({"snapshot_year": str(year), "as_of": as_of})


def write_snapshot_source(
    storage: StorageBackend,
    *,
    year: int,
    as_of: str,
    source: str,
    records: Sequence[Mapping[str, Any]],
) -> int:
    """Persist an immutable source plus its queryable row-count manifest."""
    partition = _snapshot_partition(year, as_of)
    entity = f"raw/preseason/{source}"
    manifest_entity = f"raw/preseason_manifest/{source}"
    if storage.partition_exists(entity, partition):
        raise FileExistsError(
            f"Immutable preseason snapshot already exists: {entity}/{partition.path_suffix()}"
        )
    row_count = storage.write(entity, list(records), partition, overwrite=False)
    storage.write(
        manifest_entity,
        [
            {
                "season": year,
                "source": source,
                "rows": row_count,
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "schema_version": SNAPSHOT_SCHEMA_VERSION,
            }
        ],
        partition,
        overwrite=False,
    )
    return row_count


def snapshot_is_complete(storage: StorageBackend, year: int, as_of: str) -> bool:
    partition = _snapshot_partition(year, as_of)
    for source in REQUIRED_SNAPSHOT_SOURCES:
        records = storage.read_index(
            f"raw/preseason_manifest/{source}", partition.values
        )
        if not records or int(records[0].get("rows", 0)) <= 0:
            return False
    return True


def snapshot_sources_available(
    storage: StorageBackend, year: int, as_of: str
) -> frozenset[str]:
    partition = _snapshot_partition(year, as_of)
    return frozenset(
        source
        for source in REQUIRED_SNAPSHOT_SOURCES
        if (
            records := storage.read_index(
                f"raw/preseason_manifest/{source}", partition.values
            )
        )
        and int(records[0].get("rows", 0)) > 0
    )


def v4_snapshot_is_usable(storage: StorageBackend, year: int, as_of: str) -> bool:
    return set(V4_REQUIRED_SNAPSHOT_SOURCES) <= snapshot_sources_available(
        storage, year, as_of
    )


def v4_preseason_feature_variants(matchups: pd.DataFrame) -> dict[str, tuple[str, ...]]:
    families = {
        "prior_quality": PRIOR_QUALITY_FEATURES,
        "returning_and_transfers": tuple(
            feature
            for feature in PRESEASON_FEATURES
            if any(token in feature for token in ("_return_", "_transfer_"))
        ),
        "recruiting_and_coaches": tuple(
            feature
            for feature in PRESEASON_FEATURES
            if any(token in feature for token in ("_recruiting_", "_coach_"))
        ),
        "talent": tuple(
            feature for feature in PRESEASON_FEATURES if "_talent" in feature
        ),
    }
    result: dict[str, tuple[str, ...]] = {}
    selected: list[str] = []
    for name, features in families.items():
        if not features or not set(features).issubset(matchups.columns):
            continue
        values = matchups.loc[:, list(features)].apply(pd.to_numeric, errors="coerce")
        if (
            values.isna().any().any()
            or not np.isfinite(values.to_numpy(dtype=float)).all()
        ):
            continue
        selected.extend(features)
        result[name] = tuple(selected)
    return result


class PreseasonSnapshotIngester:
    """Fetch provider preseason sources and save immutable snapshots."""

    def __init__(self, year: int, as_of: str, storage: StorageBackend, cfbd_config):
        self.year = year
        self.as_of = as_of
        self.storage = storage
        self.cfbd_config = cfbd_config

    def fetch(self, source: str) -> list[dict[str, Any]]:
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
        return {
            source: write_snapshot_source(
                self.storage,
                year=self.year,
                as_of=self.as_of,
                source=source,
                records=self.fetch(source),
            )
            for source in sources
        }


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
    if year == 2020:
        raise ValueError("2020 is excluded from preseason feature construction")
    prior_year = 2019 if year == 2021 else year - 1
    if prior_year == 2020:
        raise ValueError("2020 cannot be used as prior-season feature lineage")
    prior = _records(storage, "processed/team_week_adj", {"year": prior_year})
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
    for target, source in {
        "return_total_ppa": "total_ppa",
        "return_passing_ppa": "total_passing_ppa",
        "return_rushing_ppa": "total_rushing_ppa",
        "return_receiving_ppa": "total_receiving_ppa",
        "return_percent_ppa": "percent_ppa",
        "return_passing_usage": "passing_usage",
        "return_rushing_usage": "rushing_usage",
    }.items():
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
        return subset.groupby("team", as_index=False).agg(
            **{
                f"transfer_{prefix}_count": ("team", "size"),
                f"transfer_{prefix}_rating": ("rating", "sum"),
                f"transfer_{prefix}_qb": (
                    "position",
                    lambda value: int((value == "QB").sum()),
                ),
            }
        )

    result = (
        aggregate("destination", "in")
        .merge(aggregate("origin", "out"), on="team", how="outer")
        .fillna(0.0)
    )
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
    result = (
        recruiting[recruiting["year"].between(year - 3, year)]
        .groupby("team", as_index=False)["points"]
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
        normalized = [
            item if isinstance(item, dict) else _as_dict(item)
            for item in (coach.get("seasons") or [])
        ]
        for season in (
            item for item in normalized if int(item.get("year", -1)) == year
        ):
            school = canonical_team(season.get("school"))
            prior_years = sorted(
                int(item["year"])
                for item in normalized
                if canonical_team(item.get("school")) == school
                and item.get("year") is not None
            )
            tenure, expected = 0, year
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
