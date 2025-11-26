from pathlib import Path

import pandas as pd


def analyze_best_bets(year=2025, start_week=2, end_week=14):
    """
    Analyze the performance of the single 'Best Bet' (highest edge) per week.
    """
    scored_dir = Path(f"artifacts/reports/{year}/scored")

    wins = 0
    losses = 0
    pushes = 0

    print(f"Analyzing Best Bets for {year} Weeks {start_week}-{end_week - 1}...")

    for week in range(start_week, end_week):
        file_path = scored_dir / f"CFB_week{week}_bets_scored.csv"
        if not file_path.exists():
            print(f"Week {week}: No scored file found.")
            continue

        df = pd.read_csv(file_path)
        if df.empty:
            continue
        candidates = []

        # Normalize columns
        df = df.rename(
            columns={"Spread Edge": "edge_spread", "Total Edge": "edge_total"}
        )

        # Spread Candidates (Threshold 0.0)
        if "edge_spread" in df.columns:
            # Ensure numeric
            cols = [
                "Spread Prediction",
                "home_team_spread_line",
                "home_points",
                "away_points",
            ]
            for c in cols:
                if c in df.columns:
                    df[c] = pd.to_numeric(df[c], errors="coerce")

            spread_cands = df[df["edge_spread"] >= 0.0].copy()
            for _, row in spread_cands.iterrows():
                # Calculate result on the fly
                margin = row["home_points"] - row["away_points"]
                cover_margin = margin + row["home_team_spread_line"]

                # Determine bet side from prediction vs line
                # If Pred > -Line, we like Home.
                # But edge is abs(Pred - (-Line)).
                # Let's assume standard logic:
                # If Pred > -Line, Bet Home.
                bet_home = row["Spread Prediction"] > -row["home_team_spread_line"]

                if bet_home:
                    if cover_margin > 0:
                        result = "Win"
                    elif cover_margin < 0:
                        result = "Loss"
                    else:
                        result = "Push"
                else:  # Bet Away
                    if cover_margin < 0:
                        result = "Win"
                    elif cover_margin > 0:
                        result = "Loss"
                    else:
                        result = "Push"

                candidates.append(
                    {
                        "type": "Spread",
                        "edge": row["edge_spread"],
                        "result": result,
                        "game": f"{row.get('home_team', row.get('Home Team'))} vs {row.get('away_team', row.get('Away Team'))}",
                    }
                )

        # Total Candidates (Threshold 5.0)
        if "edge_total" in df.columns:
            # Ensure numeric
            cols_t = ["Total Prediction", "total_line", "home_points", "away_points"]
            for c in cols_t:
                if c in df.columns:
                    df[c] = pd.to_numeric(df[c], errors="coerce")

            total_cands = df[df["edge_total"] >= 5.0].copy()
            for _, row in total_cands.iterrows():
                # Calculate result on the fly
                total_score = row["home_points"] + row["away_points"]

                # Bet Over if Pred > Line
                bet_over = row["Total Prediction"] > row["total_line"]

                if bet_over:
                    if total_score > row["total_line"]:
                        result = "Win"
                    elif total_score < row["total_line"]:
                        result = "Loss"
                    else:
                        result = "Push"
                else:  # Bet Under
                    if total_score < row["total_line"]:
                        result = "Win"
                    elif total_score > row["total_line"]:
                        result = "Loss"
                    else:
                        result = "Push"

                candidates.append(
                    {
                        "type": "Total",
                        "edge": row["edge_total"],
                        "result": result,
                        "game": f"{row.get('home_team', row.get('Home Team'))} vs {row.get('away_team', row.get('Away Team'))}",
                    }
                )
        else:
            pass  # Removed print statement
        if not candidates:
            print(f"Week {week}: No bets found.")
            continue

        # Pick Best Bet (Max Edge)
        best_bet = max(candidates, key=lambda x: x["edge"])

        result = best_bet["result"]
        print(
            f"Week {week}: {best_bet['type']} - {best_bet['game']} (Edge {best_bet['edge']:.2f}) -> {result}"
        )

        if result == "Win":
            wins += 1
        elif result == "Loss":
            losses += 1
        elif result == "Push":
            pushes += 1

    total = wins + losses
    win_rate = wins / total if total > 0 else 0.0

    record_str = f"{wins}-{losses}-{pushes}"
    percentage_str = f"{win_rate:.1%}"

    print(f"\nOverall Best Bet Record: {record_str} ({percentage_str})")
    return record_str, percentage_str


if __name__ == "__main__":
    analyze_best_bets()
