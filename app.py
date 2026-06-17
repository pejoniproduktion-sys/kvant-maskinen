import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import json
import gspread
from google.oauth2.service_account import Credentials

# ==========================================
# 1. INSTÄLLNINGAR & GOOGLE-KOppling
# ==========================================
st.set_page_config(page_title="Kvant-Maskinen v2.3", page_icon="🚀", layout="wide")

def get_gspread_client():
    creds_dict = json.loads(st.secrets["google_credentials"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
    return gspread.authorize(creds)

# --- Funktioner för data ---
def ladda_innehav_gspread(strategi):
    try:
        gc = get_gspread_client()
        sh = gc.open_by_url(st.secrets["google_sheet_url"])
        try: worksheet = sh.worksheet(f"Innehav_{strategi}")
        except: worksheet = sh.add_worksheet(title=f"Innehav_{strategi}", rows="100", cols="5")
        data = worksheet.get_all_records()
        return pd.DataFrame(data) if data else pd.DataFrame(columns=["Bolagsnamn", "Ticker", "Antal", "Kurs"])
    except: return pd.DataFrame(columns=["Bolagsnamn", "Ticker", "Antal", "Kurs"])

def spara_innehav_gspread(df, strategi):
    try:
        gc = get_gspread_client()
        sh = gc.open_by_url(st.secrets["google_sheet_url"])
        worksheet = sh.worksheet(f"Innehav_{strategi}")
        worksheet.clear()
        worksheet.append_row(["Bolagsnamn", "Ticker", "Antal", "Kurs"])
        if not df.empty: worksheet.append_rows(df.values.tolist())
        return True
    except: return False

# ==========================================
# 2. SESSION STATE
# ==========================================
strategier = ["Value", "Utdelning", "Momentum"]
for s in strategier:
    if f'bef_portfolj_{s}' not in st.session_state: st.session_state[f'bef_portfolj_{s}'] = ladda_innehav_gspread(s)
if 'mal_portfolj' not in st.session_state: st.session_state['mal_portfolj'] = pd.DataFrame(columns=["Bolagsnamn", "Ticker", "Kurs"])
if 'aktiv_strategi' not in st.session_state: st.session_state['aktiv_strategi'] = "Value"

# ==========================================
# 3. SIDOMENY & HJÄLPFUNKTIONER
# ==========================================
meny_val = st.sidebar.radio("Välj vy:", ["💼 Min Portfölj", "📈 Strategi: Trending Value", "💸 Strategi: Trend. Utdelning", "⚡ Strategi: Momentum", "⚖️ Ombalansering"])
uppladdad_fil = st.sidebar.file_uploader("Ladda upp Börsdata-fil", type=["xlsx", "csv"])

def ladda_och_tvatta(fil):
    df = pd.read_csv(fil, sep=';', encoding='utf-8') if fil.name.endswith('.csv') else pd.read_excel(fil)
    k_namn = next((c for c in df.columns if 'bolagsnamn' in c.lower() or 'namn' in c.lower()), df.columns[0])
    k_tick = next((c for c in df.columns if 'ticker' in c.lower()), df.columns[1])
    k_kurs = next((c for c in df.columns if 'kurs' in c.lower() and 'utveck' not in c.lower()), df.columns[2])
    return df, k_namn, k_tick, k_kurs

# ==========================================
# 4. SIDOR
# ==========================================
if meny_val == "💼 Min Portfölj":
    st.title("💼 Mina Befintliga Portföljer")
    vald = st.selectbox("Välj portfölj:", strategier, index=strategier.index(st.session_state['aktiv_strategi']))
    st.session_state['aktiv_strategi'] = vald 
    
    st.dataframe(st.session_state[f'bef_portfolj_{vald}'], use_container_width=True)
    
    with st.expander("➕ Lägg till/Ändra aktie"):
        with st.form("lagg_till"):
            n, t, a, k = st.text_input("Namn"), st.text_input("Ticker"), st.number_input("Antal", 0), st.number_input("Kurs", 0.0)
            if st.form_submit_button("Spara"):
                df = st.session_state[f'bef_portfolj_{vald}'].copy()
                row = {"Bolagsnamn": n, "Ticker": t.upper(), "Antal": a, "Kurs": k}
                if t.upper() in df['Ticker'].values: df.loc[df['Ticker'] == t.upper()] = row.values()
                else: df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
                st.session_state[f'bef_portfolj_{vald}'] = df
                st.rerun()

    if st.button("💾 Spara till Google Sheets"):
        if spara_innehav_gspread(st.session_state[f'bef_portfolj_{vald}'], vald): st.success("Sparat!")

elif "Strategi" in meny_val:
    st.title(meny_val)
    if uppladdad_fil:
        df, k_namn, k_tick, k_kurs = ladda_och_tvatta(uppladdad_fil)
        st.dataframe(df.head(10), use_container_width=True)
        if st.button("⚡ Skicka Topp 10 till Ombalansering"):
            st.session_state['mal_portfolj'] = df[[k_namn, k_tick, k_kurs]].head(10).rename(columns={k_namn:"Bolagsnamn", k_tick:"Ticker", k_kurs:"Kurs"})
            st.session_state['aktiv_strategi'] = meny_val.split(": ")[1].replace("Trend. ", "").strip()
            st.success("Skickat till Ombalansering!")

elif meny_val == "⚖️ Ombalansering":
    st.title("⚖️ Ombalansering")
    strat = st.session_state['aktiv_strategi']
    kassa = st.number_input("Nysparande (SEK)", 10000)
    
    c1, c2 = st.columns(2)
    with c1: st.subheader("Befintlig"); st.dataframe(st.session_state[f'bef_portfolj_{strat}'])
    with c2: st.subheader("Målaktier"); st.dataframe(st.session_state['mal_portfolj'])
    
    if st.button("Beräkna affärer"):
        df_bef = st.session_state[f'bef_portfolj_{strat}']
        df_mal = st.session_state['mal_portfolj']
        
        # Beräkningslogik
        tot_varde = (df_bef['Antal'] * df_bef['Kurs']).sum() + kassa
        mal_per_aktie = tot_varde / len(df_mal)
        
        ordrar = []
        for _, r in df_mal.iterrows():
            kurs = float(r['Kurs'])
            antal = int(mal_per_aktie // kurs)
            ordrar.append({"Ticker": r['Ticker'], "Antal att äga": antal, "Handling": "KÖP"})
        
        st.session_state['ordrar'] = pd.DataFrame(ordrar)
        st.session_state['ny_portfolj'] = st.session_state['mal_portfolj'].copy()
        st.session_state['ny_portfolj']['Antal'] = [int(mal_per_aktie // float(r['Kurs'])) for _, r in df_mal.iterrows()]

    if 'ordrar' in st.session_state:
        st.dataframe(st.session_state['ordrar'])
        if st.button("💾 Verkställ & Spara"):
            spara_innehav_gspread(st.session_state['ny_portfolj'], strat)
            st.session_state[f'bef_portfolj_{strat}'] = st.session_state['ny_portfolj']
            st.success("Portfölj uppdaterad i Google Sheets!")
