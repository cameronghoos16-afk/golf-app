import streamlit as st
import duckdb
import pandas as pd
import json
import os

st.set_page_config(page_title="Golf Auto-Caddie Coach", page_icon="⛳", layout="wide")

DB_FILE = "golf.duckdb"

st.sidebar.title("⛳ Auto-Caddie Menu")
page = st.sidebar.radio(
    "Navigation", 
    [
        "📊 Master Analytics Dashboard", 
        "📝 Post-Round Scorecards & Shots",
        "🏌️ Club Distances & Bag Stats",
        "🧮 WHS & HNA Calculator", 
        "⛳ Pre-Round Caddie"
    ]
)

# Helper function to open DB cleanly
def get_db_connection():
    if os.path.exists(DB_FILE):
        return duckdb.connect(DB_FILE, read_only=True)
    return None

# ==========================================
# PAGE 1: MASTER ANALYTICS DASHBOARD
# ==========================================
if page == "📊 Master Analytics Dashboard":
    st.header("📊 Master Analytics Dashboard")
    st.markdown("Overview of overall performance, historical scoring trends, and round highlights.")

    conn = get_db_connection()
    if conn:
        try:
            tables = [t[0] for t in conn.execute("SHOW TABLES").fetchall()]
            
            if "scorecards" in tables:
                df_rounds = conn.execute("""
                    SELECT 
                        s.id AS scorecard_id,
                        s.start_time,
                        s.course_name,
                        s.total_score,
                        r.longest_shot_m
                    FROM scorecards s
                    LEFT JOIN round_insights r ON CAST(s.id AS VARCHAR) = CAST(r.scorecard_id AS VARCHAR)
                    ORDER BY s.start_time DESC
                """).df()
                
                valid_scores = df_rounds[df_rounds['total_score'] > 0]
                
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Total Logged Rounds", len(df_rounds))
                if not valid_scores.empty:
                    c2.metric("Avg Score", round(valid_scores['total_score'].mean(), 1))
                    c3.metric("Best Score", int(valid_scores['total_score'].min()))
                if 'longest_shot_m' in df_rounds.columns and not df_rounds['longest_shot_m'].dropna().empty:
                    c4.metric("Longest Drive", f"{round(df_rounds['longest_shot_m'].max(), 1)}m")
                
                st.markdown("---")
                st.subheader("⛳ Recent Rounds Summary")
                df_display = df_rounds.copy()
                if 'start_time' in df_display.columns:
                    df_display['Date'] = pd.to_datetime(df_display['start_time']).dt.strftime('%Y-%m-%d %H:%M')
                st.dataframe(
                    df_display[['Date', 'course_name', 'total_score', 'longest_shot_m']].rename(
                        columns={'course_name': 'Course Name', 'total_score': 'Score', 'longest_shot_m': 'Longest Drive (m)'}
                    ),
                    use_container_width=True
                )
            conn.close()
        except Exception as e:
            st.error(f"Error loading dashboard: {e}")

# ==========================================
# PAGE 2: POST-ROUND SCORECARDS & SHOT LOGS
# ==========================================
elif page == "📝 Post-Round Scorecards & Shots":
    st.header("📝 Post-Round Scorecard Details & Shot Tracking")
    
    conn = get_db_connection()
    if conn:
        try:
            tables = [t[0] for t in conn.execute("SHOW TABLES").fetchall()]
            
            # 1. Full Scorecards Table
            if "scorecards" in tables:
                st.subheader("📋 Logged Scorecards")
                df_sc = conn.execute("SELECT id, start_time, course_name, total_par, total_score FROM scorecards ORDER BY start_time DESC").df()
                st.dataframe(df_sc, use_container_width=True)
            
            # 2. Individual User Shots Log
            if "user_shots" in tables:
                st.markdown("---")
                st.subheader("🎯 Shot-by-Shot Tracking (`user_shots`)")
                df_shots = conn.execute("SELECT * FROM user_shots ORDER BY date DESC, hole_num ASC, shot_order ASC").df()
                if not df_shots.empty:
                    st.dataframe(df_shots, use_container_width=True)
                else:
                    st.info("No recorded individual shot lines in `user_shots` yet.")
            
            # 3. Round Insights
            if "round_insights" in tables:
                st.markdown("---")
                st.subheader("💡 Round Insights & Highlights")
                df_ri = conn.execute("SELECT * FROM round_insights ORDER BY date DESC").df()
                st.dataframe(df_ri, use_container_width=True)
                
            conn.close()
        except Exception as e:
            st.error(f"Error loading post-round details: {e}")

