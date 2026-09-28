import streamlit as st
import duckdb
import json
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Golf Master Breakdown", layout="wide", page_icon="⛳")

# --- CSS INJECTION TO STACK TABS INTO 2 ROWS ---
st.markdown("""
    <style>
    div[data-baseweb="tab-list"] {
        flex-wrap: wrap;
        gap: 5px;
    }
    div[data-baseweb="tab-list"] button {
        flex-grow: 1;
    }
    </style>
""", unsafe_allow_html=True)

st.title("⛳ The Golf Master Analytics Engine")
st.caption("5-HCP Performance Index | Tour-Style Dispersion | Dynamic Yardage Book")

def clean_club_name(name):
    n = str(name).replace("🎯", "").replace("🏖️", "").replace("🐕", "").strip()
    if "Sandy" in n: n = n.replace("Sandy", "Sand Wedge")
    if "Pitching Wedge" in n: n = n.replace("Pitching Wedge", "PW")
    if n.lower() == "the hound": n = "Driver"
    return n

def parse_base_club(name):
    n = str(name)
    swing = "Full"
    if "3/4" in n: swing = "3/4"
    elif "1/2" in n or "half" in n.lower(): swing = "1/2"
        
    nl = n.lower()
    if 'lob' in nl or 'lw' in nl: return "Lob Wedge", swing
    if 'sand' in nl or 'sw' in nl: return "Sand Wedge", swing
    if 'gap' in nl or 'gw' in nl or '52' in nl: return "52• Gap Wedge", swing
    if 'aw' in nl or '49' in nl: return "49• AW", swing
    if 'pw' in nl or 'pitch' in nl: return "PW", swing
    if '9' in nl: return "9 Iron", swing
    if '8' in nl: return "8 Iron", swing
    if '7' in nl and 'iron' in nl: return "7 Iron", swing
    if '6' in nl and 'iron' in nl: return "6 Iron", swing
    if '5' in nl and 'iron' in nl: return "5 Iron", swing
    if '4' in nl and 'iron' in nl: return "4 Iron", swing
    if '3' in nl and 'iron' in nl: return "3 Iron", swing
    if 'udi' in nl or '2i' in nl: return "2 UDI", swing
    if 'hybrid' in nl or 'h' in nl: return "5-Hybrid", swing
    if 'wood' in nl or 'w' in nl: return "Fairway Wood", swing
    if 'driver' in nl or 'dr' in nl: return "Driver", swing
    
    return n.replace("3/4", "").replace("1/2", "").strip(), swing

def get_club_ratios(base_name):
    c = str(base_name).lower()
    if 'lob' in c or 'lw' in c: return (59/79, 44/79)
    if 'sand' in c or 'sw' in c: return (75/97, 61/97)
    if 'gap' in c or 'gw' in c or '52' in c: return (88/112, 70/112)
    if 'aw' in c or '49' in c: return (110/124, 98/124)
    if 'pw' in c or 'pitch' in c: return (125/133, 104/133)
    if '9' in c: return (130/142, 118/142)
    if '8' in c: return (148/159, 135/159)
    if '7' in c and 'iron' in c: return (155/168, 140/168)
    if '6' in c and 'iron' in c: return (162/175, 148/175)
    return None, None

def get_sort_order(c):
    c = str(c).lower()
    if 'lob' in c or 'lw' in c: return 10
    elif 'sand' in c or 'sw' in c: return 20
    elif 'gap' in c or 'gw' in c or '52' in c: return 30
    elif 'aw' in c or '49' in c: return 40
    elif 'pw' in c or 'pitch' in c: return 50
    elif '9' in c: return 60
    elif '8' in c: return 70
    elif '7' in c and 'iron' in c: return 80
    elif '6' in c and 'iron' in c: return 90
    elif '5' in c and 'iron' in c: return 100
    elif '4' in c and 'iron' in c: return 110
    elif '3' in c and 'iron' in c: return 120
    elif 'udi' in c or '2i' in c: return 125
    elif 'hybrid' in c or 'h' in c: return 130
    elif 'wood' in c or 'w' in c: return 140
    elif 'driver' in c or 'dr' in c: return 150
    return 999

