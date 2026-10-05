import streamlit as st

st.set_page_config(page_title="Golf Auto-Caddie Coach", page_icon="⛳", layout="wide")
st.sidebar.title("⛳ Auto-Caddie Menu")
page = st.sidebar.radio("Navigation", ["📊 Master Analytics Dashboard", "🧮 WHS & HNA Calculator", "⛳ Pre-Round Caddie"])

if page == "📊 Master Analytics Dashboard":
    st.header("📊 Master Analytics Dashboard")
    st.success("✅ Dashboard online and connected!")

elif page == "🧮 WHS & HNA Calculator":
    st.header("🧮 WHS & HNA Calculator")
    st.info("Handicap and differential tracking active.")

elif page == "⛳ Pre-Round Caddie":
    st.header("⛳ Pre-Round Caddie")
    st.warning("⚠️ Pre-Round Caddie is paused while undergoing maintenance.")