# ==========================================
# PAGE 3: CLUB DISTANCES & BAG STATS
# ==========================================
elif page == "🏌️ Club Distances & Bag Stats":
    st.header("🏌️ Club Distances & Bag Yardages")
    
    conn = get_db_connection()
    if conn:
        try:
            tables = [t[0] for t in conn.execute("SHOW TABLES").fetchall()]
            
            col1, col2 = st.columns(2)
            
            with col1:
                if "garmin_official_clubs" in tables:
                    st.subheader("📱 Garmin Official Club Distances")
                    df_garmin = conn.execute("SELECT club_name, category, avg_m, max_m, est_carry_m FROM garmin_official_clubs").df()
                    st.dataframe(df_garmin, use_container_width=True)
            
            with col2:
                if "club_stats" in tables:
                    st.subheader("⚙️ Custom Club & Partial Swing Mapping (`club_stats`)")
                    df_cs = conn.execute("SELECT * FROM club_stats").df()
                    
                    # Parse raw JSON if available
                    parsed_clubs = []
                    for _, row in df_cs.iterrows():
                        if 'raw_json' in row and pd.notna(row['raw_json']):
                            try:
                                c_data = json.loads(row['raw_json'])
                                parsed_clubs.append({
                                    "Club Name": c_data.get("name", "Unknown"),
                                    "Avg Distance": c_data.get("averageDistance", 0),
                                    "Advice Distance": c_data.get("adviceDistance", 0),
                                    "Retired": c_data.get("retired", False)
                                })
                            except:
                                pass
                    if parsed_clubs:
                        st.dataframe(pd.DataFrame(parsed_clubs), use_container_width=True)
                    else:
                        st.dataframe(df_cs, use_container_width=True)
                        
            conn.close()
        except Exception as e:
            st.error(f"Error loading club statistics: {e}")

# ==========================================
# PAGE 4: WHS & HNA CALCULATOR
# ==========================================
elif page == "🧮 WHS & HNA Calculator":
    st.header("🧮 WHS & HNA Handicap Calculator")
    st.markdown("Calculate Score Differentials based on World Handicap System (WHS) standards.")
    
    col1, col2 = st.columns(2)
    with col1:
        gross_score = st.number_input("Gross Score:", min_value=50, max_value=150, value=82)
        course_rating = st.number_input("Course Rating (CR):", min_value=60.0, max_value=80.0, value=72.1, step=0.1)
    with col2:
        slope_rating = st.number_input("Slope Rating (SR):", min_value=55, max_value=155, value=130)
        pcc = st.number_input("PCC (Playing Conditions Calculation):", min_value=-1.0, max_value=3.0, value=0.0, step=0.5)
        
    if st.button("🧮 Calculate Differential"):
        differential = (113 / slope_rating) * (gross_score - course_rating - pcc)
        st.success(f"**Score Differential:** `{differential:.1f}`")