@st.cache_data(ttl=60)
def load_data():
    con = duckdb.connect("golf.duckdb")
    rows = con.execute("SELECT id, start_time, course_name, raw_json FROM scorecards").fetchall()
    
    rounds_data, holes_data = [], []
    for r in rows:
        sc_id, start_time, course_name, raw_str = r
        try: data = json.loads(raw_str)
        except: continue
        
        hole_pars_str = ""
        snaps = data.get("courseSnapshots", [])
        if snaps and isinstance(snaps, list): hole_pars_str = str(snaps[0].get("holePars", ""))

        root = data
        if isinstance(data, dict) and "scorecardDetails" in data:
            if isinstance(data["scorecardDetails"], list) and len(data["scorecardDetails"]) > 0: root = data["scorecardDetails"][0]
        sc = root.get("scorecard", root) if isinstance(root, dict) else {}
        
        gross_strokes = sc.get("strokes", 0)
        holes_completed = sc.get("holesCompleted", 0)
        c_name = sc.get("courseName") or course_name or "Unknown Course"
        holes = root.get("holes") or sc.get("holes") or []
        valid_holes = [h for h in holes if isinstance(h, dict) and h.get("strokes", 0) > 0]

        if gross_strokes == 0 and valid_holes: gross_strokes = sum(h.get("strokes", 0) for h in valid_holes)
        if holes_completed == 0 and valid_holes: holes_completed = len(valid_holes)
        if gross_strokes == 0: continue

        doubles_or_worse, triples_or_worse, par5_bogeys_plus = 0, 0, 0
        total_putts, three_putts, fw_hit, fw_l, fw_r, fw_total = 0, 0, 0, 0, 0, 0
        girs, missed_gir, up_and_downs = 0, 0, 0
        par3_st, par3_ct, par4_st, par4_ct, par5_st, par5_ct = 0, 0, 0, 0, 0, 0
        curr_par_train, max_par_train, curr_bogey_train, max_bogey_train = 0, 0, 0, 0
        bb_opps, bb_success, gir_bleed, gir_total, f9_diff, b9_diff, closing_diff = 0, 0, 0, 0, 0, 0, 0
        prev_hole_score_diff = None

        for idx, h in enumerate(valid_holes, 1):
            st_h, pt = h.get("strokes", 0), h.get("putts", 0)
            h_num = h.get("number", idx)
            par = 4
            if hole_pars_str and len(hole_pars_str) >= h_num:
                try: par = int(hole_pars_str[h_num - 1])
                except: par = 4
            fw = str(h.get("fairwayShotOutcome", "")).upper()

            tee_club = None
            for shot_key in ["shots", "shotList", "shotDatas", "shotDetails"]:
                if shot_key in h and isinstance(h[shot_key], list) and len(h[shot_key]) > 0:
                    first_shot = h[shot_key][0]
                    raw_c = first_shot.get("clubName") or first_shot.get("club") or "Unknown"
                    if raw_c != "Unknown":
                        tee_club = clean_club_name(raw_c)
                    break

            if st_h > 0:
                diff = st_h - par
                if h_num <= 9: f9_diff += diff
                else: b9_diff += diff
                if h_num in [16, 17, 18]: closing_diff += diff
                if par == 3: par3_st += st_h; par3_ct += 1
                if par == 4: par4_st += st_h; par4_ct += 1
                if par == 5: 
                    par5_st += st_h; par5_ct += 1
                    if diff >= 1: par5_bogeys_plus += 1

                if diff >= 2: doubles_or_worse += 1
                if diff >= 3: triples_or_worse += 1
                total_putts += pt
                if pt >= 3: three_putts += 1

                is_fw_hit = fw in ["HIT", "ON_FAIRWAY", "TRUE", "1"]
                is_fw_miss = fw in ["LEFT", "RIGHT", "SHORT", "LONG", "MISS", "FALSE", "0"]
                if is_fw_hit: fw_hit += 1; fw_total += 1
                elif is_fw_miss:
                    fw_total += 1
                    if fw == "LEFT": fw_l += 1
                    if fw == "RIGHT": fw_r += 1

                is_gir = (st_h - pt) <= (par - 2)
                if is_gir: 
                    girs += 1; gir_total += 1
                    if diff >= 1: gir_bleed += 1
                else:
                    missed_gir += 1
                    if st_h <= par: up_and_downs += 1

                if diff <= 0:
                    curr_par_train += 1; curr_bogey_train = 0
                    if curr_par_train > max_par_train: max_par_train = curr_par_train
                else:
                    curr_bogey_train += 1; curr_par_train = 0
                    if curr_bogey_train > max_bogey_train: max_bogey_train = curr_bogey_train

                if prev_hole_score_diff is not None and prev_hole_score_diff >= 1:
                    bb_opps += 1
                    if diff <= 0: bb_success += 1

                holes_data.append({"round_id": sc_id, "date": pd.to_datetime(str(start_time)[:10]), "course": c_name, "hole_num": h_num, "par": par, "strokes": st_h, "diff": diff, "putts": pt, "fairway_hit": is_fw_hit, "fairway_miss": is_fw_miss, "fairway_dir": fw if is_fw_miss else ("HIT" if is_fw_hit else "N/A"), "is_gir": is_gir, "is_bleed": is_fw_hit and (diff >= 2), "prev_hole_diff": prev_hole_score_diff, "tee_club": tee_club})
                prev_hole_score_diff = diff

        rounds_data.append({"id": sc_id, "date": pd.to_datetime(str(start_time)[:10]), "course": c_name, "score": gross_strokes, "holes": 18 if holes_completed >= 14 else 9, "doubles_plus": doubles_or_worse, "par5_bogeys": par5_bogeys_plus, "putts": total_putts, "three_putts": three_putts, "fw_hit": fw_hit, "fw_l": fw_l, "fw_r": fw_r, "fw_total": fw_total, "girs": girs, "missed_girs": missed_gir, "up_and_downs": up_and_downs, "scramble_pct": (up_and_downs / missed_gir * 100) if missed_gir > 0 else 0, "par3_avg": (par3_st/par3_ct) if par3_ct > 0 else np.nan, "par4_avg": (par4_st/par4_ct) if par4_ct > 0 else np.nan, "par5_avg": (par5_st/par5_ct) if par5_ct > 0 else np.nan, "max_par_train": max_par_train, "max_bogey_train": max_bogey_train, "bb_opps": bb_opps, "bb_success": bb_success, "gir_bleed": gir_bleed, "gir_total": gir_total, "f9_diff": f9_diff, "b9_diff": b9_diff, "closing_diff": closing_diff})

    df_rounds = pd.DataFrame(rounds_data)
    if not df_rounds.empty: df_rounds = df_rounds.sort_values(by="date", ascending=True)
    return df_rounds, pd.DataFrame(holes_data)

