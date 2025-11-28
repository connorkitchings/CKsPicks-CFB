import glob
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="CFB Model Dashboard", layout="wide")

# --- Constants ---
DATA_ROOT = Path("data/production/scored")


# --- Helper Functions ---
@st.cache_data
def load_data():
    """Load all scored bets from the production directory."""
    all_files = glob.glob(
        str(DATA_ROOT / "**" / "CFB_week*_bets_scored.csv"), recursive=True
    )
    if not all_files:
        return pd.DataFrame()

    frames = []
    for f in all_files:
        try:
            df = pd.read_csv(f)
            # Extract year from path if not in df
            path_parts = Path(f).parts
            # path is like data/production/scored/2024/CFB_weekX...
            # year is -2 index
            year = int(path_parts[-2])
            if "year" not in df.columns:
                df["year"] = year
            frames.append(df)
        except Exception as e:
            st.warning(f"Failed to read {f}: {e}")

    if not frames:
        return pd.DataFrame()

    df = pd.concat(frames, ignore_index=True)

    # Normalize columns
    col_map = {
        "Spread Prediction": "model_spread",
        "Total Prediction": "model_total",
        "home_team_spread_line": "spread_line",
        "total_line": "total_line",
        "edge_spread": "spread_edge",
        "edge_total": "total_edge",
        "Spread Bet Result": "spread_result",
        "Total Bet Result": "total_result",
        "Spread Bet": "spread_bet",
        "Total Bet": "total_bet",
    }
    df.rename(columns=col_map, inplace=True)

    # Ensure numeric
    cols_to_numeric = [
        "model_spread",
        "spread_line",
        "spread_edge",
        "model_total",
        "total_line",
        "total_edge",
    ]
    for c in cols_to_numeric:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    return df


def calculate_metrics(df, bet_type="spread"):
    """Calculate Win Rate, ROI, and Units Won."""
    if df.empty:
        return 0, 0, 0

    result_col = f"{bet_type}_result"

    # Filter to actual bets (Win/Loss)
    bets = df[df[result_col].isin(["Win", "Loss"])].copy()

    wins = len(bets[bets[result_col] == "Win"])
    losses = len(bets[bets[result_col] == "Loss"])
    total = wins + losses

    win_rate = wins / total if total > 0 else 0.0

    # ROI Calculation (assuming -110 odds => win 0.909, lose 1.0)
    # Net Units = (Wins * 0.909) - (Losses * 1.0)
    units_won = (wins * 0.90909) - (losses * 1.0)
    roi = units_won / total if total > 0 else 0.0

    return win_rate, roi, units_won


# --- Main App ---
st.title("🏈 CFB Model Performance Dashboard")

df = load_data()

if df.empty:
    st.error(
        "No data found in `data/production/scored`. Please ensure the pipeline has run."
    )
    st.stop()

# Sidebar Filters
st.sidebar.header("Filters")
selected_years = st.sidebar.multiselect(
    "Select Year(s)", sorted(df["year"].unique()), default=sorted(df["year"].unique())
)
selected_weeks = st.sidebar.multiselect(
    "Select Week(s)",
    sorted(df["Week"].unique()) if "Week" in df.columns else [],
    default=[],
)

# Apply Filters
filtered_df = df[df["year"].isin(selected_years)]
if selected_weeks:
    filtered_df = filtered_df[filtered_df["Week"].isin(selected_weeks)]

# --- Overview Tab ---
tab1, tab2, tab3, tab4 = st.tabs(
    ["Overview", "Weekly Performance", "Betting Log", "Edge Analysis"]
)

with tab1:
    st.header("Season Overview")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Spread Bets")
        swr, sroi, sunits = calculate_metrics(filtered_df, "spread")
        st.metric("Win Rate", f"{swr:.1%}")
        st.metric("ROI", f"{sroi:.1%}")
        st.metric("Units Won", f"{sunits:.2f}")

    with col2:
        st.subheader("Total Bets")
        twr, troi, tunits = calculate_metrics(filtered_df, "total")
        st.metric("Win Rate", f"{twr:.1%}")
        st.metric("ROI", f"{troi:.1%}")
        st.metric("Units Won", f"{tunits:.2f}")

