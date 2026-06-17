import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import json
import gspread
from google.oauth2.service_account import Credentials

# ==========================================
# 1. INSTÄLLNINGAR & GOOGLE CONNECTIONS
# ==========================================
st.set_page_config(page_title="Kvant-Maskinen v3.0", page_icon="🚀", layout="wide")

def get_gspread_client():
    creds_dict = json.loads(st.secrets["google_credentials"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
    return gspread.authorize(creds)

# --- Funktioner för Historik ---
def ladda_historik_gspread():
    try:
        gc = get_gspread_client()
        sh = gc.open_by_url(st.secrets["google_sheet_url"])
        worksheet = sh.worksheet("Historik")
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        if df.empty:
            return pd.DataFrame(columns=['datum', 'portfolj_varde', 'omx_index'])
        df['datum'] = df['datum'].astype(str)
        
        # --- NY STÄDNING FÖR SVENSKA KOMMATECKEN ---
        df['portfolj_varde'] = pd.to_numeric(df['portfolj_varde'].astype(str).str.replace(' ', '').str.replace(',', '.'), errors='coerce').fillna(0)
        df['omx_index'] = pd.to_numeric(df['omx_index'].astype(str).str.replace(' ', '').str.replace(',', '.'), errors='coerce').fillna(0)
        # ------------------------------------------
        
        return df.sort_values('datum').reset_index(drop=True)
    except:
        return pd.DataFrame(columns=['datum', 'portfolj_varde', 'omx_index'])

def spara_historik_gspread(datum_str, portfolj_kronor, omx_stangning):
    try:
        gc = get_gspread_client()
        sh = gc.open_by_url(st.secrets["google_sheet_url"])
        worksheet = sh.worksheet("Historik")
        data = worksheet.get_all_values()
        if not data:
            worksheet.append_row(["datum", "portfolj_varde", "omx_index"])
            data = [["datum", "portfolj_varde", "omx_index"]]
            
        rows = data[1:]
        found_row = None
        for i, row in enumerate(rows):
            if row and row[0] == datum_str:
                found_row = i + 2
                break
                
        if found_row:
            worksheet.update_cell(found_row, 2, portfolj_kronor)
            worksheet.update_cell(found_row, 3, omx_stangning)
        else:
            worksheet.append_row([datum_str, portfolj_kronor, omx_stangning])
        return True
    except:
        return False

# --- Funktioner för Innehav ---
def ladda_innehav_gspread(strategi):
    fliknamn = f"Innehav_{strategi}"
    try:
        gc = get_gspread_client()
        sh = gc.open_by_url(st.secrets["google_sheet_url"])
        try: worksheet = sh.worksheet(fliknamn)
        except:
            worksheet = sh.add_worksheet(title=fliknamn, rows="100", cols="5")
            worksheet.append_row(["Bolagsnamn", "Ticker", "Antal", "Kurs"])
            return pd.DataFrame(columns=["Bolagsnamn", "Ticker", "Antal", "Kurs"])
        data = worksheet.get_all_records()
        return pd.DataFrame(data) if data else pd.DataFrame(columns=["Bolagsnamn", "Ticker", "Antal", "Kurs"])
    except:
        return pd.DataFrame(columns=["Bolagsnamn", "Ticker", "Antal", "Kurs"])

def spara_innehav_gspread(df_ny, strategi):
    fliknamn = f"Innehav_{strategi}"
    try:
        gc = get_gspread_client()
        sh = gc.open_by_url(st.secrets["google_sheet_url"])
        try: worksheet = sh.worksheet(fliknamn)
        except: worksheet = sh.add_worksheet(title=fliknamn, rows="100", cols="5")
        worksheet.clear() 
        worksheet.append_row(["Bolagsnamn", "Ticker", "Antal", "Kurs"]) 
        df_clean = df_ny.dropna(subset=['Ticker'])
        df_clean = df_clean[df_clean['Ticker'].astype(str).str.strip() != '']
        if not df_clean.empty:
            worksheet.append_rows(df_clean[["Bolagsnamn", "Ticker", "Antal", "Kurs"]].values.tolist())
        return True
    except:
        return False

# ==========================================
# 2. SESSION STATE (APPENS MINNE)
# ==========================================
strategier = ["Value", "Utdelning", "Momentum"]
for s in strategier:
    if f'bef_portfolj_{s}' not in st.session_state:
        st.session_state[f'bef_portfolj_{s}'] = ladda_innehav_gspread(s)

if 'mal_portfolj' not in st.session_state: st.session_state['mal_portfolj'] = pd.DataFrame(columns=["Bolagsnamn", "Ticker", "Kurs"])
if 'aktiv_strategi' not in st.session_state: st.session_state['aktiv_strategi'] = "Value"
if 'ombalansering_beraknad' not in st.session_state: st.session_state['ombalansering_beraknad'] = False

# ==========================================
# 3. SIDOMENY & STRIPPNING/TVÄTT
# ==========================================
meny_val = st.sidebar.radio(
    "Välj vy:",
    ["📊 Översikt & Historik", "💼 Min Portfölj", "📈 Strategi: Trending Value", "💸 Strategi: Trend. Utdelning", "⚡ Strategi: Momentum", "⚖️ Ombalansering"]
)
uppladdad_fil = st.sidebar.file_uploader("Ladda upp Börsdata-fil", type=["xlsx", "csv"])

def ladda_och_tvatta_basdata(fil):
    df = pd.read_csv(fil, sep=';', encoding='utf-8') if fil.name.endswith('.csv') else pd.read_excel(fil)
    k_namn = next((c for c in df.columns if 'bolagsnamn' in c.lower() or 'namn' in c.lower()), df.columns[0])
    k_tick = next((c for c in df.columns if 'ticker' in c.lower()), df.columns[1])
    k_kurs = next((c for c in df.columns if 'aktiekurs' in c.lower() or ('kurs' in c.lower() and 'utveck' not in c.lower())), None)
    if not k_kurs: k_kurs = df.columns[2]
    df[k_kurs] = pd.to_numeric(df[k_kurs], errors='coerce').fillna(0)
    
    # Standard-tvätt för Börsdata (Börsvärde > 500M och rätt listor)
    k_bv = next((c for c in df.columns if 'börsvärde' in c.lower()), None)
    k_lista = next((c for c in df.columns if 'lista' in c.lower() or 'marknad' in c.lower()), None)
    if k_bv:
        df[k_bv] = pd.to_numeric(df[k_bv], errors='coerce').fillna(0)
        df = df[df[k_bv] >= 500].copy()
    if k_lista:
        df = df[df[k_lista].astype(str).str.contains('Large|Mid|Small', case=False, na=False)].copy()
    return df, k_namn, k_tick, k_kurs

# ==========================================
# 4. SIDORNAS LOGIK
# ==========================================

# --- SIDA 1: ÖVERSIKT & HISTORIK ---
if meny_val == "📊 Översikt & Historik":
    st.title("📊 Portföljöversikt & Evig Historik")
    
    with st.expander("➕ Logga ett nytt totalvärde för dina portföljer"):
        with st.form("logga_varde"):
            valt_datum = st.date_input("Välj datum", datetime.now())
            portfolj_kronor = st.number_input("Totalt värde (Alla portföljer + Kassa) i SEK", min_value=0.0, step=1000.0)
            if st.form_submit_button("Spara datapunkt"):
                datum_str = valt_datum.strftime("%Y-%m-%d")
                with st.spinner("Hämtar OMXSPI från Yahoo Finance..."):
                    try:
                        omx = yf.Ticker("^OMXSPI")
                        hist = omx.history(start=valt_datum, end=valt_datum + timedelta(days=4))
                        if not hist.empty:
                            # Avrunda till max 2 decimaler
                            omx_stangning = round(float(hist['Close'].iloc[0]), 2)
                            
                            # Gör om till svenskt textformat (komma istället för punkt) innan vi sparar
                            port_str = str(round(portfolj_kronor, 2)).replace('.', ',')
                            omx_str = str(omx_stangning).replace('.', ',')
                            
                            if spara_historik_gspread(datum_str, port_str, omx_str):
                                st.success("Sparat i Google Sheets!")
                                st.rerun()
                        else: st.error("Kunde inte hitta indexkurs för detta datum (helgdag?). Prova en närliggande vardag.")
                    except Exception as e: st.error(f"Fel: {e}")

    with st.spinner("Hämtar historik..."):
        hist_df = ladda_historik_gspread()
    
    if len(hist_df) >= 1:
        st.subheader("📈 Procentuell utveckling jämfört med OMX Stockholm PI")
        if len(hist_df) >= 2:
            hist_df['Portfölj (%)'] = (hist_df['portfolj_varde'] / hist_df['portfolj_varde'].iloc[0]) * 100 - 100
            hist_df['OMX Stockholm PI (%)'] = (hist_df['omx_index'] / hist_df['omx_index'].iloc[0]) * 100 - 100
            st.line_chart(hist_df.set_index('datum')[['Portfölj (%)', 'OMX Stockholm PI (%)']])
            
        st.subheader("Historisk datatabell")
        st.dataframe(hist_df.rename(columns={'datum':'Datum', 'portfolj_varde':'Portföljvärde (SEK)', 'omx_index':'OMXSPI Index'}), use_container_width=True)
    else: st.warning("Kalkylarket är tomt. Logga ditt första värde i fliken ovan!")

# --- SIDA 2: MIN PORTFÖLJ ---
elif meny_val == "💼 Min Portfölj":
    st.title("💼 Mina Befintliga Portföljer")
    vald = st.selectbox("Välj portfölj att hantera:", strategier, index=strategier.index(st.session_state['aktiv_strategi']))
    st.session_state['aktiv_strategi'] = vald 
    
    st.subheader(f"Innehav för {vald}")
    st.dataframe(st.session_state[f'bef_portfolj_{vald}'], use_container_width=True)
    
    with st.expander("➕ Lägg till eller ändra en aktie manuellt"):
        with st.form("lagg_till_form"):
            col_namn = st.text_input("Bolagsnamn")
            col_tick = st.text_input("Ticker")
            col_antal = st.number_input("Antal aktier", min_value=0, step=1)
            col_kurs = st.number_input("Kurs (SEK)", min_value=0.0, step=0.1)
            if st.form_submit_button("Spara i tabell"):
                df = st.session_state[f'bef_portfolj_{vald}'].copy()
                new_row = {"Bolagsnamn": col_namn, "Ticker": col_tick.upper().strip(), "Antal": int(col_antal), "Kurs": float(col_kurs)}
                if col_tick.upper().strip() in df['Ticker'].values:
                    df.loc[df['Ticker'] == col_tick.upper().strip(), :] = [new_row['Bolagsnamn'], new_row['Ticker'], new_row['Antal'], new_row['Kurs']]
                else: df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                st.session_state[f'bef_portfolj_{vald}'] = df
                st.rerun()

    c1, c2 = st.columns(2)
    with c1:
        if uppladdad_fil and st.button(f"🔄 Hämta dagsaktuella priser från Börsdata-filen"):
            df_bd, k_namn, k_tick, k_kurs = ladda_och_tvatta_basdata(uppladdad_fil)
            kurs_dict = dict(zip(df_bd[k_tick].astype(str).str.upper().str.strip(), df_bd[k_kurs]))
            temp_bef = st.session_state[f'bef_portfolj_{vald}'].copy()
            for idx, row in temp_bef.iterrows():
                t = str(row['Ticker']).upper().strip()
                if t in kurs_dict: temp_bef.at[idx, 'Kurs'] = float(kurs_dict[t])
            st.session_state[f'bef_portfolj_{vald}'] = temp_bef
            st.success("Kurserna har uppdaterats i vyn!")
            st.rerun()
    with c2:
        if st.button(f"💾 Spara {vald}-portföljen permanent till Google Sheets"):
            if spara_innehav_gspread(st.session_state[f'bef_portfolj_{vald}'], vald): st.success("Sparat i molnet!")

# --- SIDA 3, 4, 5: STRATEGIERNA ---
elif "Strategi" in meny_val:
    st.title(meny_val)
    strat_typ = "Value" if "Value" in meny_val else "Utdelning" if "Utdelning" in meny_val else "Momentum"
    
    if uppladdad_fil:
        with st.spinner("Beräknar strategi..."):
            df, k_namn, k_tick, k_kurs = ladda_och_tvatta_basdata(uppladdad_fil)
            
            # Beräkningar baserat på vald strategi
            if strat_typ == "Value":
                k_pe, k_ps, k_pb, k_pfcf, k_ev = 'P/E - Senaste', 'P/S - Senaste', 'P/B - Senaste', 'P/FCF - Senaste', 'EV/EBITDA - Senaste'
                v_kols = [k_pe, k_ps, k_pb, k_pfcf, k_ev]
                for k in v_kols:
                    if k in df.columns: df[k] = pd.to_numeric(df[k], errors='coerce').fillna(5000)
                    else: df[k] = 5000
                    df
