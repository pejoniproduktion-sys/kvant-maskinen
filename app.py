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
st.set_page_config(page_title="Kvant-Maskinen v3.3", page_icon="🚀", layout="wide")

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
            return pd.DataFrame(columns=['datum', 'varde_value', 'varde_utdelning', 'varde_momentum', 'portfolj_varde', 'omx_index'])
        
        df['datum'] = df['datum'].astype(str)
        
        for col in ['varde_value', 'varde_utdelning', 'varde_momentum', 'portfolj_varde', 'omx_index']:
            if col not in df.columns:
                df[col] = 0
            else:
                df[col] = pd.to_numeric(df[col].astype(str).str.replace(' ', '').str.replace(',', '.'), errors='coerce').fillna(0)
                
        return df.sort_values('datum').reset_index(drop=True)
    except:
        return pd.DataFrame(columns=['datum', 'varde_value', 'varde_utdelning', 'varde_momentum', 'portfolj_varde', 'omx_index'])

def spara_historik_gspread(datum_str, v_val_str, v_utd_str, v_mom_str, tot_str, omx_str):
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
            worksheet.update_cell(found_row, 2, v_val_str)
            worksheet.update_cell(found_row, 3, v_utd_str)
            worksheet.update_cell(found_row, 4, v_mom_str)
            worksheet.update_cell(found_row, 5, tot_str)
            worksheet.update_cell(found_row, 6, omx_str)
        else:
            worksheet.append_row([datum_str, v_val_str, v_utd_str, v_mom_str, tot_str, omx_str])
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
    ["📊 Översikt & Historik", "💼 Min Portfölj", "📅 Säsongsmönster & Viktning", "📈 Strategi: Trending Value", "💸 Strategi: Trend. Utdelning", "⚡ Strategi: Momentum", "⚖️ Ombalansering"]
)
uppladdad_fil = st.sidebar.file_uploader("Ladda upp Börsdata-fil", type=["xlsx", "csv"])

def ladda_och_tvatta_basdata(fil):
    df = pd.read_csv(fil, sep=';', encoding='utf-8') if fil.name.endswith('.csv') else pd.read_excel(fil)
    k_namn = next((c for c in df.columns if 'bolagsnamn' in c.lower() or 'namn' in c.lower()), df.columns[0])
    k_tick = next((c for c in df.columns if 'ticker' in c.lower()), df.columns[1])
    k_kurs = next((c for c in df.columns if 'aktiekurs' in c.lower() or ('kurs' in c.lower() and 'utveck' not in c.lower())), None)
    if not k_kurs: k_kurs = df.columns[2]
    df[k_kurs] = pd.to_numeric(df[k_kurs], errors='coerce').fillna(0)
    
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