with tab2:
    st.header("Weekly Performance")

    if "Week" in filtered_df.columns:
        weekly_metrics = []
        for (year, week), group in filtered_df.groupby(["year", "Week"]):
            swr, sroi, sunits = calculate_metrics(group, "spread")
            twr, troi, tunits = calculate_metrics(group, "total")
            weekly_metrics.append(
                {
                    "year": year,
                    "week": week,
                    "spread_units": sunits,
                    "total_units": tunits,
                    "total_net": sunits + tunits,
                }
            )

        metrics_df = pd.DataFrame(weekly_metrics)
        if not metrics_df.empty:
            fig = px.bar(
                metrics_df,
                x="week",
                y=["spread_units", "total_units"],
                title="Net Units by Week",
                barmode="group",
                facet_col="year" if len(selected_years) > 1 else None,
            )
            st.plotly_chart(fig, use_container_width=True)

            # Cumulative
            metrics_df = metrics_df.sort_values(["year", "week"])
            metrics_df["cumulative_units"] = metrics_df.groupby("year")[
                "total_net"
            ].cumsum()

            fig2 = px.line(
                metrics_df,
                x="week",
                y="cumulative_units",
                color="year",
                title="Cumulative Units Won over Season",
            )
            st.plotly_chart(fig2, use_container_width=True)

            # Rolling 4-Week Win Rate
            st.subheader("Rolling 4-Week Performance")

            # Need to calculate rolling win rate from raw data, not aggregated units
            # Create a complete timeline of weeks
            rolling_metrics = []
            for year in selected_years:
                year_df = filtered_df[filtered_df["year"] == year].sort_values("Week")
                weeks = sorted(year_df["Week"].unique())

                for i, week in enumerate(weeks):
                    # Get last 4 weeks (inclusive)
                    start_idx = max(0, i - 3)
                    window_weeks = weeks[start_idx : i + 1]

                    window_df = year_df[year_df["Week"].isin(window_weeks)]

                    swr, sroi, _ = calculate_metrics(window_df, "spread")
                    twr, troi, _ = calculate_metrics(window_df, "total")

                    rolling_metrics.append(
                        {
                            "year": year,
                            "week": week,
                            "rolling_spread_wr": swr,
                            "rolling_total_wr": twr,
                            "rolling_spread_roi": sroi,
                            "rolling_total_roi": troi,
                        }
                    )

            rolling_df = pd.DataFrame(rolling_metrics)
            if not rolling_df.empty:
                col1, col2 = st.columns(2)
                with col1:
                    fig3 = px.line(
                        rolling_df,
                        x="week",
                        y=["rolling_spread_wr", "rolling_total_wr"],
                        color="year",
                        facet_col="year" if len(selected_years) > 1 else None,
                        title="Rolling 4-Week Win Rate",
                        markers=True,
                    )
                    fig3.add_hline(
                        y=0.524,
                        line_dash="dash",
                        line_color="red",
                        annotation_text="Breakeven",
                    )
                    st.plotly_chart(fig3, use_container_width=True)

                with col2:
                    fig4 = px.line(
                        rolling_df,
                        x="week",
                        y=["rolling_spread_roi", "rolling_total_roi"],
                        color="year",
                        facet_col="year" if len(selected_years) > 1 else None,
                        title="Rolling 4-Week ROI",
                        markers=True,
                    )
                    fig4.add_hline(y=0.0, line_dash="dash", line_color="black")
                    st.plotly_chart(fig4, use_container_width=True)

with tab3:
    st.header("Betting Log")
    st.dataframe(filtered_df)

with tab4:
    st.header("Edge Analysis")

    edge_type = st.radio("Select Bet Type", ["Spread", "Total"])
    col = "spread_edge" if edge_type == "Spread" else "total_edge"
    res = "spread_result" if edge_type == "Spread" else "total_result"

    if col in filtered_df.columns:
        # Bin edges
        bins = [0, 3, 5, 7, 10, 20]
        labels = ["0-3", "3-5", "5-7", "7-10", "10+"]
        filtered_df["edge_bucket"] = pd.cut(filtered_df[col], bins=bins, labels=labels)

        bucket_metrics = []
        for bucket, group in filtered_df.groupby("edge_bucket"):
            wr, roi, units = calculate_metrics(group, edge_type.lower())
            count = len(group[group[res].isin(["Win", "Loss"])])
            bucket_metrics.append(
                {"bucket": bucket, "win_rate": wr, "roi": roi, "count": count}
            )

        b_df = pd.DataFrame(bucket_metrics)

        col1, col2 = st.columns(2)
        with col1:
            fig = px.bar(
                b_df,
                x="bucket",
                y="win_rate",
                title=f"{edge_type} Win Rate by Edge",
                text_auto=".1%",
            )
            fig.add_hline(
                y=0.524, line_dash="dash", line_color="red", annotation_text="Breakeven"
            )
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            fig2 = px.bar(
                b_df,
                x="bucket",
                y="roi",
                title=f"{edge_type} ROI by Edge",
                text_auto=".1%",
            )
            st.plotly_chart(fig2, use_container_width=True)
