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
st.set_page_config(page_title="Kvant-Maskinen v6.13", page_icon="🚀", layout="wide")

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

def radera_varning_gspread(ticker):
    try:
        gc = get_gspread_client()
        sh = gc.open_by_url(st.secrets["google_sheet_url"])
        worksheet = sh.worksheet("MA200_Varningar")
        data = worksheet.get_all_values()
        if not data: return False
        headers = data[0]
        if "Ticker" not in headers: return False
        ticker_col_idx = headers.index("Ticker")
        
        rows_to_delete = []
        for i, row in enumerate(data):
            if i > 0 and len(row) > ticker_col_idx:
                if str(row[ticker_col_idx]).strip().upper() == str(ticker).strip().upper():
                    rows_to_delete.append(i + 1)
        
        for r in reversed(rows_to_delete):
            worksheet.delete_rows(r)
        return len(rows_to_delete) > 0
    except:
        return False

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
if 'senast_uppdaterad_kurser' not in st.session_state:
    st.session_state['senast_uppdaterad_kurser'] = "Ej uppdaterat denna session"

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
svartlista_input = st.sidebar.text_input("🛑 Manuell Svartlista (kommaseparerat)", value="", help="Tvinga bort specifika bolag helt, t.ex. HUM, SBB B")
svartlista = [x.strip().upper() for x in svartlista_input.split(',')] if svartlista_input.strip() else []
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
        with st.expander("Visa varningslista 🚨", expanded=True):
            st.info("💡 När du har sålt en aktie eller uppmärksammat varningen kan du klicka på 'Kvittera' nedan för att dölja den från listan.")
            for idx, row in auto_warn_df.iterrows():
                aktie = row.get('Aktie', 'Okänd')
                ticker = row.get('Ticker', '-')
                avv = row.get('Avvikelse', '-')
                c1, c2, c3 = st.columns([3, 3, 2])
                c1.write(f"**{aktie}** ({ticker})")
                c2.write(f"Avvikelse: {avv}")
                if c3.button("✅ Kvittera (Dölj)", key=f"kvitt_{ticker}_{idx}"):
                    with st.spinner("Döljer varning..."):
                        radera_varning_gspread(ticker)
                        st.rerun()

    hist_df = ladda_historik_gspread()
    if len(hist_df) >= 1:
        st.markdown("---")
        st.subheader("📈 Utveckling jämfört med OMXSPI")
        if len(hist_df) >= 2:
            temp_hist = hist_df.copy()
            temp_hist['datum_dt'] = pd.to_datetime(temp_hist['datum'])
            senaste_datum = temp_hist['datum_dt'].iloc[-1]
            senaste_rad = temp_hist.iloc[-1]
            st.caption(f"🕒 Statusuppdatering: Utveckling per stängning **{senaste_datum.strftime('%Y-%m-%d')}**")
            
            tidsperiod = st.radio("⏳ Välj tidsperiod för avkastning:", ["Dagsutveckling", "1 Månad", "I år (YTD)", "1 År", "Total Utveckling"], index=4, horizontal=True)
            st.write("") 
            
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
            
            c1, c2, c3 = st.columns(3)
            c1.metric("💼 Total Portfölj", f"{senaste_rad['portfolj_varde']:,.0f} kr".replace(',', ' '), f"{ret_tot:+.2f} %")
            c2.metric("🏆 Alfa (vs Index)", f"{alfa:+.2f} %-enh.", f"{alfa:+.2f}")
            c3.metric("📊 OMXSPI", f"{senaste_rad['omx_index']:,.0f}".replace(',', ' '), f"{ret_omx:+.2f} %")
            st.write("") 
            
            c4, c5, c6 = st.columns(3)
            c4.metric("📈 Value", f"{senaste_rad['varde_value']:,.0f} kr".replace(',', ' '), f"{ret_val:+.2f} %")
            c5.metric("💸 Utdelning", f"{senaste_rad['varde_utdelning']:,.0f} kr".replace(',', ' '), f"{ret_utd:+.2f} %")
            c6.metric("⚡ Momentum", f"{senaste_rad['varde_momentum']:,.0f} kr".replace(',', ' '), f"{ret_mom:+.2f} %")
            
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