# --- SIDA 1: ÖVERSIKT & HISTORIK (NU MED DASHBOARD) ---
if meny_val == "📊 Översikt & Historik":
    st.title("📊 Portföljöversikt & Dashboard")
    
    with st.expander("➕ Logga värde per kvantstrategi"):
        with st.form("logga_varde"):
            valt_datum = st.date_input("Välj datum", datetime.now())
            
            v_value = st.number_input("Värde: Trending Value (SEK)", min_value=0.0, step=1000.0)
            v_utd = st.number_input("Utdelning: Trendande Utdelning (SEK)", min_value=0.0, step=1000.0)
            v_mom = st.number_input("Momentum: Sammansatt Momentum (SEK)", min_value=0.0, step=1000.0)
            
            if st.form_submit_button("Spara datapunkt"):
                datum_str = valt_datum.strftime("%Y-%m-%d")
                totalt_portfoljvarde = v_value + v_utd + v_mom
                
                with st.spinner("Hämtar OMXSPI från Yahoo Finance..."):
                    try:
                        omx = yf.Ticker("^OMXSPI")
                        hist = omx.history(start=valt_datum, end=valt_datum + timedelta(days=4))
                        if not hist.empty:
                            omx_stangning = round(float(hist['Close'].iloc[0]), 2)
                            
                            val_str = str(round(v_value, 2)).replace('.', ',')
                            utd_str = str(round(v_utd, 2)).replace('.', ',')
                            mom_str = str(round(v_mom, 2)).replace('.', ',')
                            tot_str = str(round(totalt_portfoljvarde, 2)).replace('.', ',')
                            omx_str = str(omx_stangning).replace('.', ',')
                            
                            if spara_historik_gspread(datum_str, val_str, utd_str, mom_str, tot_str, omx_str):
                                st.success(f"Sparat! Total portfölj: {totalt_portfoljvarde:,.0f} SEK")
                                st.rerun()
                        else: 
                            st.error("Kunde inte hitta indexkurs.")
                    except Exception as e: 
                        st.error(f"Fel: {e}")

    with st.spinner("Hämtar historik..."):
        hist_df = ladda_historik_gspread()
    
    if len(hist_df) >= 1:
        if len(hist_df) >= 2:
            st.subheader("📈 Utveckling per strategi jämfört med OMXSPI")
            
            # Skapa en DataFrame för den dynamiska grafen
            kols_att_raknas = {
                'varde_value': 'Value (%)',
                'varde_utdelning': 'Utdelning (%)',
                'varde_momentum': 'Momentum (%)',
                'portfolj_varde': 'Total Portfölj (%)',
                'omx_index': 'OMXSPI (%)'
            }
            
            graf_df = hist_df[['datum']].copy()
            
            # Beräkna procentuell uppgång för varje specifik strategi separat
            for org_col, ny_col in kols_att_raknas.items():
                start_varden = hist_df[hist_df[org_col] > 0][org_col]
                if not start_varden.empty:
                    start_v = start_varden.iloc[0]
                    graf_df[ny_col] = (hist_df[org_col] / start_v) * 100 - 100
                else:
                    graf_df[ny_col] = 0.0
            
            graf_df = graf_df.set_index('datum')
            
            # Snygga Dashboard-kort högst upp!
            senaste_pct = graf_df.iloc[-1]
            senaste_sek = hist_df.iloc[-1]
            
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("💼 Total Portfölj", f"{senaste_sek['portfolj_varde']:,.0f} kr".replace(',', ' '), f"{senaste_pct['Total Portfölj (%)']:.1f} % totalt")
            c2.metric("📈 Value", f"{senaste_sek['varde_value']:,.0f} kr".replace(',', ' '), f"{senaste_pct['Value (%)']:.1f} %")
            c3.metric("💸 Utdelning", f"{senaste_sek['varde_utdelning']:,.0f} kr".replace(',', ' '), f"{senaste_pct['Utdelning (%)']:.1f} %")
            c4.metric("⚡ Momentum", f"{senaste_sek['varde_momentum']:,.0f} kr".replace(',', ' '), f"{senaste_pct['Momentum (%)']:.1f} %")
            c5.metric("📊 OMXSPI", f"{senaste_sek['omx_index']:,.0f}".replace(',', ' '), f"{senaste_pct['OMXSPI (%)']:.1f} %", delta_color="off")
            
            st.markdown("---")
            
            # Rita ut den separerade, klickbara grafen
            st.line_chart(graf_df)
            
        st.subheader("Historisk datatabell")
        vy_df = hist_df.rename(columns={
            'datum': 'Datum', 
            'varde_value': 'Value (SEK)', 
            'varde_utdelning': 'Utdelning (SEK)', 
            'varde_momentum': 'Momentum (SEK)', 
            'portfolj_varde': 'Total Portfölj (SEK)', 
            'omx_index': 'OMXSPI Index'
        })
        st.dataframe(vy_df, use_container_width=True)
    else: 
        st.warning("Kalkylarket är tomt. Logga dina första värden ovan!")

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
        if uppladdad_fil and st.button(f"🔄 Hämta dagsaktuella priser"):
            df_bd, k_namn, k_tick, k_kurs = ladda_och_tvatta_basdata(uppladdad_fil)
            kurs_dict = dict(zip(df_bd[k_tick].astype(str).str.upper().str.strip(), df_bd[k_kurs]))
            temp_bef = st.session_state[f'bef_portfolj_{vald}'].copy()
            for idx, row in temp_bef.iterrows():
                t = str(row['Ticker']).upper().strip()
                if t in kurs_dict: temp_bef.at[idx, 'Kurs'] = float(kurs_dict[t])
            st.session_state[f'bef_portfolj_{vald}'] = temp_bef
            st.success("Kurserna har uppdaterats!")
            st.rerun()
    with c2:
        if st.button(f"💾 Spara {vald}-portföljen permanent"):
            if spara_innehav_gspread(st.session_state[f'bef_portfolj_{vald}'], vald): st.success("Sparat i molnet!")