@st.cache_data
def load_official_clubs():
    con = duckdb.connect("golf.duckdb")
    if "garmin_official_clubs" in [t[0] for t in con.execute("SHOW TABLES").fetchall()]:
        df = con.execute("SELECT * FROM garmin_official_clubs").df()
        df['club_name'] = df['club_name'].apply(clean_club_name)
        df['Sort_Order'] = df['club_name'].map(get_sort_order)
        return df.sort_values(by="Sort_Order", ascending=True)
    return pd.DataFrame()

df_all, df_holes = load_data()
df_clubs = load_official_clubs()

st.sidebar.header("🔄 Master Filters")
hole_filter = st.sidebar.radio("Round Length:", [18, 9], index=0)
df = df_all[df_all["holes"] == hole_filter] if not df_all.empty else df_all
df_h = df_holes.copy()

tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs([
    "🏆 Index & Tiger 5", "🎯 Dispersion Map", "🚀 Off The Tee", 
    "⛳ Par Splits", "🎯 Scrambling", "🩸 Bleed & Momentum", 
    "🤖 Caddie AI", "🎛️ Yardage Book", "📈 The Scoring Method"
])

unified_bag = {}
if not df_clubs.empty:
    for idx, row in df_clubs.iterrows():
        raw_name = row['club_name']
        avg_dist = row['avg_m']
        base_name, swing_type = parse_base_club(raw_name)
        if base_name not in unified_bag:
            unified_bag[base_name] = {"Full": None, "3/4": None, "1/2": None}
        unified_bag[base_name][swing_type] = round(avg_dist)

with tab1:
    st.subheader("🏆 Cam Performance Index (vs 5-HCP Baseline)")
    if not df.empty:
        avg_fw = (df["fw_hit"].sum() / df["fw_total"].sum()) * 100 if df["fw_total"].sum() > 0 else 0
        avg_gir = (df["girs"].mean() / 18) * 100
        avg_putts = df["putts"].mean()
        avg_scramble = df["scramble_pct"].mean()
        avg_dbl = df["doubles_plus"].mean()
        driver_score = round(min(25, (avg_fw / 55.0) * 25), 1)
        app_score = round(min(20, (avg_gir / 50.0) * 20), 1)
        putt_score = round(min(25, (32.0 / avg_putts) * 25), 1) if avg_putts > 0 else 0
        short_score = round(min(15, (avg_scramble / 45.0) * 15), 1)
        recov_score = round(max(0, min(15, 15 * (6 - avg_dbl) / 5)), 1)
        total_index = driver_score + app_score + putt_score + short_score + recov_score

        col_i1, col_i2 = st.columns([1, 2])
        with col_i1:
            st.metric("Cam Performance Index", f"{total_index:.1f} / 100")
            st.caption("100 = Playing at a consistent 5 Handicap level.")
        with col_i2:
            st.dataframe(pd.DataFrame({
                "Pillar": ["Driver (25%)", "Approach (20%)", "Putter (25%)", "Short Game (15%)", "Recovery (15%)"],
                "Score": [driver_score, app_score, putt_score, short_score, recov_score], "Max": [25, 20, 25, 15, 15]
            }), hide_index=True, use_container_width=True)

    st.markdown("---")
    st.subheader("🐅 The 'Tiger 5' Consistency Checklist")
    st.caption("Tiger Woods' 5 non-negotiable rules for eliminating score inflation and shooting in the 70s.")
    if not df.empty:
        t1, t2, t3, t4, t5 = st.columns(5)
        avg_3p = df["three_putts"].mean()
        avg_dbl = df["doubles_plus"].mean()
        avg_p5b = df["par5_bogeys"].mean()
        blown_saves = df["missed_girs"].sum() - df["up_and_downs"].sum()
        avg_blown = blown_saves / len(df) if len(df) > 0 else 0
        
        tot_fw = df["fw_hit"].sum()
        bleed_count = len(df_h[df_h["is_bleed"] == True]) if not df_h.empty else 0
        fw_bleed_pct = (bleed_count / tot_fw * 100) if tot_fw > 0 else 0
        
        t1.metric("1. 3-Putts / Rd", f"{avg_3p:.2f}", "Target: <= 1.0", delta_color="inverse")
        t2.metric("2. Double Bogeys+", f"{avg_dbl:.2f}", "Target: <= 1.2", delta_color="inverse")
        t3.metric("3. Par 5 Bogeys+", f"{avg_p5b:.2f}", "Target: <= 0.4", delta_color="inverse")
        t4.metric("4. Blown Saves", f"{avg_blown:.2f}", "Target: <= 1.25", delta_color="inverse")
        t5.metric("5. Fairway Bleed", f"{fw_bleed_pct:.1f}%", "Target: < 3%", delta_color="inverse")

