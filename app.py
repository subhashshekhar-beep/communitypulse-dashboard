# CommunityPulse - AI Trend Detection
# Streamlit dashboard for visualizing trending Reddit posts from trending_analysis.csv

import os
import time
from typing import Tuple

import pandas as pd
import numpy as np
import streamlit as st
import altair as alt

# Optional autorefresh component (pip package: streamlit-autorefresh)
try:
    from streamlit_autorefresh import st_autorefresh
    HAS_AUTOREFRESH = True
except Exception:
    HAS_AUTOREFRESH = False


# ---------------------------
# Page config & Styling
# ---------------------------
st.set_page_config(
    page_title="CommunityPulse - AI Trend Detection",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Minimal professional theming tweaks
st.markdown(
    """
    <style>
      .small-muted { color: #6b7280; font-size: 0.9rem; }
      .metric-note { color: #6b7280; font-size: 0.8rem; margin-top: -0.5rem; }
      .dataframe td, .dataframe th { font-size: 0.9rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("CommunityPulse - AI Trend Detection")
st.caption("Real-time view of high-signal community discussions across subreddits.")


# ---------------------------
# Sidebar Controls
# ---------------------------
with st.sidebar:
    st.header("Filters & Refresh")

    # File selection / upload
    st.markdown("**Data source**")
    default_path = "trending_analysis.csv"
    file_exists = os.path.exists(default_path)

    uploaded_file = st.file_uploader(
        "Upload a trending_analysis.csv (optional)",
        type=["csv"],
        help="If not uploaded, the app will look for trending_analysis.csv in the working directory.",
    )

    # Auto-refresh settings
    refresh_enabled = st.toggle("Auto-refresh", value=True, help="Periodically reload data & refresh visuals.")
    refresh_seconds = st.number_input(
        "Refresh interval (seconds)", min_value=10, max_value=3600, value=60, step=10
    )

    st.divider()

    # Filters (populated after data load)
    min_score_default = 60
    st.markdown("**Filters**")
    min_trending_score = st.slider(
        "Minimum trending score", min_value=0, max_value=100, value=min_score_default, step=1
    )
    # Subreddit multiselect will be defined after data is loaded (depends on list)


# ---------------------------
# Data Loading (cached)
# ---------------------------
@st.cache_data(show_spinner=False)
def load_data_from_path(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    # Normalize/ensure required columns exist
    expected = {"title", "subreddit", "trending_score", "score", "num_comments"}
    missing = expected - set(df.columns)
    if missing:
        raise ValueError(f"CSV missing required columns: {missing}")
    return df

@st.cache_data(show_spinner=False)
def load_data_from_buffer(buffer) -> pd.DataFrame:
    df = pd.read_csv(buffer)
    expected = {"title", "subreddit", "trending_score", "score", "num_comments"}
    missing = expected - set(df.columns)
    if missing:
        raise ValueError(f"CSV missing required columns: {missing}")
    return df


def get_data() -> Tuple[pd.DataFrame, str]:
    """
    Returns (df, source_label)
    Prefers uploaded file. Otherwise attempts local 'trending_analysis.csv'.
    """
    if uploaded_file is not None:
        try:
            df = load_data_from_buffer(uploaded_file)
            return df, "Uploaded file"
        except Exception as e:
            st.error(f"Failed to read uploaded CSV: {e}")
            st.stop()
    else:
        if file_exists:
            try:
                df = load_data_from_path(default_path)
                return df, f"Local file: {default_path}"
            except Exception as e:
                st.error(f"Failed to read {default_path}: {e}")
                st.stop()
        else:
            st.warning("No data file found. Please upload **trending_analysis.csv**.")
            st.stop()


# ---------------------------
# Auto-refresh trigger
# ---------------------------
if refresh_enabled:
    if HAS_AUTOREFRESH:
        # This triggers a rerun every N seconds without breaking the session state.
        _ = st_autorefresh(interval=refresh_seconds * 1000, limit=None, key="auto_refresh_key")
    else:
        st.info("`streamlit-autorefresh` not installed. Auto-refresh disabled. "
                "Add it to requirements.txt to enable.")


# ---------------------------
# Load & Filter Data
# ---------------------------
df, data_source = get_data()
st.markdown(f"<span class='small-muted'>Data source: {data_source} • Rows: {len(df):,}</span>", unsafe_allow_html=True)

# Clean up/ensure types
df["trending_score"] = pd.to_numeric(df["trending_score"], errors="coerce").fillna(0.0)
df["score"] = pd.to_numeric(df["score"], errors="coerce").fillna(0)
df["num_comments"] = pd.to_numeric(df["num_comments"], errors="coerce").fillna(0)

# Populate subreddit filter in sidebar (after load)
with st.sidebar:
    all_subs = sorted(df["subreddit"].dropna().astype(str).unique().tolist())
    selected_subs = st.multiselect(
        "Subreddits", options=all_subs, default=all_subs,
        help="Filter posts to selected subreddits."
    )

# Apply filters
filtered = df[df["trending_score"] >= min_trending_score]
if selected_subs:
    filtered = filtered[filtered["subreddit"].isin(selected_subs)]

# Sort by trending score desc & slice top 20
top20 = (filtered.sort_values("trending_score", ascending=False)
                 .loc[:, ["title", "subreddit", "trending_score", "score", "num_comments"]]
                 .rename(columns={"num_comments": "comments"})
                 .head(20)
                 .reset_index(drop=True))

# ---------------------------
# KPI / Summary
# ---------------------------
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Total posts (filtered)", f"{len(filtered):,}")
with col2:
    avg_ts = np.round(filtered["trending_score"].mean(), 2) if len(filtered) else 0.0
    st.metric("Avg trending score", avg_ts)
with col3:
    st.metric("Subreddits shown", f"{len(selected_subs)}")

st.markdown("<div class='metric-note'>Metrics reflect current filters.</div>", unsafe_allow_html=True)
st.divider()

# ---------------------------
# 1) Top 20 trending posts table
# ---------------------------
st.subheader("Top 20 Trending Posts")
st.dataframe(
    top20,
    use_container_width=True,
    hide_index=True,
)

# ---------------------------
# 2) Trending score visualization (bar)
# ---------------------------
st.subheader("Trending Score (Top 20)")
if len(top20):
    # Build a shorter title for y-axis readability
    top20_plot = top20.copy()
    top20_plot["title_short"] = top20_plot["title"].str.slice(0, 80) + top20_plot["title"].apply(lambda t: "…" if len(t) > 80 else "")
    chart = (
        alt.Chart(top20_plot)
        .mark_bar()
        .encode(
            x=alt.X("trending_score:Q", title="Trending score"),
            y=alt.Y("title_short:N", sort="-x", title="Post"),
            tooltip=[
                alt.Tooltip("title:N", title="Title"),
                alt.Tooltip("subreddit:N", title="Subreddit"),
                alt.Tooltip("trending_score:Q", title="Trending score"),
                alt.Tooltip("score:Q", title="Upvotes"),
                alt.Tooltip("comments:Q", title="Comments"),
            ],
        )
        .properties(height=520)
    )
    st.altair_chart(chart, use_container_width=True)
else:
    st.info("No posts match the current filters for the bar chart.")

# ---------------------------
# 3) Subreddit breakdown (pie)
# ---------------------------
st.subheader("Subreddit Breakdown")
if len(filtered):
    sub_counts = (filtered["subreddit"].value_counts().reset_index())
    sub_counts.columns = ["subreddit", "count"]

    # Altair pie chart
    pie = (
        alt.Chart(sub_counts)
        .mark_arc(innerRadius=60)
        .encode(
            theta=alt.Theta(field="count", type="quantitative"),
            color=alt.Color(field="subreddit", type="nominal", legend=alt.Legend(title="Subreddit")),
            tooltip=[alt.Tooltip("subreddit:N"), alt.Tooltip("count:Q")]
        )
        .properties(height=420)
    )
    st.altair_chart(pie, use_container_width=True)

    # Optional: legend/table of counts
    with st.expander("View subreddit counts"):
        st.dataframe(sub_counts, hide_index=True, use_container_width=True)
else:
    st.info("No data available for pie chart with the current filters.")

st.divider()

# ---------------------------
# Footer / Help
# ---------------------------
with st.expander("How to use"):
    st.markdown(
        """
        - **Upload or provide** a `trending_analysis.csv` with columns:
          `title, subreddit, trending_score, score, num_comments` (others allowed).
        - Use the **sidebar** to set filters and auto-refresh.
        - The table shows the **Top 20** posts after filtering.
        - The bar chart visualizes their **trending scores**.
        - The pie chart shows the **subreddit distribution** for all filtered posts.
        """
    )

st.caption("© CommunityPulse • Built with Streamlit")
