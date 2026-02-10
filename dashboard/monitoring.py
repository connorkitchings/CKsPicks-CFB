import glob
import re
from pathlib import Path

import pandas as pd
import streamlit as st

# --- Configuration ---
st.set_page_config(
    page_title="CFB Model Monitoring Dashboard",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Functions ---


def get_repo_root():
    """Finds the repository root from the current script's location."""
    return Path(__file__).parent.parent


def natural_sort_key(s, _nsre=re.compile("([0-9]+)")):
    """Sorts strings with numbers in a natural, human-friendly order."""
    return [int(text) if text.isdigit() else text.lower() for text in _nsre.split(s)]


@st.cache_data
def load_data(year):
    """Loads all scored bet files for a given year into a single DataFrame."""
    repo_root = get_repo_root()
    data_path = repo_root / "data" / "production" / "scored" / str(year)

    if not data_path.exists():
        st.error(f"Data directory not found for year {year}: {data_path}")
        return pd.DataFrame()

    all_files = glob.glob(str(data_path / "CFB_week*_bets_scored.csv"))
    all_files.sort(key=natural_sort_key)

    if not all_files:
        st.warning(f"No scored bet files found for {year}.")
        return pd.DataFrame()

    df_list = []
    for file in all_files:
        try:
            df = pd.read_csv(file)
            week_search = re.search(r"week(\d+)", file)
            if week_search:
                df["week"] = int(week_search.group(1))
            df_list.append(df)
        except Exception as e:
            st.error(f"Error loading file {file}: {e}")

    if not df_list:
        return pd.DataFrame()

    full_df = pd.concat(df_list, ignore_index=True)
    full_df = full_df.sort_values(by="week").reset_index(drop=True)
    return full_df


def calculate_metrics(df):
    """Calculates key performance metrics from a DataFrame of bets."""
    if df.empty:
        return {"total_bets": 0, "hit_rate": 0, "roi": 0, "total_profit": 0}

    total_bets = len(df)
    correct_bets = len(df[df["correct_bet"] == 1])
    hit_rate = (correct_bets / total_bets) * 100 if total_bets > 0 else 0

    # Assuming 1 unit per bet and standard -110 juice
    df["profit"] = df.apply(
        lambda row: 0.909 if row["correct_bet"] == 1 else -1, axis=1
    )
    total_profit = df["profit"].sum()
    roi = (total_profit / total_bets) * 100 if total_bets > 0 else 0

    return {
        "total_bets": total_bets,
        "hit_rate": hit_rate,
        "roi": roi,
        "total_profit": total_profit,
    }


# --- UI ---
st.title("🏆 CFB Model V2 Monitoring Dashboard")

# --- Sidebar ---
st.sidebar.header("Configuration")
selected_year = st.sidebar.selectbox("Select Year", [2025, 2024], index=0)

# --- Data Loading ---
data = load_data(selected_year)

if data.empty:
    st.stop()

# --- Main Content ---
st.header(f"Year-to-Date Performance ({selected_year})")

# Overall Metrics
overall_metrics = calculate_metrics(data)
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Bets", f"{overall_metrics['total_bets']:,}")
col2.metric("Hit Rate", f"{overall_metrics['hit_rate']:.2f}%")
col3.metric("Total Profit", f"{overall_metrics['total_profit']:.2f} units")
col4.metric("ROI", f"{overall_metrics['roi']:.2f}%")

st.markdown("---")

# Performance by Bet Type
st.subheader("Performance by Bet Type")
spread_data = data[data["bet_type"] == "spread"]
total_data = data[data["bet_type"] == "total"]

spread_metrics = calculate_metrics(spread_data)
total_metrics = calculate_metrics(total_data)

col1, col2 = st.columns(2)
with col1:
    st.markdown("#### Spreads")
    sp_col1, sp_col2, sp_col3 = st.columns(3)
    sp_col1.metric("Bets", f"{spread_metrics['total_bets']:,}")
    sp_col2.metric("Hit Rate", f"{spread_metrics['hit_rate']:.2f}%")
    sp_col3.metric("ROI", f"{spread_metrics['roi']:.2f}%")

with col2:
    st.markdown("#### Totals")
    to_col1, to_col2, to_col3 = st.columns(3)
    to_col1.metric("Bets", f"{total_metrics['total_bets']:,}")
    to_col2.metric("Hit Rate", f"{total_metrics['hit_rate']:.2f}%")
    to_col3.metric("ROI", f"{total_metrics['roi']:.2f}%")

st.markdown("---")

# Weekly Performance Trends
st.subheader("Weekly Performance")

weekly_profit = data.groupby("week")["profit"].sum().cumsum()
weekly_roi = data.groupby("week").apply(lambda x: calculate_metrics(x)["roi"])

# Create a DataFrame for charting
chart_data = pd.DataFrame(
    {"Cumulative Profit (Units)": weekly_profit, "Weekly ROI (%)": weekly_roi}
).reset_index()

st.line_chart(chart_data.set_index("week")["Cumulative Profit (Units)"])

st.markdown("---")

# Performance by Edge
st.subheader("ROI by Edge Bucket")
data["edge_bucket"] = pd.cut(
    data["model_edge"], bins=range(0, int(data["model_edge"].max()) + 2, 1)
)

edge_performance = (
    data.groupby("edge_bucket")
    .apply(lambda x: calculate_metrics(x)["roi"])
    .reset_index()
)
edge_performance.columns = ["Edge Bucket", "ROI (%)"]

st.bar_chart(edge_performance.set_index("Edge Bucket"))

# Display Raw Data
with st.expander("Show Raw Data"):
    st.dataframe(data)