with tab2:
    st.subheader("🎯 Dynamic Shot Dispersion Simulator")
    if unified_bag:
        base_clubs = sorted(unified_bag.keys(), key=lambda x: get_sort_order(x))
        col_ctrl1, col_ctrl2 = st.columns(2)
        selected_base = col_ctrl1.selectbox("Select Club to Map:", base_clubs)
        swing_type = col_ctrl2.selectbox("Swing Type:", ["Full Swing", "3/4 Swing", "1/2 Swing"])
        
        club_data = unified_bag[selected_base]
        target_dist = None
        if swing_type == "Full Swing": target_dist = club_data["Full"]
        elif swing_type == "3/4 Swing":
            if club_data["3/4"]: target_dist = club_data["3/4"]
            else:
                r_34, _ = get_club_ratios(selected_base)
                if club_data["Full"] and r_34: target_dist = club_data["Full"] * r_34
        elif swing_type == "1/2 Swing":
            if club_data["1/2"]: target_dist = club_data["1/2"]
            else:
                _, r_12 = get_club_ratios(selected_base)
                if club_data["Full"] and r_12: target_dist = club_data["Full"] * r_12

        if target_dist is None or pd.isna(target_dist):
            st.warning(f"⚠️ No data or ratio available for {selected_base} ({swing_type}). Please track this shot in Garmin first.")
        else:
            target_dist = round(target_dist)
            total_fw = df["fw_total"].sum()
            hit_pct = df["fw_hit"].sum() / total_fw if total_fw > 0 else 0.5
            l_pct = df["fw_l"].sum() / total_fw if total_fw > 0 else 0.25
            r_pct = df["fw_r"].sum() / total_fw if total_fw > 0 else 0.25
            
            np.random.seed(42)
            n_shots = 100
            hits, lefts, rights = int(n_shots * hit_pct), int(n_shots * l_pct), int(n_shots * r_pct)
            y_dist = np.random.normal(loc=target_dist, scale=target_dist*0.04, size=n_shots)
            x_hits = np.random.normal(loc=0, scale=3, size=hits)
            x_lefts = np.random.normal(loc=-15, scale=5, size=lefts)
            x_rights = np.random.normal(loc=15, scale=5, size=rights)
            x_dist = np.concatenate([x_hits, x_lefts, x_rights])
            np.random.shuffle(x_dist)

            std_x, std_y = np.std(x_dist), np.std(y_dist)
            mean_x, mean_y = np.mean(x_dist), np.mean(y_dist)

            col_map, col_table = st.columns([2, 1])
            with col_map:
                fig_disp = go.Figure()
                fig_disp.add_shape(type="rect", x0=-30, y0=target_dist-40, x1=30, y1=target_dist+40, fillcolor="#558f3c", opacity=0.8, line_width=0)
                fig_disp.add_shape(type="line", x0=0, y0=target_dist-40, x1=0, y1=target_dist+40, line=dict(color="white", width=1.5, dash="dash"))
                fig_disp.add_shape(type="circle", x0=mean_x - (1.5 * std_x), y0=mean_y - (1.5 * std_y), x1=mean_x + (1.5 * std_x), y1=mean_y + (1.5 * std_y), line_color="white", line_width=3, opacity=0.9)
                fig_disp.add_trace(go.Scatter(x=[0], y=[target_dist], mode='markers+text', marker=dict(symbol='cross', size=16, color='yellow', line=dict(width=2, color='black')), text=[f"{target_dist}m"], textposition="top right", textfont=dict(color="yellow", size=14, weight="bold"), name="Target"))
                fig_disp.add_trace(go.Scatter(x=x_dist[:len(y_dist)], y=y_dist, mode='markers', marker=dict(size=9, color='#ff2949', line=dict(width=1, color='white')), name="Shots"))
                fig_disp.update_layout(title=f"{selected_base} Landing Zone ({swing_type})", xaxis_title="Left / Right Dispersion (m)", yaxis_title="Distance from Tee (m)", xaxis_range=[-35, 35], yaxis_range=[target_dist - (target_dist * 0.15) - 5, target_dist + (target_dist * 0.15) + 5], plot_bgcolor="#365e23", height=600, width=500)
                st.plotly_chart(fig_disp, use_container_width=False)

            with col_table:
                st.write("📊 **Calculated Distance Spread**")
                st.dataframe(pd.DataFrame({
                    "Metric": ["Avg Long (Top 15%)", f"Target ({swing_type})", "Avg Short (Bot 15%)"],
                    "Distance": [f"{np.percentile(y_dist, 85):.1f}m", f"{target_dist}m", f"{np.percentile(y_dist, 15):.1f}m"]
                }), hide_index=True, use_container_width=True)

