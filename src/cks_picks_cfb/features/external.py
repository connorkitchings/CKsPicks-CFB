"""External feature engineering.

Functions for merging external data sources into matchup DataFrames.
Covers: SP+/FPI/SRS ratings, recruiting composite, AP/Coaches poll rankings.
"""

import logging

import pandas as pd


def _get_storage(storage=None):
    """Return provided storage or auto-detect from environment."""
    if storage is not None:
        return storage
    from cks_picks_cfb.data.storage import get_storage

    return get_storage()


def merge_external_ratings(
    matchup_df: pd.DataFrame,
    year: int,
    storage=None,
) -> pd.DataFrame:
    """Merge SP+/FPI/SRS external ratings into matchup DataFrame.

    Adds home_sp_rating, away_sp_rating, sp_rating_diff, home_fpi, away_fpi,
    fpi_diff, home_srs, away_srs, srs_diff columns.
    """
    storage = _get_storage(storage)

    try:
        records = storage.read_index("external_ratings", {"year": year})
        if not records:
            logging.warning(f"No external ratings for {year}")
            return matchup_df
        ratings_df = pd.DataFrame.from_records(records)
    except Exception as e:
        logging.warning(f"Could not load external ratings for {year}: {e}")
        return matchup_df

    if "rating_type" not in ratings_df.columns or "team" not in ratings_df.columns:
        return matchup_df

    # Build one-row-per-team table with each rating type as a column.
    # All record types have a "rating" field; FPI also has "fpi" field.
    rating_specs = [
        ("sp", "rating", "sp_rating"),
        ("fpi", "fpi", "fpi"),
        ("srs", "rating", "srs"),
    ]

    team_ratings: pd.DataFrame | None = None
    for rt, src_col, dst_col in rating_specs:
        subset = ratings_df[ratings_df["rating_type"] == rt]
        if subset.empty or src_col not in subset.columns:
            continue
        piece = (
            subset[["team", src_col]]
            .rename(columns={src_col: dst_col})
            .drop_duplicates("team")
        )
        team_ratings = (
            piece
            if team_ratings is None
            else team_ratings.merge(piece, on="team", how="outer")
        )

    if team_ratings is None or team_ratings.empty:
        return matchup_df

    rating_cols = [c for c in team_ratings.columns if c != "team"]

    # Build rename maps: one for home, one for away
    home_rename = {c: f"home_{c}" for c in rating_cols}
    home_rename["team"] = "_home_t"
    away_rename = {c: f"away_{c}" for c in rating_cols}
    away_rename["team"] = "_away_t"

    result = matchup_df.merge(
        team_ratings.rename(columns=home_rename),
        left_on="home_team",
        right_on="_home_t",
        how="left",
    ).drop(columns=["_home_t"], errors="ignore")

    result = result.merge(
        team_ratings.rename(columns=away_rename),
        left_on="away_team",
        right_on="_away_t",
        how="left",
    ).drop(columns=["_away_t"], errors="ignore")

    # Compute home - away differentials
    for col in rating_cols:
        h, a = f"home_{col}", f"away_{col}"
        if h in result.columns and a in result.columns:
            result[f"{col}_diff"] = result[h] - result[a]

    return result


def merge_recruiting_composite(
    matchup_df: pd.DataFrame,
    year: int,
    storage=None,
    n_years: int = 4,
) -> pd.DataFrame:
    """Merge rolling recruiting composite into matchup DataFrame.

    Averages 247Sports composite recruiting points over the past n_years
    recruiting classes (year-n_years+1 .. year).
    Adds home_talent_composite, away_talent_composite, talent_diff columns.
    """
    storage = _get_storage(storage)

    frames = []
    for recruit_year in range(year - n_years + 1, year + 1):
        try:
            records = storage.read_index("recruiting", {"year": recruit_year})
            if records:
                frames.append(pd.DataFrame.from_records(records))
        except Exception:
            pass

    if not frames:
        logging.warning(f"No recruiting data found for {year} ({n_years}-year window)")
        return matchup_df

    recruiting_df = pd.concat(frames, ignore_index=True)

    if "points" not in recruiting_df.columns or "team" not in recruiting_df.columns:
        return matchup_df

    composite = (
        recruiting_df.groupby("team")["points"]
        .mean()
        .reset_index()
        .rename(columns={"points": "talent_composite"})
    )

    result = matchup_df.merge(
        composite.rename(
            columns={"talent_composite": "home_talent_composite", "team": "_home_t"}
        ),
        left_on="home_team",
        right_on="_home_t",
        how="left",
    ).drop(columns=["_home_t"], errors="ignore")

    result = result.merge(
        composite.rename(
            columns={"talent_composite": "away_talent_composite", "team": "_away_t"}
        ),
        left_on="away_team",
        right_on="_away_t",
        how="left",
    ).drop(columns=["_away_t"], errors="ignore")

    result["talent_diff"] = (
        result["home_talent_composite"] - result["away_talent_composite"]
    )

    return result


def merge_rankings(
    matchup_df: pd.DataFrame,
    year: int,
    storage=None,
    polls: tuple[str, ...] = ("AP Top 25", "Coaches Poll"),
    unranked_value: int = 26,
) -> pd.DataFrame:
    """Merge AP/Coaches poll rankings into matchup DataFrame by week.

    Adds home_rank, away_rank, rank_diff, is_ranked_home, is_ranked_away.
    Unranked teams receive unranked_value (default 26).
    """
    storage = _get_storage(storage)

    try:
        records = storage.read_index("rankings", {"year": year})
        if not records:
            logging.warning(f"No rankings data for {year}")
            return matchup_df
        rankings_df = pd.DataFrame.from_records(records)
    except Exception as e:
        logging.warning(f"Could not load rankings for {year}: {e}")
        return matchup_df

    needed = {"poll", "week", "team", "rank"}
    if not needed.issubset(rankings_df.columns):
        return matchup_df

    rankings_df = rankings_df[rankings_df["poll"].isin(polls)]
    if rankings_df.empty:
        return matchup_df

    # Average rank across polls per team per week, round to nearest integer
    avg_rank = (
        rankings_df.groupby(["week", "team"])["rank"].mean().round().reset_index()
    )
    avg_rank["rank"] = avg_rank["rank"].astype(int)

    if "week" not in matchup_df.columns:
        return matchup_df

    result = matchup_df.merge(
        avg_rank.rename(columns={"rank": "home_rank", "team": "_home_t"}),
        left_on=["week", "home_team"],
        right_on=["week", "_home_t"],
        how="left",
    ).drop(columns=["_home_t"], errors="ignore")

    result = result.merge(
        avg_rank.rename(columns={"rank": "away_rank", "team": "_away_t"}),
        left_on=["week", "away_team"],
        right_on=["week", "_away_t"],
        how="left",
    ).drop(columns=["_away_t"], errors="ignore")

    result["home_rank"] = result["home_rank"].fillna(unranked_value).astype(int)
    result["away_rank"] = result["away_rank"].fillna(unranked_value).astype(int)
    result["rank_diff"] = result["home_rank"] - result["away_rank"]
    result["is_ranked_home"] = (result["home_rank"] < unranked_value).astype(int)
    result["is_ranked_away"] = (result["away_rank"] < unranked_value).astype(int)

    return result
