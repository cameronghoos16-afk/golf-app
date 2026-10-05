import streamlit as st
import duckdb
import pandas as pd
import json
import os

st.set_page_config(page_title="Golf Auto-Caddie Coach", page_icon="⛳", layout="wide")

DB_FILE = "golf.duckdb"

st.sidebar.title("⛳ Auto-Caddie Menu")
page = st.sidebar.radio("Navigation", ["📊 Master Analytics Dashboard", "🧮 WHS & HNA Calculator", "⛳ Pre-Round Caddie"])

# ==========================================
# PAGE 1: MASTER ANALYTICS DASHBOARD
# ==========================================
if page == "📊 Master Analytics Dashboard":
    st.header("📊 Master Analytics Dashboard")
    st.markdown("Track performance metrics, historical scores, and club performance.")

    if os.path.exists(DB_FILE):
        try:
            conn = duckdb.connect(DB_FILE, read_only=True)
            tables = [t[0] for t in conn.execute("SHOW TABLES").fetchall()]
            
            if "scorecards" in tables:
                join_query = """
                SELECT 
                    s.id AS scorecard_id,
                    s.start_time,
                    s.course_name,
                    s.total_score,
                    r.longest_shot_m
                FROM scorecards s
                LEFT JOIN round_insights r ON CAST(s.id AS VARCHAR) = CAST(r.scorecard_id AS VARCHAR)
                ORDER BY s.start_time DESC
                """
                df_rounds = conn.execute(join_query).df()
                valid_scores = df_rounds[df_rounds['total_score'] > 0]
                
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Total Logged Rounds", len(df_rounds))
                if not valid_scores.empty:
                    c2.metric("Avg Score", round(valid_scores['total_score'].mean(), 1))
                    c3.metric("Best Score", int(valid_scores['total_score'].min()))
                if 'longest_shot_m' in df_rounds.columns and not df_rounds['longest_shot_m'].dropna().empty:
                    c4.metric("Longest Drive", f"{round(df_rounds['longest_shot_m'].max(), 1)}m")
                
                st.markdown("---")
                st.subheader("⛳ Recent Rounds History")
                
                df_display = df_rounds.copy()
                if 'start_time' in df_display.columns:
                    df_display['Date'] = pd.to_datetime(df_display['start_time']).dt.strftime('%Y-%m-%d %H:%M')
                df_display = df_display[['Date', 'course_name', 'total_score', 'longest_shot_m']].rename(
                    columns={
                        'course_name': 'Course Name',
                        'total_score': 'Total Score',
                        'longest_shot_m': 'Longest Drive (m)'
                    }
                )
                st.dataframe(df_display, use_container_width=True)
            
            if "garmin_official_clubs" in tables:
                st.markdown("---")
                st.subheader("🏌️ Club Distances & Bag Performance")
                df_clubs = conn.execute("SELECT club_name, category, avg_m, max_m, est_carry_m FROM garmin_official_clubs").df()
                df_clubs.columns = ['Club Name', 'Category', 'Avg Distance (m)', 'Max Distance (m)', 'Est Carry (m)']
                st.dataframe(df_clubs, use_container_width=True)
                
            conn.close()
        except Exception as e:
            st.error(f"Error loading dashboard metrics: {e}")
    else:
        st.info("💡 `golf.duckdb` file not found.")

# ==========================================
# PAGE 2: WHS & HNA CALCULATOR
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
# PAGE 3: PRE-ROUND CADDIE
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
        
        # 1. Local Database Match First
        if os.path.exists(DB_FILE):
            try:
                conn = duckdb.connect(DB_FILE, read_only=True)
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
        
        # 2. AI Search Fallback
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
        
        # 3. Strategy Presentation
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
