import streamlit as st
import duckdb
import pandas as pd

st.set_page_config(page_title="Golf Auto-Caddie Coach", page_icon="⛳", layout="centered")

@st.cache_resource
def get_db():
    return duckdb.connect("golf.duckdb", read_only=False)

conn = get_db()

st.title("⛳ Auto-Caddie Coach")

tab1, tab2 = st.tabs(["📊 Stats & Analytics", "🧮 HNA Handicap Calculator"])

# ==========================================
# TAB 1: ALL DASHBOARD DATA & TABLES
# ==========================================
with tab1:
    st.header("Player Analytics & History")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("WHS Handicap Index", "8.3", delta="Single Digit")
    with col2:
        st.metric("Recent 20 Avg Score", "84.0")
    with col3:
        st.metric("18-Hole Rounds Logged", "143")

    st.markdown("---")
    
    try:
        tables = [t[0] for t in conn.execute("SHOW TABLES").fetchall()]
        if tables:
            selected_table = st.selectbox(
                "📁 View Data Table", 
                tables, 
                index=tables.index('scorecards') if 'scorecards' in tables else 0
            )
            df = conn.execute(f"SELECT * FROM \"{selected_table}\"").df()
            st.subheader(f"Table: {selected_table} ({len(df)} rows)")
            st.dataframe(df, use_container_width=True)
    except Exception as e:
        st.error(f"Error loading database: {e}")

# ==========================================
# TAB 2: HNA HANDICAP CALCULATOR
# ==========================================
with tab2:
    st.header("HNA Course Handicap Calculator")
    
    handicap_index = st.number_input(
        "Your Current Handicap Index", 
        min_value=-10.0, 
        max_value=54.0, 
        value=8.3, 
        step=0.1
    )

    st.markdown("---")
    st.subheader("Course Details")

    COURSES = {
        "Custom / Standard Tee (CR: 72.0 | SR: 113)": {"cr": 72.0, "sr": 113, "par": 72},
        "Parkview Golf Club": {"cr": 71.8, "sr": 128, "par": 72},
        "The Wanderers Golf Club": {"cr": 72.2, "sr": 131, "par": 71},
        "Vaal de Grace Golf Estate": {"cr": 72.8, "sr": 133, "par": 72},
        "Glendower Golf Club": {"cr": 73.5, "sr": 135, "par": 72},
        "Huddle Park Golf Club (Blue)": {"cr": 70.8, "sr": 122, "par": 72},
        "Blue Valley Golf & Country Estate": {"cr": 73.0, "sr": 132, "par": 72},
        "Randpark Golf Club (Firethorn)": {"cr": 73.1, "sr": 133, "par": 72},
        "Steyn City Golf Course (Championship)": {"cr": 74.5, "sr": 142, "par": 72},
        "Steyn City Golf Course (Club)": {"cr": 72.1, "sr": 135, "par": 72},
        "Royal Johannesburg (East Course)": {"cr": 73.8, "sr": 136, "par": 72},
        "Royal Johannesburg (West Course)": {"cr": 71.5, "sr": 128, "par": 72},
        "Durban Country Club": {"cr": 73.2, "sr": 134, "par": 72},
        "Pearl Valley Golf Estate": {"cr": 74.1, "sr": 138, "par": 72},
        "Blair Atholl Golf Estate": {"cr": 76.2, "sr": 148, "par": 72},
        "Leopard Creek CC": {"cr": 74.8, "sr": 140, "par": 72},
        "Houghton Golf Club": {"cr": 72.8, "sr": 132, "par": 72},
        "Bryanston Country Club": {"cr": 71.9, "sr": 129, "par": 72},
        "CCJ - Woodmead": {"cr": 72.5, "sr": 130, "par": 72},
    }

    selected_course = st.selectbox("Select Course Preset", list(COURSES.keys()))

    default_cr = COURSES[selected_course]["cr"]
    default_sr = COURSES[selected_course]["sr"]
    default_par = COURSES[selected_course]["par"]

    col1, col2, col3 = st.columns(3)
    with col1:
        course_rating = st.number_input("Course Rating (CR)", min_value=50.0, max_value=85.0, value=float(default_cr), step=0.1)
    with col2:
        slope_rating = st.number_input("Slope Rating (SR)", min_value=55, max_value=155, value=int(default_sr), step=1)
    with col3:
        par_rating = st.number_input("Par", min_value=60, max_value=75, value=int(default_par), step=1)

    course_handicap_raw = handicap_index * (slope_rating / 113.0) + (course_rating - par_rating)
    course_handicap = round(course_handicap_raw)

    st.markdown("---")
    st.metric(label="Target Playing Handicap", value=f"{course_handicap} Strokes", delta=f"Exact: {course_handicap_raw:.2f}")

    if course_handicap > 0:
        st.info(f"💡 You receive **1 stroke** on Stroke Index 1 through {min(course_handicap, 18)}.")
        if course_handicap > 18:
            st.info(f"💡 You receive **2 strokes** on Stroke Index 1 through {course_handicap - 18}.")
    elif course_handicap == 0:
        st.info("💡 Playing off scratch (0 strokes).")
    else:
        st.info(f"💡 Plus handicap: You give back {abs(course_handicap)} strokes.")