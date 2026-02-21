import pandas as pd


def add_internal_power_ratings(df: pd.DataFrame) -> pd.DataFrame:
    """
    Constructs Option 2: Internal SP+ / Power Ratings.

    Generates point-in-time valid expected margin scalars purely from
    opponent-adjusted efficiency (EPA/Play) and the team's rolling pace
    (Plays Per Game).

    This ensures we construct an accurate, self-contained SP+ equivalent
    without leaking data from future weeks or relying on external API scrapes.
    """
    # Defensive programming: ensure our required base EWMA columns exist
    if "adj_off_epa_pp" not in df.columns or "adj_def_epa_pp" not in df.columns:
        return df

    # We use actual EWMA plays_per_game if available to scale the expected points accurately per team.
    # If a team plays super fast, their expected offensive points should scale dynamically.
    if "plays_per_game" in df.columns:
        pace = df["plays_per_game"].fillna(70.0)  # CFB average is ~70
    else:
        pace = 70.0

    # Offensive Rating: Represents expected points scored above an average defense in an average pace game.
    # Note: adj_off_epa_pp represents EPA per play relative to an average opponent.
    df["internal_off_rtg"] = df["adj_off_epa_pp"] * pace

    # Defensive Rating: Represents expected points allowed below an average offense.
    # Note: lower EPA is better for a defense, so a lower internal_def_rtg is superior.
    df["internal_def_rtg"] = df["adj_def_epa_pp"] * pace

    # Global Power Rating: Overall expected margin per game against an average team.
    df["internal_power_rtg"] = df["internal_off_rtg"] - df["internal_def_rtg"]

    return df
