import streamlit as st
import duckdb
import pandas as pd
import json
import os

st.set_page_config(page_title="Golf Auto-Caddie Coach", page_icon="⛳", layout="wide")
st.sidebar.title("⛳ Auto-Caddie Menu")
page = st.sidebar.radio("Navigation", ["📊 Master Analytics Dashboard", "🧮 WHS & HNA Calculator", "⛳ Pre-Round Caddie"])

if page == "📊 Master Analytics Dashboard":
    st.header("📊 Master Analytics Dashboard")
    st.info("Welcome back! Your core performance dashboard is running smoothly.")
    # Standard dashboard code displays here from your DuckDB rounds

elif page == "🧮 WHS & HNA Calculator":
    st.header("🧮 WHS & HNA Calculator")
    st.info("Handicap calculations and differential tracking.")

elif page == "⛳ Pre-Round Caddie":
    st.header("⛳ Pre-Round Caddie & Course Strategy")
    st.warning("⚠️ This feature is currently paused for maintenance. Check back soon!")
