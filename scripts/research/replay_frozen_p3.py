"""Replay the frozen P3 margin bridge on development seasons in an offline mirror."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from cks_picks_cfb.forecast.heads import FEATURES, _fit_one
from cks_picks_cfb.preseason_features import canonical_team

SEASONS = (2015, 2016, 2017, 2018, 2019, 2021, 2022, 2023, 2024, 2025)
KEYS = ["season", "game_id"]
P3_FEATURES = FEATURES + ("FCS", "E", "HW", "WH")
P4_CONFERENCES = {"Big Ten", "ACC", "SEC", "Big 12"}
REFERENCE = (
    Path(__file__).resolve().parents[2]
    / "conf/research/offseason_2027/p3_reference.json"
)


def _verified_file(root: Path, ref: dict[str, str]) -> Path:
    path = root / ref["path"]
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if digest != ref["sha256"]:
        raise ValueError(f"P3 reference checksum mismatch for {path}")
    return path


def _tier(team: str, record: dict, season: int) -> str:
    if team == "Notre Dame":
        return "P4"
    if record.get("classification") != "fbs":
        return "FCS/other"
    conference = record.get("conference")
    if conference in P4_CONFERENCES or (conference == "Pac-12" and season <= 2023):
        return "P4"
    return "G5"


def _load_frame(root: Path, seasons: tuple[int, ...]) -> pd.DataFrame:
    ref = json.loads(REFERENCE.read_text())["inputs"]
    filters = [("season", "in", list(seasons))]
    path = _verified_file(root, ref["features"])
    columns = KEYS + [
        "home_team",
        "away_team",
        "completed_game_stage",
        "actual_margin",
        "offset_margin",
        "home_host",
        "venue_unknown",
    ]
    frame = pd.read_parquet(path, columns=columns, filters=filters)
    if set(frame.season) != set(seasons):
        raise ValueError("P3 feature frame lacks a requested development season")
    postseason = json.loads(_verified_file(root, ref["postseason"]).read_text())
    postseason_keys = pd.MultiIndex.from_tuples(map(tuple, postseason), names=KEYS)
    frame = frame.loc[~pd.MultiIndex.from_frame(frame[KEYS]).isin(postseason_keys)]

    path = _verified_file(root, ref["ratings"])
    states = pd.read_parquet(
        path,
        columns=KEYS + ["candidate_id", "team", "role", "mean"],
        filters=filters,
    )
    if set(states.candidate_id) != {"v5_game_adjusted_at_cutoff_v1"}:
        raise ValueError("P3 rating states have unexpected candidate identity")

    tier_rows = []
    for season in seasons:
        records = json.loads(
            _verified_file(root, ref["teams"][str(season)]).read_text()
        )
        for record in records:
            team = canonical_team(record["school"])
            tier_rows.append((season, team, _tier(team, record, season)))
    tiers = pd.DataFrame(tier_rows, columns=["season", "team", "tier"])
    tiers = tiers.drop_duplicates(["season", "team"])

    for side in ("home", "away"):
        team = f"{side}_team"
        for role in ("offense", "defense"):
            rating = f"{side}_{role}"
            selected = states.loc[states.role.eq(role)].rename(
                columns={"team": team, "mean": rating},
            )
            frame = frame.merge(
                selected[KEYS + [team, rating]],
                on=KEYS + [team],
                how="left",
                validate="one_to_one",
            )
        tier = f"{side}_tier"
        frame = frame.merge(
            tiers.rename(columns={"team": team, "tier": tier}),
            on=["season", team],
            how="left",
            validate="many_to_one",
        )
        frame[tier] = frame[tier].fillna("FCS/other")

    if frame[list(FEATURES)].isna().any().any():
        raise ValueError("P3 frame is missing frozen bridge features")
    frame["FCS"] = (
        frame.home_tier.eq("FCS/other") | frame.away_tier.eq("FCS/other")
    ).astype(float)
    early = frame.completed_game_stage.le(3)
    home_p4 = frame.home_tier.eq("P4")
    away_p4 = frame.away_tier.eq("P4")
    frame["E"] = early.astype(float)
    frame["HW"] = (early & home_p4 & ~away_p4).astype(float)
    frame["WH"] = (early & ~home_p4 & away_p4).astype(float)
    return frame


def replay(root: Path, seasons: list[int]) -> pd.DataFrame:
    """Fit each requested season on all allowed earlier seasons."""
    if (
        not seasons
        or len(seasons) != len(set(seasons))
        or set(seasons) - set(SEASONS[1:])
    ):
        raise ValueError(
            f"replay seasons must be unique development seasons in {SEASONS[1:]}"
        )
    frame = _load_frame(
        root, tuple(season for season in SEASONS if season <= max(seasons))
    )
    predictions = []
    for season in sorted(seasons):
        train = frame.loc[frame.season.lt(season)]
        test = frame.loc[frame.season.eq(season)]
        result = test[KEYS + ["completed_game_stage", "actual_margin"]].copy()
        result["fbs_vs_fbs"] = test.FCS.eq(0)
        for arm, features in (("baseline", FEATURES), ("p3", P3_FEATURES)):
            signal, _ = _fit_one(
                train,
                test,
                target="margin",
                alpha=10.0,
                floor=1e-6,
                features=features,
            )
            result[arm] = signal + test.offset_margin.to_numpy(float)
        predictions.append(result)
    return pd.concat(predictions, ignore_index=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--research-root", type=Path, required=True, help="offline input mirror"
    )
    parser.add_argument(
        "--season", type=int, required=True, action="append", choices=SEASONS[1:]
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = replay(args.research_root, args.season)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    with args.output.open("xb") as stream:
        result.to_parquet(stream, index=False)

    early = result.loc[result.fbs_vs_fbs & result.completed_game_stage.le(3)]
    gain = (
        (early.actual_margin - early.baseline).abs()
        - (early.actual_margin - early.p3).abs()
    ).mean()
    print(
        f"{len(result)} predictions, {len(early)} early FBS-vs-FBS games, gain {gain:.6f} MAE"
    )


if __name__ == "__main__":
    main()
