import streamlit as st
import duckdb
import pandas as pd
import json
import os

st.set_page_config(page_title="Golf Auto-Caddie Coach", page_icon="⛳", layout="wide")
st.sidebar.title("⛳ Auto-Caddie Menu")
page = st.sidebar.radio("Navigation", ["📊 Master Analytics Dashboard", "🧮 WHS & HNA Calculator", "⛳ Pre-Round Caddie"])

if page == "⛳ Pre-Round Caddie":
    st.header("⛳ Pre-Round Caddie & Course Strategy")
    st.markdown("Plan your target holes, bag mapping, and danger zones before stepping on the 1st tee.")
    
    conn = duckdb.connect("golf.duckdb", read_only=True)
    
    search_c = st.text_input("🔍 Search Course Name (e.g. Parkview, Houghton, Wanderers):", placeholder="Type course name...")
    
    if search_c:
        c_clean = search_c.strip().lower()
        
        # 1. Query Database (43 Historical Courses)
        cached = conn.execute("SELECT holes FROM course_blueprints WHERE LOWER(course_name) LIKE ?", (f"%{c_clean}%",)).fetchone()
        
        blueprint = None
        if cached:
            blueprint = json.loads(cached[0])
            st.success(f"✅ Loaded scorecard blueprint from database!")
        else:
            # 2. Gemini AI Fallback for unplayed courses
            st.info(f"🔍 Searching Gemini AI Engine for '{search_c}'...")
            api_key = st.secrets.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")
            
            if not api_key:
                st.warning("⚠️ Gemini API Key missing in Streamlit Secrets. Please add GEMINI_API_KEY to test new courses.")
            else:
                try:
                    import google.generativeai as genai
                    genai.configure(api_key=api_key)
                    model = genai.GenerativeModel('gemini-3.5-flash')
                    
                    prompt = f"""
                    IMPORTANT: Assume the golf course is located in South Africa unless a specific country or international city is mentioned. Find the official 18-hole golf scorecard for '{search_c}' (White/Mens tees).
                    Return ONLY a JSON array of 18 objects with keys: hole (1-18), par, si (stroke index), yardage.
                    Example format: [{{"hole": 1, "par": 4, "si": 7, "yardage": 380}}, ...]
                    DO NOT output markdown formatting outside the raw JSON string.
                    """
                    
                    response = model.generate_content(prompt)
                    raw_text = response.text.replace('```json', '').replace('```', '').strip()
                    blueprint = json.loads(raw_text)
                    st.success(f"🤖 Gemini AI fetched scorecard online!")
                except Exception as e:
                    st.error(f"❌ Error retrieving scorecard: {e}")

        if blueprint:
            st.markdown("---")
            st.subheader("🎯 Strategy Game Plan (8.3 Handicap)")
            
            df_bp = pd.DataFrame(blueprint)
            df_bp['Net Par Target'] = df_bp.apply(lambda r: r['par'] + 1 if r['si'] <= 10 else r['par'], axis=1)
            
            danger_holes = df_bp[df_bp['si'] <= 4]['hole'].tolist()
            scoring_holes = df_bp[df_bp['si'] >= 15]['hole'].tolist()
            
            c1, c2 = st.columns(2)
            with c1: st.error(f"🚨 **Danger Holes (Play for Net Par):** Holes {', '.join(map(str, danger_holes))}")
            with c2: st.success(f"🔥 **Scoring Holes (Green Light):** Holes {', '.join(map(str, scoring_holes))}")
                
            st.markdown("### ⛳ Hole-by-Hole Strategy")
            for h in blueprint:
                h_num, h_par, h_yd, h_si = h['hole'], h['par'], h['yardage'], h['si']
                with st.expander(f"Hole {h_num} - Par {h_par} | {h_yd}m | Stroke Index {h_si}"):
                    if h_par == 3:
                        st.write(f"**Target:** {h_yd}m. Use **7-Iron** (155m) or **6-Iron** (165m). Aim center green.")
                    elif h_par == 4:
                        if h_si <= 4: st.write(f"**Danger Hole:** 3-Wood tee shot. Mid-iron approach, play safe side. Accept Net Par.")
                        else: st.write(f"**Scoring Opportunity:** Driver off tee. Leaves wedge approach. Target pin.")
                    elif h_par == 5:
                        st.write(f"**3-Shot Strategy:** Driver tee shot. Lay up to 85m wedge range. Avoid hazards.")
                        
            st.markdown("---")
            st.dataframe(df_bp[['hole', 'par', 'si', 'yardage', 'Net Par Target']].set_index('hole').T, use_container_width=True)
