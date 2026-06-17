import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import json
import gspread
from google.oauth2.service_account import Credentials

# ==========================================
# 1. APPENS INSTÄLLNINGAR & MINNE (SESSION STATE)
# ==========================================
st.set_page_config(page_title="Kvant-Maskinen v1.2", page_icon="🚀", layout="wide")

# Skapa appens korttidsminne så data överlever flikbyten
if 'bef_portfolj' not in st.session_state:
    st.session_state['bef_portfolj'] = pd.DataFrame([{"Bolagsnamn": "", "Ticker": "", "Antal": 0, "Kurs": 0.0}])
if 'mal_portfolj' not in st.session_state:
    st.session_state['mal_portfolj'] = pd.DataFrame(columns=["Bolagsnamn", "Ticker", "Kurs"])

def get_gspread_client():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(st.secrets["google_credentials"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(creds)

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

# ==========================================
# 2. SIDOMENY OCH DELAD DATALADDNING
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
        df = df[df[kol_lista].astype(str).str.contains('Large|Mid|Small', case=False, na=False)].copy()
        
    return df, kol_namn, kol_ticker, kol_kurs

# ==========================================
# 3. SIDORNAS LOGIK
# ==========================================

if meny_val == "📊 Översikt & Historik":
    st.title("📊 Portföljöversikt & Evig Historik")
    
    with st.expander("➕ Logga ett nytt portföljvärde"):
        with st.form("logga_varde"):
            valt_datum = st.date_input("Välj datum för loggning", datetime.now())
            portfolj_kronor = st.number_input("Totalt portföljvärde (Aktier + Kassa) i SEK", min_value=0.0, step=1000.0)
            knapp_spara = st.form_submit_button("Spara datapunkt")
            
            if knapp_spara:
                datum_str = valt_datum.strftime("%Y-%m-%d")
                with st.spinner("Hämtar indexdata från Yahoo Finance..."):
                    try:
                        omx = yf.Ticker("^OMXSPI")
                        start_date = valt_datum
                        end_date = valt_datum + timedelta(days=4)
                        hist = omx.history(start=start_date, end=end_date)
                        
                        if not hist.empty:
                            omx_stangning = float(hist['Close'].iloc[0])
                            if spara_historik_gspread(datum_str, portfolj_kronor, omx_stangning):
                                st.success(f"Sparat i Google Sheets! Portfölj: {portfolj_kronor:,.0f} kr, OMXSPI: {omx_stangning:.2f}")
                                st.rerun()
                        else:
                            st.error("Kunde inte hitta indexkurs.")
                    except Exception as e:
                        st.error(f"Ett fel uppstod: {e}")

    with st.spinner("Hämtar din historik från Google Sheets..."):
        hist_df = ladda_historik_gspread()
    
    if len(hist_df) >= 1:
        st.subheader("📈 Utveckling jämfört med OMX Stockholm PI")
        if len(hist_df) >= 2:
            hist_df['Portfölj (%)'] = (hist_df['portfolj_varde'] / hist_df['portfolj_varde'].iloc[0]) * 100 - 100
            hist_df['OMX Stockholm PI (%)'] = (hist_df['omx_index'] / hist_df['omx_index'].iloc[0]) * 100 - 100
            graf_df = hist_df.set_index('datum')[['Portfölj (%)', 'OMX Stockholm PI (%)']]
            st.line_chart(graf_df)
        st.dataframe(hist_df.rename(columns={'datum':'Datum', 'portfolj_varde':'Portföljvärde (SEK)', 'omx_index':'OMXSPI Index'}), use_container_width=True)

# ---------------------------------------------------------
# NY FLIK: MIN PORTFÖLJ
# ---------------------------------------------------------
elif meny_val == "💼 Min Portfölj":
    st.title("💼 Min Befintliga Portfölj")
    st.write("Skriv in dina aktier här. Appen minns dem när du hoppar mellan flikarna!")
    
    # Låt användaren redigera portföljen (sparas direkt i minnet)
    redigerad_bef = st.data_editor(st.session_state['bef_portfolj'], num_rows="dynamic", use_container_width=True, key="edit_min_portfolj")
    st.session_state['bef_portfolj'] = redigerad_bef
    
    if uppladdad_fil is not None:
        if st.button("🔄 Hämta dagsaktuella kurser från Börsdata"):
            df_bd, kol_namn_bd, kol_tick_bd, kol_kurs_bd = ladda_och_tvatta_basdata(uppladdad_fil)
            # Skapa ett lexikon för snabb sökning av kurser
            kurs_dict = dict(zip(df_bd[kol_tick_bd].astype(str).str.upper().str.strip(), df_bd[kol_kurs_bd]))
            namn_dict = dict(zip(df_bd[kol_tick_bd].astype(str).str.upper().str.strip(), df_bd[kol_namn_bd]))
            
            temp_bef = st.session_state['bef_portfolj'].copy()
            uppdaterade = 0
            for idx, row in temp_bef.iterrows():
                ticker = str(row['Ticker']).upper().strip()
                if ticker in kurs_dict:
                    temp_bef.at[idx, 'Kurs'] = float(kurs_dict[ticker])
                    # Kan även fylla i bolagsnamnet automatiskt om det saknas
                    if pd.isna(row['Bolagsnamn']) or row['Bolagsnamn'] == "":
                        temp_bef.at[idx, 'Bolagsnamn'] = namn_dict[ticker]
                    uppdaterade += 1
            
            st.session_state['bef_portfolj'] = temp_bef
            st.success(f"✅ Kurser för {uppdaterade} aktier uppdaterades!")
            st.rerun()
    else:
        st.info("👈 Ladda upp en Börsdata-fil i menyn om du vill kunna hämta aktuella priser automatiskt.")

# ---------------------------------------------------------
# STRATEGIERNA (Nu med "Skicka"-knappar!)
# ---------------------------------------------------------
elif meny_val == "📈 Strategi: Trending Value":
    st.title("Trending Value 📈")
    if uppladdad_fil is not None:
        with st.spinner('Räknar ut Trending Value...'):
            df, kol_namn, kol_ticker, kol_kurs = ladda_och_tvatta_basdata(uppladdad_fil)
            KOL_PE, KOL_PS, KOL_PB, KOL_PFCF, KOL_EVEBITDA, KOL_UTDELNING = 'P/E - Senaste', 'P/S - Senaste', 'P/B - Senaste', 'P/FCF - Senaste', 'EV/EBITDA - Senaste', 'Direktav. - Senaste'
            varderings_kolumner = [KOL_PE, KOL_PS, KOL_PB, KOL_PFCF, KOL_EVEBITDA]
            
            for kol in varderings_kolumner:
                if kol in df.columns:
                    df[kol] = pd.to_numeric(df[kol], errors='coerce').fillna(5000)

            if KOL_UTDELNING in df.columns:
                df[KOL_UTDELNING] = pd.to_numeric(df[KOL_UTDELNING], errors='coerce').fillna(0)

            antal_bolag = len(df)
            rank_kolumner = []
            for kol in varderings_kolumner:
                if kol in df.columns:
                    rank_namn = f'Rank_{kol}'
                    df[rank_namn] = df[kol].rank(ascending=True, method='min')
                    rank_kolumner.append(rank_namn)

            if KOL_UTDELNING in df.columns:
                har_utdelning = df[KOL_UTDELNING] > 0
                df.loc[har_utdelning, f'Rank_{KOL_UTDELNING}'] = df.loc[har_utdelning, KOL_UTDELNING].rank(ascending=False, method='min')
                df.loc[~har_utdelning, f'Rank_{KOL_UTDELNING}'] = antal_bolag
                rank_kolumner.append(f'Rank_{KOL_UTDELNING}')

            df['Total_Rank'] = df[rank_kolumner].sum(axis=1) / len(rank_kolumner)

            kol_3m = next((c for c in df.columns if '3m' in c.lower()), None)
            kol_6m = next((c for c in df.columns if '6m' in c.lower()), None)
            kol_12m = next((c for c in df.columns if '1år' in c.lower() or '12m' in c.lower()), None)

            for kol in [kol_3m, kol_6m, kol_12m]:
                if kol: df[kol] = pd.to_numeric(df[kol], errors='coerce').fillna(0)

            df['Sammansatt_Momentum'] = (df[kol_3m] + df[kol_6m] + df[kol_12m]) / 3
            topp_40 = df.nsmallest(40, 'Total_Rank').sort_values(by='Sammansatt_Momentum', ascending=False)
            vy_kolumner = [kol_namn, kol_ticker, kol_kurs, 'Sammansatt_Momentum', 'Total_Rank']
            
            st.subheader("🚀 Topp 10 Köpkandidater")
            st.dataframe(topp_40[vy_kolumner].head(10).reset_index(drop=True), use_container_width=True)
            
            # MAGISK KNAPP FÖR ATT SKICKA TILL OMBALANSERING
            if st.button("⚡ Skicka Topp 10 till Ombalansering", key="btn_val"):
                mal = topp_40[[kol_namn, kol_ticker, kol_kurs]].head(10).copy()
                mal.columns = ["Bolagsnamn", "Ticker", "Kurs"]
                st.session_state['mal_portfolj'] = mal.reset_index(drop=True)
                st.success("✅ Målaktierna är sparade i minnet! Klicka på fliken Ombalansering i menyn.")
    else:
        st.warning("👈 Ladda upp fil i menyn.")

elif meny_val == "💸 Strategi: Trend. Utdelning":
    st.title("Trendande Utdelning 💸")
    if uppladdad_fil is not None:
        with st.spinner('Sållar fram direktavkastning...'):
            df, kol_namn, kol_ticker, kol_kurs = ladda_och_tvatta_basdata(uppladdad_fil)
            KOL_UTDELNING = 'Direktav. - Senaste'
            if KOL_UTDELNING in df.columns:
                df[KOL_UTDELNING] = pd.to_numeric(df[KOL_UTDELNING], errors='coerce').fillna(0)
                kol_3m = next((c for c in df.columns if '3m' in c.lower()), None)
                kol_6m = next((c for c in df.columns if '6m' in c.lower()), None)
                kol_12m = next((c for c in df.columns if '1år' in c.lower() or '12m' in c.lower()), None)

                for kol in [kol_3m, kol_6m, kol_12m]:
                    if kol: df[kol] = pd.to_numeric(df[kol], errors='coerce').fillna(0)

                df['Sammansatt_Momentum'] = (df[kol_3m] + df[kol_6m] + df[kol_12m]) / 3
                topp_40 = df.nlargest(40, KOL_UTDELNING).sort_values(by='Sammansatt_Momentum', ascending=False)
                vy_kolumner = [kol_namn, kol_ticker, kol_kurs, KOL_UTDELNING, 'Sammansatt_Momentum']
                
                st.subheader("🚀 Topp 10 Köpkandidater")
                st.dataframe(topp_40[vy_kolumner].head(10).reset_index(drop=True), use_container_width=True)
                
                # MAGISK KNAPP 
                if st.button("⚡ Skicka Topp 10 till Ombalansering", key="btn_utd"):
                    mal = topp_40[[kol_namn, kol_ticker, kol_kurs]].head(10).copy()
                    mal.columns = ["Bolagsnamn", "Ticker", "Kurs"]
                    st.session_state['mal_portfolj'] = mal.reset_index(drop=True)
                    st.success("✅ Målaktierna är sparade i minnet! Klicka på fliken Ombalansering.")
    else:
        st.warning("👈 Ladda upp fil i menyn.")

elif meny_val == "⚡ Strategi: Momentum":
    st.title("Sammansatt Momentum ⚡")
    if uppladdad_fil is not None:
        with st.spinner('Rankar efter rent momentum...'):
            df, kol_namn, kol_ticker, kol_kurs = ladda_och_tvatta_basdata(uppladdad_fil)
            kol_3m = next((c for c in df.columns if '3m' in c.lower()), None)
            kol_6m = next((c for c in df.columns if '6m' in c.lower()), None)
            kol_12m = next((c for c in df.columns if '1år' in c.lower() or '12m' in c.lower()), None)

            if all([kol_3m, kol_6m, kol_12m]):
                for kol in [kol_3m, kol_6m, kol_12m]:
                    df[kol] = pd.to_numeric(df[kol], errors='coerce').fillna(0)

                df['Sammansatt_Momentum'] = (df[kol_3m] + df[kol_6m] + df[kol_12m]) / 3
                df_sorterad = df.sort_values(by='Sammansatt_Momentum', ascending=False)
                vy_kolumner = [kol_namn, kol_ticker, kol_kurs, 'Sammansatt_Momentum']
                
                st.subheader("🚀 Topp 10 Köpkandidater")
                st.dataframe(df_sorterad[vy_kolumner].head(10).reset_index(drop=True), use_container_width=True)
                
                # MAGISK KNAPP
                if st.button("⚡ Skicka Topp 10 till Ombalansering", key="btn_mom"):
                    mal = df_sorterad[[kol_namn, kol_ticker, kol_kurs]].head(10).copy()
                    mal.columns = ["Bolagsnamn", "Ticker", "Kurs"]
                    st.session_state['mal_portfolj'] = mal.reset_index(drop=True)
                    st.success("✅ Målaktierna är sparade i minnet! Klicka på fliken Ombalansering.")
    else:
        st.warning("👈 Ladda upp fil i menyn.")

# ---------------------------------------------------------
# OMBALANSERING (Nu helt automatisk!)
# ---------------------------------------------------------
# ---------------------------------------------------------
# OMBALANSERING (Nu helt automatisk!)
# ---------------------------------------------------------
elif meny_val == "⚖️ Ombalansering":
    st.title("Portföljombalansering ⚖️")
    st.write("*(Dina aktier laddas nu in helt automatiskt från minnet)*")
    
    kassa = st.number_input("Nysparande / Ledig Kassa att tillföra (SEK)", min_value=0.0, value=10000.0, step=1000.0)
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("1. Din Befintliga Portfölj")
        st.dataframe(st.session_state['bef_portfolj'], use_container_width=True)
        
    with col2:
        st.subheader("2. Dina Nya Målaktier (Topp 10)")
        redigerad_mal = st.data_editor(st.session_state['mal_portfolj'], num_rows="dynamic", use_container_width=True, key="edit_mal")
        st.session_state['mal_portfolj'] = redigerad_mal
        
    if st.button("⚡ Beräkna ombalansering", type="primary"):
        df_bef = pd.DataFrame(st.session_state['bef_portfolj'])
        df_mal = pd.DataFrame(st.session_state['mal_portfolj'])
        
        # 1. Städa bort helt tomma rader (där Ticker saknas eller är blank)
        df_bef = df_bef.dropna(subset=['Ticker'])
        df_bef = df_bef[df_bef['Ticker'].astype(str).str.strip() != '']
        
        df_mal = df_mal.dropna(subset=['Ticker'])
        df_mal = df_mal[df_mal['Ticker'].astype(str).str.strip() != '']
        
        # 2. Snygga till Tickers så de matchar (stora bokstäver, inga mellanslag)
        df_bef['Ticker'] = df_bef['Ticker'].astype(str).str.upper().str.strip()
        df_mal['Ticker'] = df_mal['Ticker'].astype(str).str.upper().str.strip()
        
        # 3. Tvinga Antal och Kurs att bli riktiga siffror (ersätt tomt strunt med 0)
        if 'Antal' in df_bef.columns:
            df_bef['Antal'] = pd.to_numeric(df_bef['Antal'], errors='coerce').fillna(0)
        if 'Kurs' in df_bef.columns:
            df_bef['Kurs'] = pd.to_numeric(df_bef['Kurs'], errors='coerce').fillna(0)
        if 'Kurs' in df_mal.columns:
            df_mal['Kurs'] = pd.to_numeric(df_mal['Kurs'], errors='coerce').fillna(0)
        
        # Beräkna värden
        if not df_bef.empty:
            df_bef['Värde'] = df_bef['Antal'] * df_bef['Kurs']
            aktie_varde = df_bef['Värde'].sum()
        else:
            aktie_varde = 0
            
        totalt_varde = aktie_varde + kassa
        antal_mal = len(df_mal)
        
        if antal_mal > 0:
            mal_varde_per_aktie = totalt_varde / antal_mal
            st.metric("Totalt Portföljvärde (inkl. kassa)", f"{totalt_varde:,.0f} kr")
            st.metric("Målvärde per aktie (Lika vikt)", f"{mal_varde_per_aktie:,.0f} kr")
            st.markdown("---")
            
            ordrar = []
            # Kolla vilka aktier vi äger som inte är målaktier (Sälj allt)
            for _, r in df_bef.iterrows():
                if r['Ticker'] not in df_mal['Ticker'].values:
                    ordrar.append({"Bolagsnamn": r['Bolagsnamn'], "Ticker": r['Ticker'], "Handling": "🔴 SÄLJ ALLT", "Antal aktier": int(r['Antal']), "Kurs": r['Kurs']})
            
            # Kolla målaktierna och jämför med vad vi har
            for _, r in df_mal.iterrows():
                ticker = r['Ticker']
                kurs = float(r['Kurs'])
                namn = r['Bolagsnamn']
                # Skydda mot nolldivision om kursen saknas
                mal_antal = int(mal_varde_per_aktie // kurs) if kurs > 0 else 0 
                
                match = df_bef[df_bef['Ticker'] == ticker]
                
                if not match.empty:
                    nuv_antal = int(match['Antal'].iloc[0])
                    diff = mal_antal - nuv_antal
                    if diff > 0:
                        ordrar.append({"Bolagsnamn": namn, "Ticker": ticker, "Handling": "🔵 KÖP MER", "Antal aktier": int(diff), "Kurs": kurs})
                    elif diff < 0:
                        ordrar.append({"Bolagsnamn": namn, "Ticker": ticker, "Handling": "🟡 SÄLJ AV", "Antal aktier": int(abs(diff)), "Kurs": kurs})
                else:
                    ordrar.append({"Bolagsnamn": namn, "Ticker": ticker, "Handling": "🟢 KÖP NY", "Antal aktier": int(mal_antal), "Kurs": kurs})
                    
            st.subheader("🛒 Köp- och säljinstruktioner:")
            if ordrar:
                st.dataframe(pd.DataFrame(ordrar), use_container_width=True)
        else:
            st.info("Inga målaktier hittades. Ladda in dem från en strategi först!")
