import streamlit as st
import pandas as pd
import numpy as np
import os
import sqlite3
import yfinance as yf
from datetime import datetime, timedelta

# ==========================================
# 1. APPENS INSTÄLLNINGAR & DATABAS
# ==========================================
st.set_page_config(page_title="Kvant-Maskinen v1.0", page_icon="🚀", layout="wide")

DB_NAMN = 'kvant_historik.db'

def initiera_databas():
    conn = sqlite3.connect(DB_NAMN)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS portfolj_historik (
            datum TEXT PRIMARY KEY,
            portfolj_varde REAL,
            omx_index REAL
        )
    ''')
    conn.commit()
    conn.close()

initiera_databas()

# ==========================================
# 2. SIDOMENY OCH DELAD DATALADDNING
# ==========================================
st.sidebar.title("Kvant-Maskinen 🚀")
st.sidebar.markdown("---")

meny_val = st.sidebar.radio(
    "Välj vy:",
    [
        "📊 Översikt & Historik", 
        "📈 Strategi: Trending Value", 
        "💸 Strategi: Trend. Utdelning", 
        "⚡ Strategi: Momentum", 
        "⚖️ Ombalansering"
    ]
)

st.sidebar.markdown("---")
st.sidebar.info("Ladda upp din senaste Excel- eller CSV-export från Börsdata nedan för att köra strategierna.")
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

# ---------------------------------------------------------
# ÖVERSIKT & HISTORIK (SQLite + Yahoo Finance)
# ---------------------------------------------------------
if meny_val == "📊 Översikt & Historik":
    st.title("📊 Portföljöversikt & Historisk Utveckling")
    
    # Formulär för att lägga till historik
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
                            
                            conn = sqlite3.connect(DB_NAMN)
                            c = conn.cursor()
                            c.execute('INSERT OR REPLACE INTO portfolj_historik VALUES (?, ?, ?)', (datum_str, portfolj_kronor, omx_stangning))
                            conn.commit()
                            conn.close()
                            st.success(f"Loggat! Portfölj: {portfolj_kronor:,.0f} kr, OMXSPI: {omx_stangning:.2f}")
                        else:
                            st.error("Kunde inte hitta indexkurs för detta specifika datum (kanske helgdag?). Prova en närliggande vardag.")
                    except Exception as e:
                        st.error(f"Ett fel uppstod vid hämtning av data: {e}")

    # Visa grafen om det finns data
    conn = sqlite3.connect(DB_NAMN)
    hist_df = pd.read_sql_query("SELECT * FROM portfolj_historik ORDER BY datum ASC", conn)
    conn.close()
    
    if len(hist_df) >= 1:
        st.subheader("📈 Utveckling jämfört med OMX Stockholm PI")
        
        # Om vi har minst 2 datapunkter kan vi indexera till 100% för rättvis jämförelse
        if len(hist_df) >= 2:
            hist_df['Portfölj (%)'] = (hist_df['portfolj_varde'] / hist_df['portfolj_varde'].iloc[0]) * 100 - 100
            hist_df['OMX Stockholm PI (%)'] = (hist_df['omx_index'] / hist_df['omx_index'].iloc[0]) * 100 - 100
            
            graf_df = hist_df.set_index('datum')[['Portfölj (%)', 'OMX Stockholm PI (%)']]
            st.line_chart(graf_df)
        else:
            st.info("Logga minst två datapunkter över tid för att rita jämförelsegrafen i procent. Just nu visas rådatan nedan.")
            
        st.subheader("Historiktabell")
        st.dataframe(hist_df.rename(columns={'datum':'Datum', 'portfolj_varde':'Portföljvärde (SEK)', 'omx_index':'OMXSPI Index'}), use_container_width=True)
        
        if st.button("Radera all historik och rensa databasen"):
            conn = sqlite3.connect(DB_NAMN)
            c = conn.cursor()
            c.execute("DELETE FROM portfolj_historik")
            conn.commit()
            conn.close()
            st.rerun()
    else:
        st.warning("Databasen är tom. Öppna fliken ovan för att lägga till ditt första portföljvärde!")

# ---------------------------------------------------------
# TRENDING VALUE
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
                    df[kol] = pd.to_numeric(df[kol], errors='coerce')
                    df.loc[df[kol] < 0, kol] = 5000
                    df[kol] = df[kol].fillna(5000)

            if KOL_UTDELNING in df.columns:
                df[KOL_UTDELNING] = pd.to_numeric(df[KOL_UTDELNING], errors='coerce').fillna(0)

            antal_kvarvarande_bolag = len(df)
            rank_kolumner = []
            for kol in varderings_kolumner:
                if kol in df.columns:
                    rank_namn = f'Rank_{kol}'
                    df[rank_namn] = df[kol].rank(ascending=True, method='min')
                    rank_kolumner.append(rank_namn)

            if KOL_UTDELNING in df.columns:
                rank_utdelning = f'Rank_{KOL_UTDELNING}'
                har_utdelning = df[KOL_UTDELNING] > 0
                df.loc[har_utdelning, rank_utdelning] = df.loc[har_utdelning, KOL_UTDELNING].rank(ascending=False, method='min')
                df.loc[~har_utdelning, rank_utdelning] = antal_kvarvarande_bolag
                rank_kolumner.append(rank_utdelning)

            df['Total_Rank'] = df[rank_kolumner].sum(axis=1) / len(rank_kolumner)

            kol_3m = next((c for c in df.columns if '3m' in c.lower()), None)
            kol_6m = next((c for c in df.columns if '6m' in c.lower()), None)
            kol_12m = next((c for c in df.columns if '1år' in c.lower() or '12m' in c.lower()), None)

            for kol in [kol_3m, kol_6m, kol_12m]:
                if kol: df[kol] = pd.to_numeric(df[kol], errors='coerce').fillna(0)

            df['Sammansatt_Momentum'] = (df[kol_3m] + df[kol_6m] + df[kol_12m]) / 3

            topp_40 = df.nsmallest(40, 'Total_Rank').copy()
            topp_40_sorterad = topp_40.sort_values(by='Sammansatt_Momentum', ascending=False)

            vy_kolumner = [kol_namn, kol_ticker, kol_kurs, 'Sammansatt_Momentum', 'Total_Rank']
            st.subheader("🚀 Topp 10 Köpkandidater")
            st.dataframe(topp_40_sorterad[vy_kolumner].head(10).reset_index(drop=True), use_container_width=True)
            
            with st.expander("Visa Topp 40 Värdebolag"):
                st.dataframe(topp_40_sorterad[vy_kolumner].reset_index(drop=True), use_container_width=True)
            with st.expander("Visa Hela Rådatan (Sorterad på prisvärdhet)"):
                st.dataframe(df.sort_values(by='Total_Rank')[vy_kolumner + rank_kolumner].reset_index(drop=True), use_container_width=True)
    else:
        st.warning("👈 Vänligen ladda upp din Excel-fil från Börsdata i sidomenyn.")

# ---------------------------------------------------------
# TRENDANDE UTDELNING
# ---------------------------------------------------------
elif meny_val == "💸 Strategi: Trend. Utdelning":
    st.title("Trendande Utdelning 💸")
    
    if uppladdad_fil is not None:
        with st.spinner('Sållar fram högsta direktavkastningen och rankar efter momentum...'):
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
                
                # Topp 40 med högst utdelning, sorterat på momentum
                topp_40_utd = df.nlargest(40, KOL_UTDELNING).copy()
                topp_40_utd_sorterad = topp_40_utd.sort_values(by='Sammansatt_Momentum', ascending=False)
                
                vy_kolumner = [kol_namn, kol_ticker, kol_kurs, KOL_UTDELNING, 'Sammansatt_Momentum']
                st.subheader("🚀 Topp 5-10 Köpkandidater (Trendande Utdelning)")
                st.dataframe(topp_40_utd_sorterad[vy_kolumner].head(10).reset_index(drop=True), use_container_width=True)
                
                with st.expander("Visa hela Rådatan"):
                    st.dataframe(df.sort_values(by=KOL_UTDELNING, ascending=False)[vy_kolumner], use_container_width=True)
            else:
                st.error(f"Kunde inte hitta kolumnen '{KOL_UTDELNING}' i filen.")
    else:
        st.warning("👈 Ladda upp filen i sidomenyn.")

# ---------------------------------------------------------
# SAMMANSATT MOMENTUM
# ---------------------------------------------------------
elif meny_val == "⚡ Strategi: Momentum":
    st.title("Sammansatt Momentum ⚡")
    
    if uppladdad_fil is not None:
        with st.spinner('Rankar marknaden efter rent momentum...'):
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
                st.subheader("🚀 Topp 5-10 Köpkandidater (Sammansatt Momentum)")
                st.dataframe(df_sorterad[vy_kolumner].head(10).reset_index(drop=True), use_container_width=True)
            else:
                st.error("Filen saknar nödvändiga kolumner för 3m, 6m eller 1år momentum.")
    else:
        st.warning("👈 Ladda upp filen i sidomenyn.")

# ---------------------------------------------------------
# INTERAKTIV OMBALANSERING (Helt utan Excel-krav!)
# ---------------------------------------------------------
elif meny_val == "⚖️ Ombalansering":
    st.title("Portföljombalansering ⚖️")
    st.write("Skriv in dina siffror direkt på skärmen för att beräkna exakt köp och sälj till lika viktning.")
    
    kassa = st.number_input("Nysparande / Ledig Kassa att tillföra (SEK)", min_value=0.0, value=10000.0, step=1000.0)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("1. Din Befintliga Portfölj")
        st.markdown("*Skriv in aktierna du äger IDAG. Lägg till rader längst ned.*")
        data_bef = pd.DataFrame([
            {"Bolagsnamn": "Exempelbolag A", "Ticker": "EXA", "Antal": 100, "Kurs": 50.0}
        ])
        redigerad_bef = st.data_editor(data_bef, num_rows="dynamic", use_container_width=True)
        
    with col2:
        st.subheader("2. Dina Nya Målaktier (Topp 10)")
        st.markdown("*Skriv in aktierna du vill äga FRAMÖVER samt deras kurs.*")
        data_mal = pd.DataFrame([
            {"Bolagsnamn": "Exempelbolag A", "Ticker": "EXA", "Kurs": 50.0},
            {"Bolagsnamn": "Nytt Toppbolag B", "Ticker": "TOB", "Kurs": 120.0}
        ])
        redigerad_mal = st.data_editor(data_mal, num_rows="dynamic", use_container_width=True)
        
    if st.button("⚡ Beräkna ombalansering"):
        st.markdown("---")
        # Städa inmatning
        df_bef = pd.DataFrame(redigerad_bef).dropna(subset=['Ticker'])
        df_mal = pd.DataFrame(redigerad_mal).dropna(subset=['Ticker'])
        
        df_bef['Ticker'] = df_bef['Ticker'].astype(str).str.upper().str.strip()
        df_mal['Ticker'] = df_mal['Ticker'].astype(str).str.upper().str.strip()
        
        # Räkna ut portföljvärde
        if not df_bef.empty:
            df_bef['Värde'] = pd.to_numeric(df_bef['Antal']) * pd.to_numeric(df_bef['Kurs'])
            aktie_varde = df_bef['Värde'].sum()
        else:
            aktie_varde = 0
            
        totalt_varde = aktie_varde + kassa
        antal_mal = len(df_mal)
        
        if antal_mal == 0:
            st.error("Du måste lägga till minst en målaktie i tabell 2.")
        else:
            mal_varde_per_aktie = totalt_varde / antal_mal
            
            st.metric("Totalt Portföljvärde (inkl. kassa)", f"{totalt_varde:,.0f} kr")
            st.metric("Målvärde per aktie (Lika vikt)", f"{mal_varde_per_aktie:,.0f} kr")
            
            ordrar = []
            
            # SÄLJ ALLT
            for _, r in df_bef.iterrows():
                if r['Ticker'] not in df_mal['Ticker'].values:
                    ordrar.append({"Bolagsnamn": r['Bolagsnamn'], "Ticker": r['Ticker'], "Handling": "🔴 SÄLJ ALLT", "Antal aktier": int(r['Antal']), "Kurs": r['Kurs']})
                    
            # KÖP / JUSTERA
            for _, r in df_mal.iterrows():
                ticker = r['Ticker']
                kurs = float(r['Kurs'])
                namn = r['Bolagsnamn']
                
                mal_antal = int(mal_varde_per_aktie // kurs)
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
                st.success("Portföljen är redan perfekt balanserad!")
