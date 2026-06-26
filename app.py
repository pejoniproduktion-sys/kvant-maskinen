import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import json
import gspread
from google.oauth2.service_account import Credentials

# ==========================================
# 1. APPENS INSTÄLLNINGAR & GOOGLE-KOPPLING
# ==========================================
st.set_page_config(page_title="Kvant-Maskinen v6.4", page_icon="🚀", layout="wide")

def get_gspread_client():
    creds_dict = json.loads(st.secrets["google_credentials"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
    return gspread.authorize(creds)

# --- Funktioner för Datahämtning ---
def ladda_historik_gspread():
    try:
        gc = get_gspread_client()
        sh = gc.open_by_url(st.secrets["google_sheet_url"])
        worksheet = sh.worksheet("Historik")
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        if df.empty: 
            return pd.DataFrame(columns=['datum', 'varde_value', 'varde_utdelning', 'varde_momentum', 'portfolj_varde', 'omx_index'])
        df['datum'] = df['datum'].astype(str)
        for col in ['varde_value', 'varde_utdelning', 'varde_momentum', 'portfolj_varde', 'omx_index']:
            if col not in df.columns: 
                df[col] = 0.0
            else: 
                df[col] = pd.to_numeric(df[col].astype(str).str.replace("'", "", regex=False).str.replace(' ', '').str.replace(',', '.'), errors='coerce').fillna(0.0)
        return df.sort_values('datum').reset_index(drop=True)
    except: 
        return pd.DataFrame(columns=['datum', 'varde_value', 'varde_utdelning', 'varde_momentum', 'portfolj_varde', 'omx_index'])

def spara_historik_gspread(datum_str, v_val, v_utd, v_mom, tot, omx):
    try:
        gc = get_gspread_client()
        sh = gc.open_by_url(st.secrets["google_sheet_url"])
        worksheet = sh.worksheet("Historik")
        data = worksheet.get_all_values()
        if not data or len(data[0]) < 6:
            worksheet.clear()
            worksheet.append_row(["datum", "varde_value", "varde_utdelning", "varde_momentum", "portfolj_varde", "omx_index"])
            data = [["datum", "varde_value", "varde_utdelning", "varde_momentum", "portfolj_varde", "omx_index"]]
        rows = data[1:]
        found_row = None
        for i, row in enumerate(rows):
            if row and row[0] == datum_str:
                found_row = i + 2
                break
        
        if found_row:
            worksheet.update_cell(found_row, 2, f"'{float(v_val):.2f}")
            worksheet.update_cell(found_row, 3, f"'{float(v_utd):.2f}")
            worksheet.update_cell(found_row, 4, f"'{float(v_mom):.2f}")
            worksheet.update_cell(found_row, 5, f"'{float(tot):.2f}")
            worksheet.update_cell(found_row, 6, f"'{float(omx):.2f}")
        else: 
            worksheet.append_row([datum_str, f"'{float(v_val):.2f}", f"'{float(v_utd):.2f}", f"'{float(v_mom):.2f}", f"'{float(tot):.2f}", f"'{float(omx):.2f}"], value_input_option='USER_ENTERED')
        return True
    except: 
        return False

def ladda_innehav_gspread(strategi):
    fliknamn = f"Innehav_{strategi}"
    try:
        gc = get_gspread_client()
        sh = gc.open_by_url(st.secrets["google_sheet_url"])
        try: 
            worksheet = sh.worksheet(fliknamn)
        except:
            worksheet = sh.add_worksheet(title=fliknamn, rows="100", cols="5")
            worksheet.append_row(["Bolagsnamn", "Ticker", "Antal", "Kurs"])
            return pd.DataFrame(columns=["Bolagsnamn", "Ticker", "Antal", "Kurs"])
        
        data = worksheet.get_all_records()
        if not data: 
            return pd.DataFrame(columns=["Bolagsnamn", "Ticker", "Antal", "Kurs"])
            
        df = pd.DataFrame(data)
        return df
    except: 
        return pd.DataFrame(columns=["Bolagsnamn", "Ticker", "Antal", "Kurs"])

def spara_innehav_gspread(df_ny, strategi):
    fliknamn = f"Innehav_{strategi}"
    try:
        gc = get_gspread_client()
        sh = gc.open_by_url(st.secrets["google_sheet_url"])
        try: 
            worksheet = sh.worksheet(fliknamn)
        except: 
            worksheet = sh.add_worksheet(title=fliknamn, rows="100", cols="5")
        worksheet.clear() 
        worksheet.append_row(["Bolagsnamn", "Ticker", "Antal", "Kurs"]) 
        
        df_clean = df_ny.copy()
        df_clean = df_clean.dropna(subset=['Ticker'])
        df_clean = df_clean[df_clean['Ticker'].astype(str).str.strip() != '']
        
        if not df_clean.empty: 
            df_clean['Antal'] = df_clean['Antal'].apply(lambda x: str(int(x)))
            df_clean['Kurs'] = df_clean['Kurs'].apply(lambda x: f"'{float(x):.2f}")
            worksheet.append_rows(df_clean[["Bolagsnamn", "Ticker", "Antal", "Kurs"]].values.tolist(), value_input_option='USER_ENTERED')
        return True
    except: 
        return False

def ladda_ai_analys_gspread():
    try:
        gc = get_gspread_client()
        sh = gc.open_by_url(st.secrets["google_sheet_url"])
        worksheet = sh.worksheet("AI_Analys")
        data = worksheet.get_all_values()
        if len(data) >= 2:
            return data[0][0], data[1][0]
        return None, "Ingen analys hittades."
    except:
        return None, "Väntar på att AI-roboten ska köra sin första analys..."

def ladda_automatisk_ma200_gspread():
    try:
        gc = get_gspread_client()
        sh = gc.open_by_url(st.secrets["google_sheet_url"])
        worksheet = sh.worksheet("MA200_Varningar")
        data = worksheet.get_all_records()
        return pd.DataFrame(data)
    except:
        return pd.DataFrame()

# ==========================================
# 2. GLOBAL DATASANERING & SESSION STATE
# ==========================================
strategier = ["Value", "Utdelning", "Momentum"]

for s in strategier:
    if f'bef_portfolj_{s}' not in st.session_state:
        st.session_state[f'bef_portfolj_{s}'] = ladda_innehav_gspread(s)
    
    df = st.session_state[f'bef_portfolj_{s}']
    if isinstance(df, pd.DataFrame):
        rename_map = {c: c.capitalize().strip() for c in df.columns if c.lower().strip() in ['bolagsnamn', 'ticker', 'antal', 'kurs']}
        df = df.rename(columns=rename_map)
        
        for col in ["Bolagsnamn", "Ticker", "Antal", "Kurs"]:
            if col not in df.columns:
                df[col] = 0 if col in ["Antal", "Kurs"] else ""
        
        df['Ticker'] = df['Ticker'].astype(str).str.upper().str.strip()
        df['Bolagsnamn'] = df['Bolagsnamn'].astype(str).str.strip()
        df['Antal'] = pd.to_numeric(df['Antal'].astype(str).str.replace("'", "", regex=False).str.replace(r'\s+', '', regex=True).str.replace(',', '.'), errors='coerce').fillna(0).astype(int)
        
        clean_kurs = df['Kurs'].astype(str).str.lower().str.replace("'", "", regex=False).str.replace(r'\s+', '', regex=True).str.replace(',', '.').replace('nan', '0')
        df['Kurs'] = pd.to_numeric(clean_kurs, errors='coerce').fillna(0.0).astype(float)
        
        df = df[~df['Ticker'].isin(['', 'NAN', 'NaN', 'nan', 'None'])]
        st.session_state[f'bef_portfolj_{s}'] = df.reset_index(drop=True)
    else:
        st.session_state[f'bef_portfolj_{s}'] = pd.DataFrame(columns=["Bolagsnamn", "Ticker", "Antal", "Kurs"])

if 'mal_portfolj' not in st.session_state: 
    st.session_state['mal_portfolj'] = pd.DataFrame(columns=["Bolagsnamn", "Ticker", "Kurs"])
if 'aktiv_strategi' not in st.session_state: 
    st.session_state['aktiv_strategi'] = "Value"
if 'ombalansering_beraknad' not in st.session_state: 
    st.session_state['ombalansering_beraknad'] = False

def hamta_malviktning(manad):
    if manad in [11, 12, 1]: return {"Value": 0.50, "Utdelning": 0.30, "Momentum": 0.20}
    elif manad in [2, 3, 4]: return {"Value": 0.20, "Utdelning": 0.40, "Momentum": 0.40}
    elif manad in [5, 6, 7, 8]: return {"Value": 0.30, "Utdelning": 0.30, "Momentum": 0.40}
    else: return {"Value": 0.20, "Utdelning": 0.20, "Momentum": 0.60}

# ==========================================
# 3. SIDOMENY & STRIPPNING/TVÄTT
# ==========================================
st.sidebar.title("Kvant-Maskinen 🚀")
st.sidebar.markdown("---")
meny_val = st.sidebar.radio(
    "Välj vy:",
    [
        "📊 Översikt & Historik", 
        "🧠 Portföljanalys & Råd",
        "💼 Min Portfölj", 
        "📅 Säsongsmönster & Viktning", 
        "📖 Om Kvantstrategierna",
        "📈 Strategi: Trending Value", 
        "💸 Strategi: Trend. Utdelning", 
        "⚡ Strategi: Momentum", 
        "⚖️ Ombalansering"
    ]
)
st.sidebar.markdown("---")
uppladdad_fil = st.sidebar.file_uploader("Ladda upp Börsdata-fil", type=["xlsx", "csv"])

def ladda_och_tvatta_basdata(fil):
    df = pd.read_csv(fil, sep=';', encoding='utf-8') if fil.name.endswith('.csv') else pd.read_excel(fil)
    k_namn = next((c for c in df.columns if 'bolagsnamn' in c.lower() or 'namn' in c.lower()), df.columns[0])
    k_tick = next((c for c in df.columns if 'ticker' in c.lower()), df.columns[1])
    k_kurs = next((c for c in df.columns if 'aktiekurs' in c.lower() or ('kurs' in c.lower() and 'utveck' not in c.lower())), None)
    if not k_kurs: k_kurs = df.columns[2]
    
    df[k_kurs] = pd.to_numeric(df[k_kurs].astype(str).str.replace(' ', '').str.replace(',', '.'), errors='coerce').fillna(0)
    
    k_bv = next((c for c in df.columns if 'börsvärde' in c.lower()), None)
    k_lista = next((c for c in df.columns if 'lista' in c.lower() or 'marknad' in c.lower()), None)
    if k_bv:
        df[k_bv] = pd.to_numeric(df[k_bv].astype(str).str.replace(' ', '').str.replace(',', '.'), errors='coerce').fillna(0)
        df = df[df[k_bv] >= 500].copy()
    if k_lista:
        df = df[df[k_lista].astype(str).str.contains('Large|Mid|Small', case=False, na=False)].copy()
    return df, k_namn, k_tick, k_kurs

# ==========================================
# 4. SIDORNAS LOGIK
# ==========================================

# --- SIDA 1: ÖVERSIKT & HISTORIK ---
if meny_val == "📊 Översikt & Historik":
    st.title("📊 Portföljöversikt & Dashboard")
    
    auto_warn_df = ladda_automatisk_ma200_gspread()
    if auto_warn_df.empty:
        st.success("🟢 **Trendindikator (MA200):** Alla dina innehav handlas just nu över sin långsiktiga trend (MA200).")
    else:
        st.error(f"🔴 **Trendindikator (MA200):** {len(auto_warn_df)} aktier handlas just nu under sin långsiktiga trend!")
        with st.expander("Visa varningslista 🚨", expanded=False):
            st.dataframe(auto_warn_df, use_container_width=True)
            st.info("💡 Överväg att sälja av dessa innehav och placera kapitalet i kassa under 'Min Portfölj' fram till nästa ordinarie ombalansering.")

    hist_df = ladda_historik_gspread()
    if len(hist_df) >= 1:
        st.markdown("---")
        st.subheader("📈 Utveckling jämfört med OMXSPI")
        
        if len(hist_df) >= 2:
            tidsperiod = st.radio("⏳ Välj tidsperiod för avkastning:", ["Dagsutveckling", "1 Månad", "I år (YTD)", "1 År", "Total Utveckling"], index=4, horizontal=True)
            st.write("") 
            
            temp_hist = hist_df.copy()
            temp_hist['datum_dt'] = pd.to_datetime(temp_hist['datum'])
            senaste_datum = temp_hist['datum_dt'].iloc[-1]
            senaste_rad = temp_hist.iloc[-1]
            
            if tidsperiod == "Dagsutveckling":
                if len(temp_hist) >= 2: start_row = temp_hist.iloc[-2]
                else: start_row = temp_hist.iloc[0]
            else:
                if tidsperiod == "1 Månad": start_date = senaste_datum - pd.DateOffset(days=30)
                elif tidsperiod == "I år (YTD)": start_date = pd.to_datetime(f"{senaste_datum.year}-01-01")
                elif tidsperiod == "1 År": start_date = senaste_datum - pd.DateOffset(days=365)
                else: start_date = temp_hist['datum_dt'].iloc[0]

                past_data = temp_hist[temp_hist['datum_dt'] <= start_date]
                if past_data.empty: start_row = temp_hist.iloc[0]
                else: start_row = past_data.iloc[-1]

            def calc_ret(nu, da):
                if float(da) > 0: return ((float(nu) / float(da)) - 1) * 100
                return 0.0

            ret_tot = calc_ret(senaste_rad['portfolj_varde'], start_row['portfolj_varde'])
            ret_val = calc_ret(senaste_rad['varde_value'], start_row['varde_value'])
            ret_utd = calc_ret(senaste_rad['varde_utdelning'], start_row['varde_utdelning'])
            ret_mom = calc_ret(senaste_rad['varde_momentum'], start_row['varde_momentum'])
            ret_omx = calc_ret(senaste_rad['omx_index'], start_row['omx_index'])
            
            alfa = ret_tot - ret_omx
            
            # RAD 1
            c1, c2, c3 = st.columns(3)
            c1.metric("💼 Total Portfölj", f"{senaste_rad['portfolj_varde']:,.0f} kr".replace(',', ' '), f"{ret_tot:+.1f} %")
            c2.metric("🏆 Alfa (vs Index)", f"{alfa:+.1f} %-enh.", f"{alfa:+.1f}")
            c3.metric("📊 OMXSPI", f"{senaste_rad['omx_index']:,.0f}".replace(',', ' '), f"{ret_omx:+.1f} %")
            
            st.write("") 
            
            # RAD 2
            c4, c5, c6 = st.columns(3)
            c4.metric("📈 Value", f"{senaste_rad['varde_value']:,.0f} kr".replace(',', ' '), f"{ret_val:+.1f} %")
            c5.metric("💸 Utdelning", f"{senaste_rad['varde_utdelning']:,.0f} kr".replace(',', ' '), f"{ret_utd:+.1f} %")
            c6.metric("⚡ Momentum", f"{senaste_rad['varde_momentum']:,.0f} kr".replace(',', ' '), f"{ret_mom:+.1f} %")
            
            st.markdown("---")
            
            kols = {'varde_value': 'Value (%)', 'varde_utdelning': 'Utdelning (%)', 'varde_momentum': 'Momentum (%)', 'portfolj_varde': 'Total Portfölj (%)', 'omx_index': 'OMXSPI (%)'}
            graf_df = hist_df[['datum']].copy()
            for org_col, ny_col in kols.items():
                start_varden = hist_df[hist_df[org_col] > 0][org_col]
                graf_df[ny_col] = ((hist_df[org_col] / start_varden.iloc[0]) * 100 - 100) if not start_varden.empty else 0.0
            graf_df = graf_df.set_index('datum')
            st.line_chart(graf_df)
            
        st.subheader("Historisk datatabell")
        st.dataframe(hist_df.rename(columns={'datum': 'Datum', 'varde_value': 'Value (SEK)', 'varde_utdelning': 'Utdelning (SEK)', 'varde_momentum': 'Momentum (SEK)', 'portfolj_varde': 'Total Portfölj (SEK)', 'omx_index': 'OMXSPI Index'}), use_container_width=True)
    else: st.warning("Kalkylarket är tomt.")
    
    st.markdown("---")
    
    with st.expander("⚙️ Nödverktyg: Logga värde per kvantstrategi manuellt"):
        st.info("Din dagliga robot gör detta automatiskt kl 18:00 varje kväll, men du kan använda detta formulär om du vill logga data manuellt mitt på dagen.")
        with st.form("logga_varde"):
            valt_datum = st.date_input("Välj datum", datetime.now())
            v_value = st.number_input("Värde: Trending Value (SEK)", min_value=0.0, step=1000.0)
            v_utd = st.number_input("Utdelning: Trendande Utdelning (SEK)", min_value=0.0, step=1000.0)
            v_mom = st.number_input("Momentum: Sammansatt Momentum (SEK)", min_value=0.0, step=1000.0)
            
            if st.form_submit_button("Spara datapunkt"):
                datum_str = valt_datum.strftime("%Y-%m-%d")
                totalt_portfoljvarde = v_value + v_utd + v_mom
                with st.spinner("Hämtar OMXSPI..."):
                    try:
                        omx = yf.Ticker("^OMXSPI")
                        hist = omx.history(start=valt_datum, end=valt_datum + timedelta(days=4))
                        if not hist.empty:
                            omx_stangning = float(hist['Close'].iloc[0])
                            if spara_historik_gspread(datum_str, v_value, v_utd, v_mom, totalt_portfoljvarde, omx_stangning):
                                st.success("Sparat!")
                                st.rerun()
                        else: st.error("Kunde inte hitta indexkurs.")
                    except Exception as e: st.error(f"Fel: {e}")

# --- SIDA 2: PORTFÖLJANALYS & RÅDGIVARE ---
elif meny_val == "🧠 Portföljanalys & Råd":
    st.title("🧠 Portföljanalys & AI-Rådgivare")
    
    ai_datum, ai_text = ladda_ai_analys_gspread()
    with st.container():
        st.subheader("🤖 Månadens Kvant-forskning (AI & Portföljgranskning)")
        if ai_datum:
            st.caption(f"🗓️ {ai_datum}")
            with st.expander("Läs månadens marknadsanalys & rannsakning", expanded=False):
                st.markdown(ai_text)
        else:
            st.info(ai_text)
            
    st.markdown("---")

    # === NY SEKTION: MATEMATISK RISKANALYS MED PEDAGOGISK TEXT ===
    st.subheader("🛡️ Avancerad Riskanalys & Nyckeltal")
    
    hist_df = ladda_historik_gspread()
    if len(hist_df) >= 5:
        with st.expander("🔗 Strategiernas Inbördes Korrelation (Samsvar)", expanded=True):
            st.markdown("""
            **💡 Enkel förklaring:** Tanken med att ha tre olika strategier är att de ska fungera som krockkuddar för varandra. Om börsen straffar *Value-aktier*, vill vi att *Momentum-aktierna* står emot fallet.
            * **Nära 1.0:** Strategierna beter sig som tvillingar. Går den ena ner, dras den andra med (Dåligt skydd).
            * **Under 0.7:** Strategierna går sin egen väg och balanserar upp varandra på ett bra sätt (Bra skydd!).
            """)
            try:
                corr_df = hist_df[['varde_value', 'varde_utdelning', 'varde_momentum']].pct_change().corr()
                corr_df.columns = ['Value (Värde)', 'Utdelning', 'Momentum']
                corr_df.index = ['Value (Värde)', 'Utdelning', 'Momentum']
                st.dataframe(corr_df.style.background_gradient(cmap='coolwarm', axis=None).format("{:.2f}"), use_container_width=True)
            except:
                st.warning("Kunde inte beräkna korrelation. Kräver mer historisk data i arket.")

    st.markdown("""
    **💡 Vad betyder riskmåtten för aktierna nedan?**
    * 📉 **Årlig Volatilitet:** Hur "stökig" är aktien? Hög procent (%) betyder att aktiens pris åker en vild berg-och-dalbana. Låg procent betyder en lugn och stabil tågresa.
    * 🏆 **Sharpekvot:** Är vinsten värd risken (magontet)? 
        * **Under 1.0:** Nja, du tar mycket risk för relativt lite vinst.
        * **Över 1.0:** Bra! Du får en fin vinst i förhållande till risken.
        * **Över 2.0:** Exceptionellt! Hög vinst med väldigt lite dramatik.
    """)
    if st.button("📊 Beräkna risknyckeltal för innehav", type="secondary"):
        with st.spinner("Hämtar historisk data och beräknar riskmått..."):
            risk_data = []
            for s in strategier:
                df = st.session_state[f'bef_portfolj_{s}']
                for _, row in df.iterrows():
                    t = str(row['Ticker']).upper().strip()
                    if t and t != 'KASSA':
                        yf_ticker = t.replace(" ", "-") if "." in t.replace(" ", "-") else f"{t.replace(' ', '-')}.ST"
                        try:
                            aktie = yf.Ticker(yf_ticker)
                            hist = aktie.history(period="1y").dropna(subset=['Close'])
                            if len(hist) > 30:
                                returns = hist['Close'].pct_change().dropna()
                                vol = returns.std() * np.sqrt(252) * 100 
                                ann_ret = (hist['Close'].iloc[-1] / hist['Close'].iloc[0] - 1) * 100
                                sharpe = (ann_ret - 3.0) / vol if vol > 0 else 0
                                risk_data.append({
                                    "Strategi": s,
                                    "Aktie": row['Bolagsnamn'],
                                    "Ticker": t,
                                    "Årlig Volatilitet": f"{vol:.1f} %",
                                    "1-Års Avkastning": f"{ann_ret:+.1f} %",
                                    "Sharpekvot (Rf=3%)": round(sharpe, 2)
                                })
                        except: pass
            if risk_data:
                st.dataframe(pd.DataFrame(risk_data).sort_values(by="Sharpekvot (Rf=3%)", ascending=False).reset_index(drop=True), use_container_width=True)
            else:
                st.warning("Hittade inga aktiva innehav att analysera.")

    st.markdown("---")
    
    st.subheader("🚨 Trendbevakning (Manuell MA200-scanning)")
    st.write("Klicka nedan för att göra en direkt-scanning i realtid av dina innehav mot MA200.")
    
    if st.button("Kör manuell scanning nu", type="primary"):
        with st.spinner("Hämtar historisk data och analyserar MA200 för hela portföljen..."):
            varningar = []
            for s in strategier:
                df = st.session_state[f'bef_portfolj_{s}']
                for _, row in df.iterrows():
                    t = str(row['Ticker']).upper().strip()
                    if t and t != 'KASSA':
                        yf_ticker = t.replace(" ", "-") if "." in t.replace(" ", "-") else f"{t.replace(' ', '-')}.ST"
                        try:
                            aktie = yf.Ticker(yf_ticker)
                            hist = aktie.history(period="1y").dropna(subset=['Close'])
                            if len(hist) > 150:
                                ma200 = hist['Close'].tail(200).mean()
                                senaste_kurs = hist['Close'].iloc[-1]
                                if senaste_kurs < ma200:
                                    varningar.append({
                                        "Strategi": s, 
                                        "Aktie": row['Bolagsnamn'], 
                                        "Ticker": t, 
                                        "Kurs": senaste_kurs, 
                                        "MA200": ma200, 
                                        "Avvikelse": ((senaste_kurs/ma200)-1)*100
                                    })
                        except: pass
            if varningar:
                st.error(f"⚠️ Hittade {len(varningar)} aktier under sitt MA200 just nu.")
                df_v = pd.DataFrame(varningar)
                df_v['Kurs'] = df_v['Kurs'].apply(lambda x: f"{x:.2f} kr")
                df_v['MA200'] = df_v['MA200'].apply(lambda x: f"{x:.2f} kr")
                df_v['Avvikelse'] = df_v['Avvikelse'].apply(lambda x: f"{x:.1f} %")
                st.dataframe(df_v, use_container_width=True)
            else:
                st.success("✅ Alla dina aktier handlas över sitt MA200 för tillfället!")
    
    st.markdown("---")

    varden = {}
    total_nu = 0.0
    har_nagra_aktier = False
    
    for s in strategier:
        df = st.session_state[f'bef_portfolj_{s}']
        if not df.empty: har_nagra_aktier = True
        summa = (df['Antal'] * df['Kurs']).sum()
        varden[s] = float(summa)
        total_nu += float(summa)

    if total_nu > 0:
        manad_nu = datetime.now().month
        mal_vikter = hamta_malviktning(manad_nu)
        
        st.subheader("⚖️ Din nuvarande portföljbalans")
        balans_data = []
        for s in strategier:
            nu_vikt = varden[s] / total_nu
            diff_vikt = nu_vikt - mal_vikter[s]
            status = "🟢 Perfekt" if abs(diff_vikt) <= 0.05 else ("🔴 För tung" if diff_vikt > 0 else "🟡 För lätt")
            balans_data.append({
                "Strategi": s,
                "Nuvarande Värde": f"{varden[s]:,.0f} kr".replace(',', ' '),
                "Din Vikt": f"{nu_vikt*100:.1f} %",
                "Målvikt (Denna månad)": f"{mal_vikter[s]*100:.1f} %",
                "Avvikelse": f"{diff_vikt*100:+.1f} %",
                "Status": status
            })
        st.dataframe(pd.DataFrame(balans_data), use_container_width=True)

        st.subheader("💡 Förslag på omviktning")
        for bd in balans_data:
            diff = float(bd['Avvikelse'].replace('%', '').strip())
            kr_diff = (total_nu * mal_vikter[bd['Strategi']]) - varden[bd['Strategi']]
            if diff > 5: st.warning(f"📉 **Sänk {bd['Strategi']}:** Du har en övervikt. Överväg att skala ner med ca **{abs(kr_diff):,.0f} kr** vid nästa ombalansering.")
            elif diff < -5: st.info(f"📈 **Öka {bd['Strategi']}:** Du är underviktad gentemot målvikt. Överväg att tillföra ca **{kr_diff:,.0f} kr**.")
        
        if len(hist_df) >= 2:
            st.markdown("---")
            st.subheader("🏆 Din Prestation (Alfa - Total Utveckling)")
            port_start = hist_df['portfolj_varde'].iloc[0]
            omx_start = hist_df['omx_index'].iloc[0]
            port_utv = (hist_df['portfolj_varde'].iloc[-1] / port_start) * 100 - 100 if port_start > 0 else 0
            omx_utv = (hist_df['omx_index'].iloc[-1] / omx_start) * 100 - 100 if omx_start > 0 else 0
            alfa = port_utv - omx_utv
            
            c1, c2 = st.columns(2)
            c1.metric("Din Totala Utveckling vs Index (Alfa)", f"{alfa:+.2f} procentenheter")
            if alfa > 0: c2.success("Fantastiskt jobbat! Din Kvant-maskin slår marknaden totalt sett.")
            else: c2.warning("Du underpresterar totalt sett mot index. Kvantstrategier kräver tålamod.")
    elif har_nagra_aktier:
        st.warning("⚠️ **Aktier hittades, men det totala värdet är 0 kr!** Hämta livekurser för att fylla i priser.")

# --- SIDA 3: MIN PORTFÖLJ ---
elif meny_val == "💼 Min Portfölj":
    st.title("💼 Mina Befintliga Portföljer")
    vald = st.selectbox("Välj portfölj att hantera:", strategier, index=strategier.index(st.session_state['aktiv_strategi']))
    st.session_state['aktiv_strategi'] = vald 
    st.dataframe(st.session_state[f'bef_portfolj_{vald}'], use_container_width=True)
    
    st.markdown("### 🛠 Hantera innehav")
    c1, c2, c3 = st.columns(3)
    
    with c1:
        with st.expander("➕ Lägg till/Ändra aktie"):
            with st.form("lagg_till_form"):
                col_namn, col_tick = st.text_input("Bolagsnamn"), st.text_input("Ticker")
                col_antal, col_kurs = st.number_input("Antal", min_value=0, step=1), st.number_input("Kurs", min_value=0.0, step=0.1)
                if st.form_submit_button("Spara i tabell"):
                    df = st.session_state[f'bef_portfolj_{vald}'].copy()
                    new_row = {"Bolagsnamn": col_namn.strip(), "Ticker": col_tick.upper().strip(), "Antal": int(col_antal), "Kurs": float(col_kurs)}
                    if col_tick.upper().strip() in df['Ticker'].values: 
                        df.loc[df['Ticker'] == col_tick.upper().strip(), ["Bolagsnamn", "Ticker", "Antal", "Kurs"]] = [new_row['Bolagsnamn'], new_row['Ticker'], new_row['Antal'], new_row['Kurs']]
                    else: df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                    st.session_state[f'bef_portfolj_{vald}'] = df
                    st.rerun()
                    
    with c2:
        with st.expander("❌ Ta bort aktie"):
            df_curr = st.session_state[f'bef_portfolj_{vald}']
            aktier_lista = df_curr[df_curr['Ticker'] != 'KASSA']['Ticker'].tolist()
            if aktier_lista:
                vald_att_ta_bort = st.selectbox("Välj aktie att sälja/ta bort:", aktier_lista)
                if st.button("Radera från tabell", type="primary"):
                    st.session_state[f'bef_portfolj_{vald}'] = df_curr[df_curr['Ticker'] != vald_att_ta_bort].reset_index(drop=True)
                    st.success(f"{vald_att_ta_bort} har raderats!")
                    st.rerun()
            else: st.write("Inga aktier att ta bort.")
                
    with c3:
        with st.expander("💵 Hantera Kassasaldo"):
            df_curr = st.session_state[f'bef_portfolj_{vald}']
            nuv_kassa_rad = df_curr[df_curr['Ticker'] == 'KASSA']
            nuv_kassa = float(nuv_kassa_rad['Kurs'].iloc[0]) if not nuv_kassa_rad.empty else 0.0
            ny_kassa = st.number_input("Aktuellt Kassasaldo (SEK)", min_value=0.0, value=float(nuv_kassa), step=1000.0)
            if st.button("Uppdatera Kassa"):
                df_clean = df_curr[df_curr['Ticker'] != 'KASSA'].copy()
                if ny_kassa > 0:
                    ny_rad = pd.DataFrame([{"Bolagsnamn": "Ledig Kassa", "Ticker": "KASSA", "Antal": 1, "Kurs": ny_kassa}])
                    df_clean = pd.concat([df_clean, ny_rad], ignore_index=True)
                st.session_state[f'bef_portfolj_{vald}'] = df_clean
                st.success(f"Kassan uppdaterad!")
                st.rerun()
                
    st.markdown("---")
    b1, b2, b3 = st.columns(3)
    with b1:
        if st.button("🌐 Hämta Live-kurser (Yahoo)", type="primary"):
            with st.spinner("Hämtar från nätet..."):
                temp_bef = st.session_state[f'bef_portfolj_{vald}'].copy()
                for idx, row in temp_bef.iterrows():
                    t = str(row['Ticker']).upper().replace(" SEK", "").strip()
                    if not t or t == 'KASSA': continue
                    t = t.replace(" ", "-")
                    yf_ticker = t if "." in t else f"{t}.ST"
                    try:
                        aktie = yf.Ticker(yf_ticker)
                        hist = aktie.history(period="1mo").dropna(subset=['Close'])
                        if not hist.empty: 
                            ny_kurs = round(float(hist['Close'].iloc[-1]), 2)
                            if ny_kurs > 0 and not pd.isna(ny_kurs):
                                temp_bef.at[idx, 'Kurs'] = ny_kurs
                    except: pass
                st.session_state[f'bef_portfolj_{vald}'] = temp_bef
                st.success("Live-kurser hämtade!")
                st.rerun()
    with b2:
        if uppladdad_fil and st.button(f"🔄 Hämta från Börsdata-fil"):
            df_bd, k_namn, k_tick, k_kurs = ladda_och_tvatta_basdata(uppladdad_fil)
            kurs_dict = dict(zip(df_bd[k_tick].astype(str).str.upper().str.strip(), df_bd[k_kurs]))
            temp_bef = st.session_state[f'bef_portfolj_{vald}'].copy()
            for idx, row in temp_bef.iterrows():
                t = str(row['Ticker']).upper().strip()
                if t in kurs_dict and t != 'KASSA': temp_bef.at[idx, 'Kurs'] = float(kurs_dict[t])
            st.session_state[f'bef_portfolj_{vald}'] = temp_bef
            st.success("Kurserna har uppdaterats från fil!")
            st.rerun()
    with b3:
        if st.button(f"💾 Spara {vald}-portföljen", use_container_width=True):
            if spara_innehav_gspread(st.session_state[f'bef_portfolj_{vald}'], vald): 
                st.success("Sparat i molnet!")

# --- SIDA 4: SÄSONGSMÖNSTER & VIKTNING ---
elif meny_val == "📅 Säsongsmönster & Viktning":
    st.title("📅 Säsongsmönster & Dynamisk Viktning")
    
    nuvarande_manad = datetime.now().month
    manader = ["Januari", "Februari", "Mars", "April", "Maj", "Juni", "Juli", "Augusti", "September", "Oktober", "November", "December"]
    manad_namn = manader[nuvarande_manad - 1]

    st.subheader(f"📍 Analys för {manad_namn}")
    mal_vikter = hamta_malviktning(nuvarande_manad)
    
    varden = {}
    total_nu = 0.0
    
    for s in strategier:
        df = st.session_state[f'bef_portfolj_{s}']
        summa = (df['Antal'] * df['Kurs']).sum()
        varden[s] = float(summa)
        total_nu += float(summa)
        
    nu_vikter = {s: (varden[s]/total_nu if total_nu > 0 else 0.0) for s in strategier}

    st.write("📊 **Jämförelse: Din Nuvarande Portfölj vs. Rekommenderad Målvikt**")
    if total_nu > 0:
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f"**📈 Value:** Nuv: **{nu_vikter['Value']*100:.1f}%** ➔ Mål: **{mal_vikter['Value']*100:.0f}%**")
            st.progress(min(float(nu_vikter['Value']), 1.0), text="Din reella vikt")
            st.progress(float(mal_vikter['Value']), text="Optimal målvikt")
        with c2:
            st.markdown(f"**💸 Utdelning:** Nuv: **{nu_vikter['Utdelning']*100:.1f}%** ➔ Mål: **{mal_vikter['Utdelning']*100:.0f}%**")
            st.progress(min(float(nu_vikter['Utdelning']), 1.0), text="Din reella vikt")
            st.progress(float(mal_vikter['Utdelning']), text="Optimal målvikt")
        with c3:
            st.markdown(f"**⚡ Momentum:** Nuv: **{nu_vikter['Momentum']*100:.1f}%** ➔ Mål: **{mal_vikter['Momentum']*100:.0f}%**")
            st.progress(min(float(nu_vikter['Momentum']), 1.0), text="Din reella vikt")
            st.progress(float(mal_vikter['Momentum']), text="Optimal målvikt")

    st.markdown("---")
    if nuvarande_manad in [11, 12, 1]:
        st.success("🟢 **Fokus: Värdestrategi (Value)**\n\nDu befinner dig i bästa möjliga miljö för Värdebolag. Nedpressade bolag säljs av fondförvaltare i skatteplaneringssyfte innan nyår. I januari köps dessa tillbaka vilket skapar kraftiga studsar uppåt.")
    elif nuvarande_manad in [2, 3, 4]:
        st.success("🟢 **Fokus: Utdelning & Momentum**\n\nDetta är fönstret för utdelningsjägare! Kapital roterar in i högutdelare fram till X-dagen. Samtidigt har Momentum återhämtat sig från januarikraschen.")
    elif nuvarande_manad in [5, 6, 7, 8]:
        st.info("🟡 **Fokus: Marknadens Vakuum (Defensivt)**\n\n'Sell in May and go away' existerar av en anledning. Sommarmånaderna lider ofta av låg likviditet.")
    elif nuvarande_manad in [9, 10]:
        st.success("🟢 **Fokus: Momentum**\n\nLikviditeten är tillbaka. Rapporterna i slutet av sommaren har etablerat nya starka trender. Rid på vinnarna!")

# --- SIDA 5: OM STRATEGIERNA ---
elif meny_val == "📖 Om Kvantstrategierna":
    st.title("📖 Dokumentation av Kvantstrategierna")
    st.markdown("""
    *Gemensamt grundkrav för alla strategier:*
    * **Storlek:** Börsvärde >= 500 MSEK.
    * **Listor:** Endast Large, Mid och Small Cap.
    """)
    st.header("📈 1. Trending Value")
    st.markdown("""
    1. Koden rankar alla godkända bolag från 1 (billigast) och uppåt på följande nyckeltal: **P/E, P/S, P/B, P/FCF, och EV/EBITDA**.
    2. Saknas data straffas bolaget med ett högt fiktivt värde (5000) för att hamna längst ner i rankingen.
    3. De 40 absolut billigaste bolagen plockas ut.
    4. De 40 billigaste bolagen sorteras så och de 10 med bäst **Sammansatt Momentum** (snitt av 3m, 6m, 12m) väljs ut.
    """)
    st.header("💸 2. Trendande Utdelning")
    st.markdown("""
    1. Koden plockar ut de 40 bolagen med absolut högst direktavkastning i %.
    2. Högutdelarna sorteras efter Sammansatt Momentum. De 10 med starkast positiv trend blir din målkorg.
    """)
    st.header("⚡ 3. Sammansatt Momentum")
    st.markdown("""
    1. Koden beräknar **Sammansatt Momentum** = (Utv 3m + Utv 6m + Utv 12m) / 3.
    2. Hela börsens bolag sorteras efter detta sammansatta värde och de 10 bästa väljs rakt av.
    """)

# --- SIDA 6, 7, 8: STRATEGIKALKYLATORERNA ---
elif "Strategi" in meny_val:
    st.title(meny_val)
    strat_typ = "Value" if "Value" in meny_val else "Utdelning" if "Utdelning" in meny_val else "Momentum"
    
    if uppladdad_fil:
        with st.spinner("Beräknar strategi..."):
            df, k_namn, k_tick, k_kurs = ladda_och_tvatta_basdata(uppladdad_fil)
            
            if strat_typ == "Value":
                v_kols = ['P/E - Senaste', 'P/S - Senaste', 'P/B - Senaste', 'P/FCF - Senaste', 'EV/EBITDA - Senaste']
                for k in v_kols:
                    if k in df.columns: df[k] = pd.to_numeric(df[k], errors='coerce').fillna(5000)
                    else: df[k] = 5000
                    df[f'Rank_{k}'] = df[k].rank(ascending=True, method='min')
                df['Total_Rank'] = df[[f'Rank_{k}' for k in v_kols]].sum(axis=1) / len(v_kols)
                k_3m, k_6m, k_12m = next((c for c in df.columns if '3m' in c.lower()), df.columns[0]), next((c for c in df.columns if '6m' in c.lower()), df.columns[0]), next((c for c in df.columns if '1år' in c.lower() or '12m' in c.lower()), df.columns[0])
                df['Momentum'] = (pd.to_numeric(df[k_3m], errors='coerce').fillna(0) + pd.to_numeric(df[k_6m], errors='coerce').fillna(0) + pd.to_numeric(df[k_12m], errors='coerce').fillna(0)) / 3
                topp = df.nsmallest(40, 'Total_Rank').sort_values(by='Momentum', ascending=False).head(10)
                
            elif strat_typ == "Utdelning":
                k_utd = 'Direktav. - Senaste'
                df[k_utd] = pd.to_numeric(df[k_utd], errors='coerce').fillna(0) if k_utd in df.columns else 0
                k_3m, k_6m, k_12m = next((c for c in df.columns if '3m' in c.lower()), df.columns[0]), next((c for c in df.columns if '6m' in c.lower()), df.columns[0]), next((c for c in df.columns if '1år' in c.lower() or '12m' in c.lower()), df.columns[0])
                df['Momentum'] = (pd.to_numeric(df[k_3m], errors='coerce').fillna(0) + pd.to_numeric(df[k_6m], errors='coerce').fillna(0) + pd.to_numeric(df[k_12m], errors='coerce').fillna(0)) / 3
                topp = df.nlargest(40, k_utd).sort_values(by='Momentum', ascending=False).head(10)
                
            elif strat_typ == "Momentum":
                k_3m, k_6m, k_12m = next((c for c in df.columns if '3m' in c.lower()), df.columns[0]), next((c for c in df.columns if '6m' in c.lower()), df.columns[0]), next((c for c in df.columns if '1år' in c.lower() or '12m' in c.lower()), df.columns[0])
                df['Momentum'] = (pd.to_numeric(df[k_3m], errors='coerce').fillna(0) + pd.to_numeric(df[k_6m], errors='coerce').fillna(0) + pd.to_numeric(df[k_12m], errors='coerce').fillna(0)) / 3
                topp = df.sort_values(by='Momentum', ascending=False).head(10)

            st.subheader("🚀 Topp 10 Köpkandidater")
            st.dataframe(topp[[k_namn, k_tick, k_kurs, 'Momentum']].reset_index(drop=True), use_container_width=True)
            
            if st.button("⚡ Skicka Topp 10 till Ombalansering"):
                st.session_state['mal_portfolj'] = topp[[k_namn, k_tick, k_kurs]].rename(columns={k_namn:"Bolagsnamn", k_tick:"Ticker", k_kurs:"Kurs"}).reset_index(drop=True)
                st.session_state['aktiv_strategi'] = strat_typ
                st.session_state['ombalansering_beraknad'] = False
                st.success("Målaktier sparade! Gå till Ombalanserings-sidan.")
    else: st.warning("👈 Vänligen ladda upp din Börsdata-export i sidomenyn.")

# --- SIDA 9: OMBALANSERING ---
elif meny_val == "⚖️ Ombalansering":
    st.title("⚖️ Portföljombalansering")
    vald_strat = st.selectbox("Välj portfölj att arbeta med:", strategier, index=strategier.index(st.session_state['aktiv_strategi']))
    st.session_state['aktiv_strategi'] = vald_strat
    
    st.info(f"📍 Aktuellt läge: Jämför befintlig **{vald_strat}**-portfölj med dina inskickade målaktier.")
    extra_kassa = st.number_input("Nytt externt sparande att tillföra (SEK)", min_value=0, value=10000, step=1000)
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("1. Din Befintliga Portfölj")
        st.dataframe(st.session_state[f'bef_portfolj_{vald_strat}'], use_container_width=True)
    with col2:
        st.subheader("2. Dina Nya Målaktier (Topp 10)")
        st.dataframe(st.session_state['mal_portfolj'], use_container_width=True)
        
    if st.button("⚡ Beräkna ombalansering", type="primary"):
        df_bef = pd.DataFrame(st.session_state[f'bef_portfolj_{vald_strat}'])
        df_mal = pd.DataFrame(st.session_state['mal_portfolj'])
        
        nuvarande_aktie_varde = (df_bef['Antal'] * df_bef['Kurs']).sum() if not df_bef.empty else 0
        totalt_portfolj_varde = nuvarande_aktie_varde + extra_kassa
        antal_malbolag = len(df_mal)
        
        if antal_malbolag > 0:
            mal_varde_per_aktie = totalt_portfolj_varde / antal_malbolag
            st.session_state['tot_v'] = totalt_portfolj_varde
            st.session_state['mal_v'] = mal_varde_per_aktie
            
            ordrar, ny_p_rader = [], []
            for _, r in df_bef.iterrows():
                if r['Ticker'] == 'KASSA': continue
                if r['Ticker'] not in df_mal['Ticker'].values:
                    ordrar.append({"Bolagsnamn": r['Bolagsnamn'], "Ticker": r['Ticker'], "Handling": "🔴 SÄLJ ALLT", "Antal aktier": int(r['Antal']), "Kurs": r['Kurs']})
            for _, r in df_mal.iterrows():
                t, k, n = r['Ticker'], float(r['Kurs']), r['Bolagsnamn']
                m_antal = int(mal_varde_per_aktie // k) if k > 0 else 0
                if m_antal > 0: ny_p_rader.append({"Bolagsnamn": n, "Ticker": t, "Antal": m_antal, "Kurs": k})
                match = df_bef[df_bef['Ticker'] == t]
                if not match.empty:
                    nuv_a = int(match['Antal'].iloc[0])
                    diff = m_antal - nuv_a
                    if diff > 0: ordrar.append({"Bolagsnamn": n, "Ticker": t, "Handling": "🔵 KÖP MER", "Antal aktier": int(diff), "Kurs": k})
                    elif diff < 0: ordrar.append({"Bolagsnamn": n, "Ticker": t, "Handling": "   SÄLJ AV", "Antal aktier": int(abs(diff)), "Kurs": k})
                else: ordrar.append({"Bolagsnamn": n, "Ticker": t, "Handling": "🟢 KÖP NY", "Antal aktier": int(m_antal), "Kurs": k})
                    
            st.session_state['ordrar_res'] = pd.DataFrame(ordrar)
            st.session_state['ny_p_res'] = pd.DataFrame(ny_p_rader)
            st.session_state['ombalansering_beraknad'] = True
        else: st.error("Hittade inga målaktier.")

    if st.session_state['ombalansering_beraknad']:
        st.markdown("---")
        st.metric("Totalt Portföljvärde (inkl. all kassa)", f"{st.session_state['tot_v']:,.0f} kr")
        st.metric("Målvärde per aktie (Lika vikt)", f"{st.session_state['mal_v']:,.0f} kr")
        st.subheader("🛒 Köp- och säljinstruktioner:")
        st.dataframe(st.session_state['ordrar_res'], use_container_width=True)
        if st.button(f"💾 Verkställ affärer & spara som mitt nya {vald_strat}-innehav"):
            with st.spinner("Sparar till Google Sheets..."):
                if spara_innehav_gspread(st.session_state['ny_p_res'], vald_strat):
                    st.session_state[f'bef_portfolj_{vald_strat}'] = st.session_state['ny_p_res']
                    st.session_state['ombalansering_beraknad'] = False
                    st.success(f"🎉 Klart! Din nya {vald_strat}-portfölj har sparats!")
                    st.rerun()