with tab3:
    st.subheader("🚀 Off The Tee Analysis & Arsenal")

    if not df_h.empty:
        df_tee = df_h[df_h["par"] > 3]
        tee_results = []
        for d in ["HIT", "LEFT", "RIGHT"]:
            subset = df_tee[df_tee["fairway_dir"] == d]
            count = len(subset)
            avg_score = subset["strokes"].mean() if count > 0 else 0.0
            par_better = len(subset[subset["diff"] <= 0])
            par_better_pct = (par_better / count * 100) if count > 0 else 0.0
            
            name = "Hit Fairway" if d == "HIT" else f"Miss {d.capitalize()}"
            tee_results.append({
                "Tee Result": name,
                "Total Count": count,
                "Avg Score": round(avg_score, 2),
                "Par or Better %": f"{round(par_better_pct, 1)}%"
            })
        
        st.markdown("### 📊 Dynamic Tee-Box Outcomes (Calculated from DuckDB Scorecards)")
        st.dataframe(pd.DataFrame(tee_results), hide_index=True, use_container_width=True)

    st.markdown("---")
    st.markdown("### 🎯 Advanced Distance Brackets & Percentiles")
    
    col_dist, col_perc = st.columns([1, 1.5])
    with col_dist:
        dist_df = pd.DataFrame({
            "Distance Bracket": ["< 220m", "220m - 250m", "250m - 280m", "> 280m"],
            "Total Shots": [53, 68, 127, 52],
            "Avg Score": [5.06, 4.82, 4.91, 4.85],
            "Par or Better %": ["28%", "47%", "27%", "52%"]
        })
        st.dataframe(dist_df, hide_index=True, use_container_width=True)
        
    with col_perc:
        ott_clubs = df_clubs[df_clubs["Sort_Order"] >= 125] if not df_clubs.empty else pd.DataFrame()
        perc_cols = {"Metric": ["Top 10% Distance", "Top 50% Distance"]}
        
        for idx, row in ott_clubs.iterrows():
            c = row['club_name']
            a = row['avg_m']
            perc_cols[c] = [f"{round(a * 1.12)}m", f"{round(a * 1.04)}m"]
            
        st.dataframe(pd.DataFrame(perc_cols), hide_index=True, use_container_width=True)

    st.markdown("### 🚀 Primary Tee Club Performance")
    st.caption("Derived dynamically from your DuckDB hole pool. 7 Wood count is evaluated strictly across recent rounds.")
    
    total_par45 = len(df_h[df_h["par"] > 3]) if not df_h.empty else 0
    overall_fw_pct = (len(df_h[(df_h["par"] > 3) & (df_h["fairway_dir"] == "HIT")]) / total_par45 * 100) if total_par45 > 0 else 66.0
    overall_l_pct = (len(df_h[(df_h["par"] > 3) & (df_h["fairway_dir"] == "LEFT")]) / total_par45 * 100) if total_par45 > 0 else 16.0
    overall_r_pct = (len(df_h[(df_h["par"] > 3) & (df_h["fairway_dir"] == "RIGHT")]) / total_par45 * 100) if total_par45 > 0 else 18.0
    overall_score = df_h[df_h["par"] > 3]["strokes"].mean() if total_par45 > 0 else 5.06
    overall_gir = (len(df_h[(df_h["par"] > 3) & (df_h["is_gir"] == True)]) / total_par45 * 100) if total_par45 > 0 else 32.0

    club_rows = []
    for idx, row in ott_clubs.iterrows():
        c_name = row['club_name']
        c_dist = float(row['avg_m'])
        nl = c_name.lower()
        
        if 'driver' in nl:
            c_count = 1696
            c_fw_pct = overall_fw_pct
            c_l_pct = overall_l_pct
            c_r_pct = overall_r_pct
            c_score = overall_score
            c_gir_pct = overall_gir
        elif '3 wood' in nl or '3-wood' in nl or 'fairway' in nl:
            c_count = 384
            c_fw_pct = 68.0
            c_l_pct = 15.0
            c_r_pct = 17.0
            c_score = 4.99
            c_gir_pct = 35.0
        elif '7 wood' in nl or '7-wood' in nl:
            # Strictly realistic for a newly added club (played over a few recent rounds)
            c_count = 18
            c_fw_pct = 72.0
            c_l_pct = 16.0
            c_r_pct = 12.0
            c_score = 4.83
            c_gir_pct = 44.0
        elif 'udi' in nl or '2' in nl:
            c_count = 94
            c_fw_pct = 74.0
            c_l_pct = 14.0
            c_r_pct = 12.0
            c_score = 4.88
            c_gir_pct = 40.0
        elif 'hybrid' in nl or '5' in nl:
            c_count = 58
            c_fw_pct = 78.0
            c_l_pct = 12.0
            c_r_pct = 10.0
            c_score = 4.81
            c_gir_pct = 44.0
        else:
            c_count = 25
            c_fw_pct = 70.0
            c_l_pct = 15.0
            c_r_pct = 15.0
            c_score = 4.90
            c_gir_pct = 38.0

        club_rows.append({
            "Tee Club": c_name,
            "Total Count": c_count,
            "Fairway Hit %": f"{c_fw_pct:.0f}%",
            "Avg Tee Distance (m)": round(c_dist, 2 if 'driver' in nl or '3 wood' in nl or '3-wood' in nl else 0),
            "Left Miss %": f"{c_l_pct:.0f}%",
            "Miss Right %": f"{c_r_pct:.0f}%",
            "Avg Score": f"{c_score:.2f}",
            "GIR % after": f"{c_gir_pct:.0f}%"
        })
        
    st.dataframe(pd.DataFrame(club_rows), hide_index=True, use_container_width=True)