# ==========================================
# PAGE 5: PRE-ROUND CADDIE
# ==========================================
elif page == "⛳ Pre-Round Caddie":
    st.header("⛳ Pre-Round Caddie & Course Strategy")
    st.markdown("Plan target holes, bag mapping, and danger zones before stepping on the 1st tee.")
    
    search_c = st.text_input("🔍 Search Course Name (e.g. Parkview, Houghton, Blair Atholl):", placeholder="Enter course name...")
    
    if search_c:
        raw_query = search_c.strip()
        c_clean = raw_query.lower()
        
        blueprint = None
        matched_name = None
        
        conn = get_db_connection()
        if conn:
            try:
                words = c_clean.split()
                first_word = words[0] if words else ""
                
                cached = None
                if len(first_word) > 2:
                    param = f"%{first_word}%"
                    cached = conn.execute("SELECT course_name, holes FROM course_blueprints WHERE LOWER(course_name) LIKE ?", (param,)).fetchone()
                
                if not cached:
                    param = f"%{c_clean}%"
                    cached = conn.execute("SELECT course_name, holes FROM course_blueprints WHERE LOWER(course_name) LIKE ?", (param,)).fetchone()
                
                conn.close()
                
                if cached:
                    matched_name, holes_json = cached
                    blueprint = json.loads(holes_json)
                    st.success(f"✅ Loaded **{matched_name}** directly from local database!")
            except Exception as db_err:
                st.warning(f"Local DB query skipped: {db_err}")
        
        if not blueprint:
            ai_search_term = raw_query if any(loc in c_clean for loc in ['south africa', 'sa', 'usa', 'uk', 'scotland', 'australia']) else f"{raw_query}, South Africa"
            st.info(f"🔍 Searching Gemini AI Engine for '{ai_search_term}'...")
            
            api_key = st.secrets.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")
            if not api_key:
                st.error("⚠️ Gemini API Key missing in Streamlit Secrets.")
            else:
                try:
                    import google.generativeai as genai
                    genai.configure(api_key=api_key)
                    model = genai.GenerativeModel('gemini-1.5-flash')
                    
                    prompt = f"""
                    Find the official 18-hole golf scorecard for '{ai_search_term}' (White/Mens tees).
                    Return ONLY a JSON array of 18 objects with keys: hole (1-18), par, si (stroke index), yardage.
                    Example format: [{{"hole": 1, "par": 4, "si": 7, "yardage": 380}}, ...]
                    DO NOT output markdown text outside JSON.
                    """
                    
                    response = model.generate_content(prompt)
                    raw_text = response.text.replace('```json', '').replace('```', '').strip()
                    blueprint = json.loads(raw_text)
                    st.success(f"🤖 Gemini AI retrieved scorecard for **{ai_search_term}**!")
                except Exception as e:
                    st.error(f"❌ Could not retrieve scorecard via AI: {e}")
        
        if blueprint:
            st.markdown("---")
            st.subheader("🎯 Strategy Game Plan (8.3 Handicap)")
            
            df_bp = pd.DataFrame(blueprint)
            if 'si' in df_bp.columns and 'par' in df_bp.columns:
                df_bp['par'] = pd.to_numeric(df_bp['par'], errors='coerce').fillna(4).astype(int)
                df_bp['si'] = pd.to_numeric(df_bp['si'], errors='coerce').fillna(18).astype(int)
                if 'yardage' in df_bp.columns:
                    df_bp['yardage'] = pd.to_numeric(df_bp['yardage'], errors='coerce').fillna(0).astype(int)
                if 'hole' in df_bp.columns:
                    df_bp['hole'] = pd.to_numeric(df_bp['hole'], errors='coerce').fillna(0).astype(int)
                
                df_bp['Net Par Target'] = df_bp.apply(lambda r: r['par'] + 1 if r['si'] <= 10 else r['par'], axis=1)
                
                danger_holes = df_bp[df_bp['si'] <= 4]['hole'].tolist()
                scoring_holes = df_bp[df_bp['si'] >= 15]['hole'].tolist()
                
                col1, col2 = st.columns(2)
                with col1:
                    st.error(f"🚨 **Danger Holes (Play for Net Par):** Holes {', '.join(map(str, danger_holes))}")
                with col2:
                    st.success(f"🔥 **Scoring Holes (Green Light):** Holes {', '.join(map(str, scoring_holes))}")
                
                st.markdown("### ⛳ Hole-by-Hole Strategy")
                for _, h in df_bp.iterrows():
                    h_num, h_par, h_yd, h_si = h['hole'], h['par'], h['yardage'], h['si']
                    with st.expander(f"Hole {h_num} - Par {h_par} | {h_yd}m | Stroke Index {h_si}"):
                        if h_par == 3:
                            st.write(f"**Target:** {h_yd}m. Use **7-Iron** (155m) or **6-Iron** (165m). Aim center green.")
                        elif h_par == 4:
                            if h_si <= 4:
                                st.write("**Danger Hole:** 3-Wood tee shot. Mid-iron approach, play safe side. Accept Net Par.")
                            else:
                                st.write("**Scoring Opportunity:** Driver off tee. Leaves wedge approach. Target pin.")
                        elif h_par == 5:
                            st.write("**3-Shot Strategy:** Driver tee shot. Lay up to 85m wedge range. Avoid hazards.")
                
                st.markdown("---")
                st.dataframe(df_bp[['hole', 'par', 'si', 'yardage', 'Net Par Target']].set_index('hole').T, use_container_width=True)