# --- SIDA 3: SÄSONGSMÖNSTER & VIKTNING ---
elif meny_val == "📅 Säsongsmönster & Viktning":
    st.title("📅 Säsongsmönster & Dynamisk Viktning")
    st.markdown("Statistiska säsongsmönster (kalendareffekter) påverkar kraftigt hur strategier som Värde, Utdelning och Momentum presterar.")

    nuvarande_manad = datetime.now().month
    manader = ["Januari", "Februari", "Mars", "April", "Maj", "Juni", "Juli", "Augusti", "September", "Oktober", "November", "December"]
    manad_namn = manader[nuvarande_manad - 1]

    st.subheader(f"📍 Aktuell rekommendation för {manad_namn}")

    if nuvarande_manad in [11, 12, 1]:
        st.success("🟢 **Skala upp: Värdestrategi (Value)**\n\nUtnyttja januarieffekten. Positionera dig i nedpressade värdebolag nu.")
        if nuvarande_manad in [12, 1]:
            st.error("🔴 **Undvik / Skala ner: Momentum**\n\n**CRITICAL:** Momentum riskerar vinsthemtagningar. Januari är historiskt den sämsta månaden för Momentum-strategin.")
    elif nuvarande_manad in [2, 3, 4]:
        st.success("🟢 **Skala upp: Utdelning (Dividend) & Momentum**\n\nRid på utdelningsrallyt fram till april. Momentum fungerar utmärkt nu.")
        st.warning("🟡 **Skala ner: Värde (Value)**\n\nJanuarieffekten är avslutad.")
    elif nuvarande_manad in [5, 6, 7, 8]:
        st.info("🟡 **Fokus: Kassalikviditet / Defensivt**\n\n'Sell in May and go away' har viss statistisk bärighet.")
        st.error("🔴 **Skala ner: Utdelning (Dividend) & Värde (Value)**\n\nHögutdelare hamnar i ett vakuum efter våren. Värdebolag missgynnas av låg likviditet.")
    elif nuvarande_manad in [9, 10]:
        st.success("🟢 **Skala upp: Momentum**\n\nMarknaden vaknar till liv igen efter sommaren. Starka trender brukar etableras.")

    st.markdown("---")
    st.subheader("📊 Årshjul för kvantstrategierna")
    
    data_sasong = {
        "Period": ["Vinter (Nov – Jan)", "Vår (Feb – April)", "Sommar (Maj – Aug)", "Höst (Sep – Okt)"],
        "Fokus / Skala upp": ["Value", "Dividend & Momentum", "Kassalikviditet / Defensivt", "Momentum"],
        "Undvik / Skala ner": ["Momentum", "Value (efter jan)", "Dividend & Value", "-"],
        "Strategisk tanke": ["Utnyttja januarieffekten. Sänk momentum i december/januari.", "Rid på utdelningsrallyt fram till april.", "'Sell in May and go away' har viss bärighet.", "Marknaden vaknar till liv och trender etableras."]
    }
    st.table(pd.DataFrame(data_sasong))

# --- SIDA 4, 5, 6: STRATEGIERNA ---
elif "Strategi" in meny_val:
    st.title(meny_val)
    strat_typ = "Value" if "Value" in meny_val else "Utdelning" if "Utdelning" in meny_val else "Momentum"
    
    if uppladdad_fil:
        with st.spinner("Beräknar strategi..."):
            df, k_namn, k_tick, k_kurs = ladda_och_tvatta_basdata(uppladdad_fil)
            
            if strat_typ == "Value":
                k_pe, k_ps, k_pb, k_pfcf, k_ev = 'P/E - Senaste', 'P/S - Senaste', 'P/B - Senaste', 'P/FCF - Senaste', 'EV/EBITDA - Senaste'
                v_kols = [k_pe, k_ps, k_pb, k_pfcf, k_ev]
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

