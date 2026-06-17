import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import json
import gspread
from google.oauth2.service_account import Credentials

# ==========================================
# 1. APPENS INSTÄLLNINGAR & GOOGLE CONNECTIONS
# ==========================================
st.set_page_config(page_title="Kvant-Maskinen v2.0", page_icon="🚀", layout="wide")

def get_gspread_client():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(st.secrets["google_credentials"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(creds)

# --- Funktioner för Historik-fliken ---
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
        df['portfolj_varde'] = pd.to_numeric(df['portfolj_varde'], errors='coerce').fillna(0)
        df['omx_index'] = pd.to_numeric(df['omx_index'], errors='coerce').fillna(0)
        return df.sort_values('datum').reset_index(drop=True)
    except Exception as e:
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
    except Exception as e:
        st.error(f"Fel vid kommunikation med Google Sheets: {e}")
        return False

# --- Funktioner för portföljinnehav (Nu uppdelat per strategi!) ---
def ladda_innehav_gspread(strategi="Value"):
    fliknamn = f"Innehav_{strategi}"
    try:
        gc = get_gspread_client()
        sh = gc.open_by_url(st.secrets["google_sheet_url"])
        try:
            worksheet = sh.worksheet(fliknamn)
        except gspread.exceptions.WorksheetNotFound:
            worksheet = sh.add_worksheet(title=fliknamn, rows="100", cols="5")
            worksheet.append_row(["Bolagsnamn", "Ticker", "Antal", "Kurs"])
            return pd.DataFrame([{"Bolagsnamn": "", "Ticker": "", "Antal": 0, "Kurs": 0.0}])
            
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        if df.empty:
            return pd.DataFrame([{"Bolagsnamn": "", "Ticker": "", "Antal": 0, "Kurs": 0.0}])
        return df
    except Exception as e:
        return pd.DataFrame([{"Bolagsnamn": "", "Ticker": "", "Antal": 0, "Kurs": 0.0}])

def spara_innehav_gspread(df_ny, strategi="Value"):
    fliknamn = f"Innehav_{strategi}"
    try:
        gc = get_gspread_client()
        sh = gc.open_by_url(st.secrets["google_sheet_url"])
        try:
            worksheet = sh.worksheet(fliknamn)
        except gspread.exceptions.WorksheetNotFound:
            worksheet = sh.add_worksheet(title=fliknamn, rows="100", cols="5")
            
        worksheet.clear() 
        worksheet.append_row(["Bolagsnamn", "Ticker", "Antal", "Kurs"]) 
        
        df_clean = df_ny.dropna(subset=['Ticker'])
        df_clean = df_clean[df_clean['Ticker'].astype(str).str.strip() != '']
        
        if not df_clean.empty:
            rader = df_clean[["Bolagsnamn", "Ticker", "Antal", "Kurs"]].values.tolist()
            worksheet.append_rows(rader)
        return True
    except Exception as e:
        st.error(f"Kunde inte spara {strategi}-portföljen till Google Sheets: {e}")
        return False

# ==========================================
# 2. APPENS KORTTIDS-MINNE (SESSION STATE)
# ==========================================
# Ladda in alla tre portföljer från start
strategier = ["Value", "Utdelning", "Momentum"]

for s in strategier:
    if f'bef_portfolj_{s}' not in st.session_state:
        st.session_state[f'bef_portfolj_{s}'] = ladda_innehav_gspread(s)

if 'mal_portfolj' not in st.session_state:
    st.session_state['mal_portfolj'] = pd.DataFrame(columns=["Bolagsnamn", "Ticker", "Kurs"])

if 'aktiv_strategi' not in st.session_state:
    st.session_state['aktiv_strategi'] = "Value"

if 'ombalansering_beraknad' not in st.session_state:
    st.session_state['ombalansering_beraknad'] = False
if 'ordrar_lista' not in st.session_state:
    st.session_state['ordrar_lista'] = []
if 'ny_portfolj_df' not in st.session_state:
    st.session_state['ny_portfolj_df'] = pd.DataFrame()

# ==========================================
# 3. SIDOMENY OCH DELAD DATALADDNING
# ==========================================
st.sidebar.title("Kvant-Maskinen 🚀")
st.sidebar.markdown("---")

meny_val = st.sidebar.radio(
    "Välj vy:",
    [
        "📊 Översikt & Historik", 
        "💼 Min Portfölj",
        "📈 Strategi: Trending Value", 
        "💸 Strategi: Trend. Utdelning", 
        "⚡ Strategi: Momentum", 
        "⚖️ Ombalansering"
    ]
)

st.sidebar.markdown("---")
st.sidebar.info("Ladda upp din Excel-export från Börsdata nedan.")
uppladdad_fil = st.sidebar.file_uploader("Ladda upp Börsdata-fil", type=["xlsx", "csv"])

def ladda_och_tvatta_basdata(fil):
    if fil.name.endswith('.csv'):
        df = pd.read_csv(fil, sep=';', encoding='utf-8')
    else:
        df = pd.read_excel(fil)
        
    kol_namn = next((c for c in df.columns if 'bolagsnamn' in c.lower() or 'namn' in c.lower()), df.columns[0])
    kol_ticker = next((c for c in df.columns if 'ticker' in c.lower()), df.columns[1])
    
    kol_kurs = None
    for c in df.columns:
        if 'aktiekurs' in c.lower():
            kol_kurs = c
            break
    if not kol_kurs:
        kol_kurs = next((c for c in df.columns if 'kurs' in c.lower() and 'utveck' not in c.lower()), None)
    if kol_kurs:
        df[kol_kurs] = pd.to_numeric(df[kol_kurs], errors='coerce').fillna(0)
    else:
        kol_kurs = 'Kurs'
        df[kol_kurs] = 0
        
    kol_borsvarde = next((c for c in df.columns if 'börsvärde' in c.lower()), None)
    kol_lista = next((c for c in df.columns if 'lista' in c.lower() or 'marknad' in c.lower()), None)

    if kol_borsvarde:
        df[kol_borsvarde] = pd.to_numeric(df[kol_borsvarde], errors='coerce').fillna(0)
        df = df[df[kol_borsvarde] >= 500].copy()
    if kol_lista:
        df = df[df[kol_lista].astype(str).str.contains('Large|