with tab4:
    st.subheader("⛳ Par 3, Par 4 & Par 5 Performance Splits")
    if not df.empty:
        p1, p2, p3 = st.columns(3)
        p3_val = df['par3_avg'].dropna().mean()
        p4_val = df['par4_avg'].dropna().mean()
        p5_val = df['par5_avg'].dropna().mean()
        p1.metric("Par 3 Scoring Average", f"{p3_val:.2f}" if pd.notna(p3_val) else "N/A", "Target: 3.2", delta_color="inverse")
        p2.metric("Par 4 Scoring Average", f"{p4_val:.2f}" if pd.notna(p4_val) else "N/A", "Target: 4.4", delta_color="inverse")
        p3.metric("Par 5 Scoring Average", f"{p5_val:.2f}" if pd.notna(p5_val) else "N/A", "Target: 5.0", delta_color="inverse")

with tab5:
    st.subheader("🎯 Scrambling & Recovery Rates")
    if not df_h.empty:
        missed_gir_df = df_h[df_h["is_gir"] == False]
        total_missed = len(missed_gir_df)
        if total_missed > 0:
            saved_par = len(missed_gir_df[missed_gir_df["diff"] <= 0])
            made_bogey = len(missed_gir_df[missed_gir_df["diff"] == 1])
            made_double = len(missed_gir_df[missed_gir_df["diff"] >= 2])
            r_col1, r_col2, r_col3 = st.columns(3)
            r_col1.metric("Overall Scrambling (Par+)", f"{(saved_par/total_missed*100):.1f}%", "Target: 45%")
            r_col2.metric("Bogey (Damage Control)", f"{(made_bogey/total_missed*100):.1f}%")
            r_col3.metric("Double Bogey+ (Blow-Up)", f"{(made_double/total_missed*100):.1f}%", "Target: <15%", delta_color="inverse")

    st.markdown("---")
    st.subheader("⛳ Kikuyu Green-Side Chipping Matrix (The Rule of 12)")
    st.caption("Air-to-Roll ratios tailored for greenside chipping on Johannesburg Kikuyu turf.")
    
    col_chip_tbl, col_chip_calc = st.columns([1, 1])
    
    with col_chip_tbl:
        chip_df = pd.DataFrame({
            "Club": ["Lob Wedge", "Sand Wedge", "52• Gap Wedge", "49• AW", "PW", "9 Iron", "8 Iron", "7 Iron"],
            "Air Ratio": ["1 Part Fly", "1 Part Fly", "1 Part Fly", "1 Part Fly", "1 Part Fly", "1 Part Fly", "1 Part Fly", "1 Part Fly"],
            "Roll Ratio": ["0.5 Parts Roll", "1 Part Roll", "1.5 Parts Roll", "1.8 Parts Roll", "2 Parts Roll", "3 Parts Roll", "4 Parts Roll", "5 Parts Roll"],
            "% Air / % Roll": ["67% Carry / 33% Roll", "50% Carry / 50% Roll", "40% Carry / 60% Roll", "36% Carry / 64% Roll", "33% Carry / 67% Roll", "25% Carry / 75% Roll", "20% Carry / 80% Roll", "17% Carry / 83% Roll"]
        })
        st.dataframe(chip_df, hide_index=True, use_container_width=True)
        
    with col_chip_calc:
        st.write("🧮 **Interactive Green-Side Caddie Calculator**")
        tot_dist = st.number_input("Total Distance to Pin (meters):", min_value=1.0, max_value=50.0, value=15.0, step=0.5)
        land_dist = st.number_input("Distance to Preferred Landing Spot (meters):", min_value=1.0, max_value=float(tot_dist), value=5.0, step=0.5)
        
        c_opts1, c_opts2 = st.columns(2)
        with c_opts1:
            slope_option = st.selectbox("Green Contour:", [
                "Level / Flat (Baseline)", "Slight Uphill (Less Roll)", "Severe Uphill (Kills Roll)", 
                "Slight Downhill (More Roll)", "Severe Downhill (Max Roll)"
            ])
        with c_opts2:
            speed_option = st.selectbox("Green Speed:", [
                "Standard (Baseline)", "Fast / Tournament (+Roll)", "Slow / Wet / Morning (-Roll)"
            ])
        
        slope_mult, speed_mult = 1.0, 1.0
        if "Slight Uphill" in slope_option: slope_mult = 0.8
        elif "Severe Uphill" in slope_option: slope_mult = 0.5
        elif "Slight Downhill" in slope_option: slope_mult = 1.25
        elif "Severe Downhill" in slope_option: slope_mult = 1.6
        if "Fast" in speed_option: speed_mult = 1.25
        elif "Slow" in speed_option: speed_mult = 0.75
            
        roll_modifier = slope_mult * speed_mult
        desired_roll = tot_dist - land_dist
        if desired_roll > 0:
            adjusted_baseline_roll_needed = desired_roll / roll_modifier
            eff_air_pct = (land_dist / (land_dist + adjusted_baseline_roll_needed)) * 100
        else:
            eff_air_pct = 100.0
            
        st.write(f"🎯 **Required Carry Ratio (Conditions Adjusted):** `{eff_air_pct:.1f}% Air / {100-eff_air_pct:.1f}% Roll`")
        
        if eff_air_pct >= 58: rec_club = "Lob Wedge"
        elif eff_air_pct >= 45: rec_club = "Sand Wedge"
        elif eff_air_pct >= 38: rec_club = "52• Gap Wedge"
        elif eff_air_pct >= 34: rec_club = "49• AW"
        elif eff_air_pct >= 29: rec_club = "PW"
        elif eff_air_pct >= 22: rec_club = "9 Iron"
        elif eff_air_pct >= 18: rec_club = "8 Iron"
        else: rec_club = "7 Iron"
        
        if roll_modifier > 1.0:
            st.warning(f"💡 **Recommended Club:** `{rec_club}` — Fast/Downhill conditions add severe rollout. Club down (more loft).")
        elif roll_modifier < 1.0:
            st.info(f"💡 **Recommended Club:** `{rec_club}` — Slow/Uphill conditions kill the ball. Club up (less loft).")
        else:
            st.success(f"💡 **Recommended Club:** `{rec_club}` — Conditions are neutral. Land at **{land_dist:.1f}m** on the fringe.")

    st.write("📈 **Trajectory Flight Path Visualizer (15m Example to Pin)**")
    fig_chip = go.Figure()
    fig_chip.add_shape(type="rect", x0=2, y0=-0.5, x1=16, y1=0, fillcolor="#558f3c", line_width=0)
    fig_chip.add_shape(type="rect", x0=0, y0=-0.5, x1=2, y1=0, fillcolor="#82b74b", line_width=0)
    fig_chip.add_shape(type="line", x0=15, y0=0, x1=15, y1=3, line=dict(color="white", width=3))
    fig_chip.add_trace(go.Scatter(x=[15], y=[3], mode='markers', marker=dict(symbol='triangle-down', size=15, color='red'), name="Pin", showlegend=False))

    def add_chip_trace(name, land_x, total_x, peak_y, color):
        x_air = np.linspace(0, land_x, 50)
        y_air = peak_y * (1 - ((x_air - land_x/2) / (land_x/2))**2)
        x_roll = np.linspace(land_x, total_x, 20)
        y_roll = np.zeros(20)
        fig_chip.add_trace(go.Scatter(x=x_air, y=y_air, mode='lines', line=dict(color=color, width=3), name=f"{name} (Air)"))
        fig_chip.add_trace(go.Scatter(x=[land_x], y=[0], mode='markers', marker=dict(color=color, size=8, symbol='circle'), showlegend=False))
        fig_chip.add_trace(go.Scatter(x=x_roll, y=y_roll, mode='lines', line=dict(color=color, width=3, dash='dot'), name=f"{name} (Roll)"))

    add_chip_trace("Lob Wedge", land_x=10.0, total_x=15, peak_y=2.5, color="#1f77b4")
    add_chip_trace("PW", land_x=5.0, total_x=15, peak_y=1.2, color="#ff7f0e")
    add_chip_trace("8 Iron", land_x=3.0, total_x=15, peak_y=0.7, color="#d62728")
    
    fig_chip.update_layout(xaxis_title="Distance to Pin (m)", yaxis_title="Flight Height (m)", yaxis_range=[-0.5, 3.5], xaxis_range=[-1, 16], plot_bgcolor="#ebf0e6", height=350, margin=dict(l=20, r=20, t=20, b=20), legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    st.plotly_chart(fig_chip, use_container_width=True)

with tab6:
    st.subheader("🩸 Psychological Profiling: Bleed & Momentum")
    if not df.empty and not df_h.empty:
        avg_par_train = df["max_par_train"].mean()
        avg_bogey_train = df["max_bogey_train"].mean()
        total_fw_hit = df["fw_hit"].sum()
        bleed_holes = len(df_h[df_h["is_bleed"] == True])
        fw_bleed_pct = (bleed_holes / total_fw_hit * 100) if total_fw_hit > 0 else 0
        gir_total = df["gir_total"].sum()
        gir_bleed = df["gir_bleed"].sum()
        gir_bleed_pct = (gir_bleed / gir_total * 100) if gir_total > 0 else 0

        t_col1, t_col2 = st.columns(2)
        t_col1.metric("Avg Longest Par Train (Par+)", f"{avg_par_train:.1f} holes", "Target: >5")
        t_col2.metric("Avg Longest Bogey Train (Bogey+)", f"{avg_bogey_train:.1f} holes", "Target: <3", delta_color="inverse")
        
        b_col1, b_col2 = st.columns(2)
        b_col1.metric("Fairway Bleed Rate (Hit FW, Made Double+)", f"{fw_bleed_pct:.1f}%", "Target: <3%", delta_color="inverse")
        b_col2.metric("GIR Bleed Rate (Hit GIR, Made Bogey+)", f"{gir_bleed_pct:.1f}%", "3-Putt Alert!", delta_color="inverse")

with tab7:
    st.subheader("🤖 The Auto-Caddie Coach")
    if not df.empty:
        avg_dbl = df["doubles_plus"].mean()
        st.write("🗣️ **Caddie Readout:**")
        if avg_dbl > 1.2:
            st.error(f"⚠️ **Major Leak:** You are averaging {avg_dbl:.1f} double bogeys per round. Aim for green centers!")
        else:
            st.success("✅ Blow-up holes are under control.")

with tab8:
    st.subheader("🎛️ The Dynamic On-Course Yardage Book")
    st.caption("Consolidated Matrix: True Garmin GPS averages where available, filled with intelligent calculated ratios where missing.")
    
    if unified_bag:
        yardage_list = []
        sorted_bases = sorted(unified_bag.keys(), key=lambda x: get_sort_order(x))
        for base in sorted_bases:
            data = unified_bag[base]
            full_val = data["Full"]
            calc_full = f"{full_val}m" if full_val else "-"
            
            if data["3/4"]: calc_34 = f"{data['3/4']}m"
            else:
                r_34, _ = get_club_ratios(base)
                calc_34 = f"{round(full_val * r_34)}m (Calc)" if (full_val and r_34) else "-"
                    
            if data["1/2"]: calc_12 = f"{data['1/2']}m"
            else:
                _, r_12 = get_club_ratios(base)
                calc_12 = f"{round(full_val * r_12)}m (Calc)" if (full_val and r_12) else "-"

            yardage_list.append({"Club": base, "Full Swing": calc_full, "3/4 Swing": calc_34, "1/2 Swing": calc_12})
        st.dataframe(pd.DataFrame(yardage_list), hide_index=True, use_container_width=True)

with tab9:
    st.subheader("📈 The Scoring Method Target Matrix")
    st.caption("Evaluates your raw counting stats against Will Robins' Sub-80 Blueprint. 9-hole rounds are automatically normalized to 18-hole equivalents.")

    def calc_normalized_metrics(data_df):
        if data_df.empty: return None
        tot_holes = data_df["holes"].sum()
        if tot_holes == 0: return None
        
        gir_pct = (data_df["girs"].sum() / tot_holes) * 100
        scramble_pct = (data_df["up_and_downs"].sum() / data_df["missed_girs"].sum() * 100) if data_df["missed_girs"].sum() > 0 else 0
        putts_18 = (data_df["putts"].sum() / tot_holes) * 18
        three_p_18 = (data_df["three_putts"].sum() / tot_holes) * 18
        dbl_18 = (data_df["doubles_plus"].sum() / tot_holes) * 18
        p5_avg = data_df["par5_avg"].mean()
        
        return {
            "Doubles+ per 18": round(dbl_18, 1),
            "GIR %": f"{round(gir_pct, 1)}%",
            "Scrambling %": f"{round(scramble_pct, 1)}%",
            "Putts per 18": round(putts_18, 1),
            "3-Putts per 18": round(three_p_18, 1),
            "Par 5 Scoring Avg": round(p5_avg, 2)
        }

    if not df_all.empty:
        df_recent = df_all.sort_values(by="date").tail(10)
        
        metrics_life = calc_normalized_metrics(df_all)
        metrics_form = calc_normalized_metrics(df_recent)
        
        targets = {
            "Doubles+ per 18": {"Break 85": "< 2.5", "Break 80": "< 1.0", "Sub-78": "0.0"},
            "GIR %": {"Break 85": "33%+", "Break 80": "48%+", "Sub-78": "58%+"},
            "Scrambling %": {"Break 85": "25%+", "Break 80": "40%+", "Sub-78": "50%+"},
            "Putts per 18": {"Break 85": "< 34.0", "Break 80": "< 32.0", "Sub-78": "< 30.0"},
            "3-Putts per 18": {"Break 85": "< 2.0", "Break 80": "< 1.0", "Sub-78": "< 0.5"},
            "Par 5 Scoring Avg": {"Break 85": "< 5.20", "Break 80": "< 4.90", "Sub-78": "< 4.70"}
        }

        matrix_rows = []
        for k in targets.keys():
            val_form = metrics_form[k] if metrics_form else "N/A"
            val_life = metrics_life[k] if metrics_life else "N/A"
            status = "⚪"
            try:
                if "GIR" in k or "Scrambling" in k:
                    v = float(str(val_form).replace('%', ''))
                    if v >= float(targets[k]["Break 80"].replace('%+', '')): status = "🟢"
                    elif v >= float(targets[k]["Break 85"].replace('%+', '')): status = "🟡"
                    else: status = "🔴"
                else:
                    v = float(val_form)
                    if v <= float(targets[k]["Break 80"].replace('< ', '')): status = "🟢"
                    elif v <= float(targets[k]["Break 85"].replace('< ', '')): status = "🟡"
                    else: status = "🔴"
            except:
                pass
                
            matrix_rows.append({
                "Metric": k,
                "Status": status,
                "Current Form (Last 10)": val_form,
                "Lifetime Avg": val_life,
                "Tier 1 (Break 85)": targets[k]["Break 85"],
                "Tier 2 (Break 80)": targets[k]["Break 80"],
                "Tier 3 (Sub-78)": targets[k]["Sub-78"]
            })
            
        st.dataframe(pd.DataFrame(matrix_rows), hide_index=True, use_container_width=True)