# --- SIDA 7: OMBALANSERING ---
elif meny_val == "⚖️ Ombalansering":
    st.title("⚖️ Portföljombalansering")
    
    vald_strat = st.selectbox("Välj portfölj att arbeta med:", strategier, index=strategier.index(st.session_state['aktiv_strategi']))
    st.session_state['aktiv_strategi'] = vald_strat
    
    st.info(f"📍 Aktuellt läge: Jämför befintlig **{vald_strat}**-portfölj med dina inskickade målaktier.")
    kassa = st.number_input("Nysparande / Ledig kassa att tillföra (SEK)", min_value=0, value=10000, step=1000)
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("1. Din Befintliga Portfölj")
        st.dataframe(st.session_state[f'bef_portfolj_{vald_strat}'], use_container_width=True)
    with col2:
        st.subheader("2. Dina Nya Målaktier (Topp 10)")
        st.dataframe(st.session_state['mal_portfolj'], use_container_width=True)
        
    if st.button("⚡ Beräkna ombalansering", type="primary"):
        df_bef = pd.DataFrame(st.session_state[f'bef_portfolj_{vald_strat}']).dropna(subset=['Ticker'])
        df_bef = df_bef[df_bef['Ticker'].astype(str).str.strip() != '']
        df_mal = pd.DataFrame(st.session_state['mal_portfolj']).dropna(subset=['Ticker'])
        df_mal = df_mal[df_mal['Ticker'].astype(str).str.strip() != '']
        
        df_bef['Ticker'] = df_bef['Ticker'].astype(str).str.upper().str.strip()
        df_mal['Ticker'] = df_mal['Ticker'].astype(str).str.upper().str.strip()
        
        df_bef['Antal'] = pd.to_numeric(df_bef['Antal'], errors='coerce').fillna(0)
        df_bef['Kurs'] = pd.to_numeric(df_bef['Kurs'], errors='coerce').fillna(0)
        df_mal['Kurs'] = pd.to_numeric(df_mal['Kurs'], errors='coerce').fillna(0)
        
        nuvarande_aktie_varde = (df_bef['Antal'] * df_bef['Kurs']).sum() if not df_bef.empty else 0
        totalt_portfolj_varde = nuvarande_aktie_varde + kassa
        antal_malbolag = len(df_mal)
        
        if antal_malbolag > 0:
            mal_varde_per_aktie = totalt_portfolj_varde / antal_malbolag
            st.session_state['tot_v'] = totalt_portfolj_varde
            st.session_state['mal_v'] = mal_varde_per_aktie
            
            ordrar = []
            ny_p_rader = []
            
            for _, r in df_bef.iterrows():
                if r['Ticker'] not in df_mal['Ticker'].values:
                    ordrar.append({"Bolagsnamn": r['Bolagsnamn'], "Ticker": r['Ticker'], "Handling": "🔴 SÄLJ ALLT", "Antal aktier": int(r['Antal']), "Kurs": r['Kurs']})
            
            for _, r in df_mal.iterrows():
                t = r['Ticker']
                k = float(r['Kurs'])
                n = r['Bolagsnamn']
                m_antal = int(mal_varde_per_aktie // k) if k > 0 else 0
                
                if m_antal > 0: ny_p_rader.append({"Bolagsnamn": n, "Ticker": t, "Antal": m_antal, "Kurs": k})
                match = df_bef[df_bef['Ticker'] == t]
                
                if not match.empty:
                    nuv_a = int(match['Antal'].iloc[0])
                    diff = m_antal - nuv_a
                    if diff > 0: ordrar.append({"Bolagsnamn": n, "Ticker": t, "Handling": "🔵 KÖP MER", "Antal aktier": int(diff), "Kurs": k})
                    elif diff < 0: ordrar.append({"Bolagsnamn": n, "Ticker": t, "Handling": "   SÄLJ AV", "Antal aktier": int(abs(diff)), "Kurs": k})
                else:
                    ordrar.append({"Bolagsnamn": n, "Ticker": t, "Handling": "🟢 KÖP NY", "Antal aktier": int(m_antal), "Kurs": k})
                    
            st.session_state['ordrar_res'] = pd.DataFrame(ordrar)
            st.session_state['ny_p_res'] = pd.DataFrame(ny_p_rader)
            st.session_state['ombalansering_beraknad'] = True
        else: st.error("Hittade inga målaktier.")

    if st.session_state['ombalansering_beraknad']:
        st.markdown("---")
        st.metric("Totalt Portföljvärde (inkl. kassa)", f"{st.session_state['tot_v']:,.0f} kr")
        st.metric("Målvärde per aktie (Lika vikt)", f"{st.session_state['mal_v']:,.0f} kr")
        
        st.subheader("🛒 Köp- och säljinstruktioner:")
        st.dataframe(st.session_state['ordrar_res'], use_container_width=True)
        
        st.markdown(f"### 💾 Spara resultatet för {vald_strat}")
        if st.button(f"💾 Verkställ affärer & spara som mitt nya {vald_strat}-innehav"):
            with st.spinner("Sparar till Google Sheets..."):
                if spara_innehav_gspread(st.session_state['ny_p_res'], vald_strat):
                    st.session_state[f'bef_portfolj_{vald_strat}'] = st.session_state['ny_p_res']
                    st.session_state['ombalansering_beraknad'] = False
                    st.success(f"🎉 Klart! Din nya {vald_strat}-portfölj har sparats!")
                    st.rerun()