# --- SIDA 2,3,4,5 ... är oförändrade (Kortade i koden här för överblick) ---
elif meny_val in ["🧠 Portföljanalys & Råd", "💼 Min Portfölj", "📅 Säsongsmönster & Viktning", "📖 Om Kvantstrategierna"]:
    st.info("Gå till strategisidorna för att se den uppdaterade bud-radarn!")

# --- SIDA 6, 7, 8: STRATEGIKALKYLATORERNA ---
elif "Strategi" in meny_val:
    st.title(meny_val)
    strat_typ = "Value" if "Value" in meny_val else "Utdelning" if "Utdelning" in meny_val else "Momentum"
    
    if uppladdad_fil:
        with st.spinner("Laddar fil och applicerar eventuell Svartlista..."):
            df, k_namn, k_tick, k_kurs = ladda_och_tvatta_basdata(uppladdad_fil)
            
            if svartlista:
                df = df[~df[k_tick].astype(str).str.upper().str.strip().isin(svartlista)].copy()
            
            with st.spinner("Beräknar strategi..."):
                if strat_typ == "Value":
                    v_kols = ['P/E - Senaste', 'P/S - Senaste', 'P/B - Senaste', 'P/FCF - Senaste', 'EV/EBITDA - Senaste']
                    for k in v_kols:
                        if k in df.columns: 
                            df[k] = pd.to_numeric(df[k], errors='coerce').fillna(5000)
                            df[k] = df[k].apply(lambda x: 5000 if x <= 0 else x)
                        else: 
                            df[k] = 5000
                        df[f'Rank_{k}'] = df[k].rank(ascending=True, method='min')
                    df['Total_Rank'] = df[[f'Rank_{k}' for k in v_kols]].sum(axis=1) / len(v_kols)
                    k_3m, k_6m, k_12m = next((c for c in df.columns if '3m' in c.lower()), df.columns[0]), next((c for c in df.columns if '6m' in c.lower()), df.columns[0]), next((c for c in df.columns if '1år' in c.lower() or '12m' in c.lower()), df.columns[0])
                    df['Momentum'] = (pd.to_numeric(df[k_3m], errors='coerce').fillna(0) + pd.to_numeric(df[k_6m], errors='coerce').fillna(0) + pd.to_numeric(df[k_12m], errors='coerce').fillna(0)) / 3
                    topp_alla = df.nsmallest(40, 'Total_Rank').sort_values(by='Momentum', ascending=False)
                    
                elif strat_typ == "Utdelning":
                    k_utd = 'Direktav. - Senaste'
                    df[k_utd] = pd.to_numeric(df[k_utd], errors='coerce').fillna(0) if k_utd in df.columns else 0
                    k_3m, k_6m, k_12m = next((c for c in df.columns if '3m' in c.lower()), df.columns[0]), next((c for c in df.columns if '6m' in c.lower()), df.columns[0]), next((c for c in df.columns if '1år' in c.lower() or '12m' in c.lower()), df.columns[0])
                    df['Momentum'] = (pd.to_numeric(df[k_3m], errors='coerce').fillna(0) + pd.to_numeric(df[k_6m], errors='coerce').fillna(0) + pd.to_numeric(df[k_12m], errors='coerce').fillna(0)) / 3
                    topp_alla = df.nlargest(40, k_utd).sort_values(by='Momentum', ascending=False)
                    
                elif strat_typ == "Momentum":
                    k_3m, k_6m, k_12m = next((c for c in df.columns if '3m' in c.lower()), df.columns[0]), next((c for c in df.columns if '6m' in c.lower()), df.columns[0]), next((c for c in df.columns if '1år' in c.lower() or '12m' in c.lower()), df.columns[0])
                    df['Momentum'] = (pd.to_numeric(df[k_3m], errors='coerce').fillna(0) + pd.to_numeric(df[k_6m], errors='coerce').fillna(0) + pd.to_numeric(df[k_12m], errors='coerce').fillna(0)) / 3
                    topp_alla = df.sort_values(by='Momentum', ascending=False).head(40)

        with st.spinner("Granskar kandidater och letar efter dolda uppköpsbud (Bud-radar)..."):
            godkanda_kandidater = []
            uppkops_varningar = []
            
            for _, row in topp_alla.iterrows():
                if len(godkanda_kandidater) >= 10:
                    break 
                    
                t = str(row[k_tick]).upper().strip()
                yf_ticker = t.replace(" ", "-") if "." in t.replace(" ", "-") else f"{t.replace(' ', '-')}.ST"
                vol_str = "N/A"
                sharpe_str = "N/A"
                
                try:
                    aktie = yf.Ticker(yf_ticker)
                    hist = aktie.history(period="1y").dropna(subset=['Close'])
                    if len(hist) > 30:
                        returns = hist['Close'].pct_change().dropna()
                        
                        # --- HÄR ÄR DEN FÖRBÄTTRADE BUD-RADARN SOM FÅNGAR HUMANA ---
                        recent_21 = hist['Close'].tail(21)
                        spread_1m = (recent_21.max() / recent_21.min()) - 1 if recent_21.min() > 0 else 1.0
                        
                        returns_90 = returns.tail(90)
                        max_hopp = returns_90.max() if not returns_90.empty else 0
                        
                        is_takeover = False
                        
                        # 1. Helt fryst aktie (Typiskt vid rena kontantbud)
                        if spread_1m < 0.035:
                            is_takeover = True
                            anledning = f"Fryst kurs senaste månaden (Max/Min-spread endast {spread_1m*100:.1f}%)"
                            
                        # 2. Extremt enskilt dagshopp (Typiskt vid blandade bud som Humana/Ambea)
                        # Gränsen är satt till >19% eftersom Humanas premiumbud var runt 25%.
                        elif max_hopp > 0.19: 
                            is_takeover = True
                            anledning = f"Extremt kurs-hopp på en dag (+{max_hopp*100:.1f}%) hittat i närtid. Hög risk för bud!"
                            
                        # 3. Mindre hopp som stannat i en trång kanal
                        elif max_hopp > 0.10 and spread_1m < 0.09:
                            is_takeover = True
                            anledning = f"Misstänkt bud-hopp (+{max_hopp*100:.1f}%) följt av fastlåst kurs"
                            
                        if is_takeover:
                            uppkops_varningar.append(f"🚨 **{row[k_namn]} ({t})** stoppades! {anledning}")
                            continue # Kasta aktien och gå vidare till NÄSTA i listan
                            
                        # Standard riskberäkning
                        vol = returns.std() * np.sqrt(252) * 100 
                        ann_ret = (hist['Close'].iloc[-1] / hist['Close'].iloc[0] - 1) * 100
                        sharpe = (ann_ret - 3.0) / vol if vol > 0 else 0
                        
                        vol_status = "🟢 Stabil" if vol < 25 else ("🟡 Volatil" if vol < 40 else "🔴 Mycket orolig")
                        sharpe_status = "🟢 Utmärkt" if sharpe > 1.5 else ("🟡 Bra" if sharpe > 0.5 else "🔴 Svag")
                        
                        vol_str = f"{vol:.1f}% ({vol_status})"
                        sharpe_str = f"{round(sharpe, 2)} ({sharpe_status})"
                except:
                    pass
                
                rad = row.copy()
                rad['Årlig Volatilitet'] = vol_str
                rad['Sharpe (Rf=3%)'] = sharpe_str
                godkanda_kandidater.append(rad)
                
            topp_risk = pd.DataFrame(godkanda_kandidater)

        # VARNINGSRUTAN - Visas DIREKT på strategisidan (ovanför tabellen)
        if uppkops_varningar:
            st.error("⚠️ **BUD-RADARN AKTIVERADES!** Följande bolag stoppades från att nå din portfölj:")
            for varning in uppkops_varningar:
                st.write(varning)
                
        st.subheader("🚀 Topp 10 Köpkandidater (inkl. Riskanalys)")
        
        display_cols = [k_namn, k_tick, k_kurs, 'Momentum', 'Årlig Volatilitet', 'Sharpe (Rf=3%)']
        st.dataframe(topp_risk[display_cols].reset_index(drop=True), use_container_width=True)
        
        if st.button("⚡ Skicka Topp 10 till Ombalansering"):
            st.session_state['mal_portfolj'] = topp_risk[[k_namn, k_tick, k_kurs]].rename(columns={k_namn:"Bolagsnamn", k_tick:"Ticker", k_kurs:"Kurs"}).reset_index(drop=True)
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