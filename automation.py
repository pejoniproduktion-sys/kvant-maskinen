import os
import json
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials
import yfinance as yf
import pandas as pd

# ==========================================
# 1. KOPPLING TILL GOOGLE SHEETS VIA ENV
# ==========================================
def get_gspread_client():
    creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS"])
    creds = Credentials.from_service_account_info(
        creds_dict, 
        scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    )
    return gspread.authorize(creds)

def kor_automatisk_uppdatering():
    print(f"🚀 Startar daglig automatisering: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    gc = get_gspread_client()
    sheet_url = os.environ["GOOGLE_SHEET_URL"]
    sh = gc.open_by_url(sheet_url)
    
    strategier = ["Value", "Utdelning", "Momentum"]
    strategi_varden = {}
    ma200_varningar = [] # Här sparar vi aktier som bryter MA200
    
    # ==========================================
    # 2. UPPDATERA LIVE-KURSER OCH KOLLA MA200
    # ==========================================
    for s in strategier:
        fliknamn = f"Innehav_{s}"
        print(f"📦 Bearbetar {fliknamn}...")
        worksheet = sh.worksheet(fliknamn)
        data = worksheet.get_all_records()
        
        if not data:
            print(f"⚠️ Fliken {fliknamn} var tom eller saknas.")
            strategi_varden[s] = 0.0
            continue
            
        rader_att_spara = []
        totalt_varde_strategi = 0.0
        
        for row in data:
            namn = row.get("Bolagsnamn", "")
            ticker = str(row.get("Ticker", "")).upper().replace(" SEK", "").strip()
            antal = 0
            
            try:
                antal = int(str(row.get("Antal", "0")).replace("'", ""))
            except:
                pass
                
            if not ticker:
                continue
                
            # Om det är kassa ska vi inte hämta kurser från Yahoo
            if ticker == 'KASSA':
                kassa_kurs = float(str(row.get("Kurs", "0")).replace("'", "").replace(",", "."))
                totalt_varde_strategi += kassa_kurs
                rader_att_spara.append([namn, ticker, "1", f"'{kassa_kurs:.2f}"])
                continue
                
            # Yahoo-formatering (ex: SSAB B -> SSAB-B.ST)
            t_formatted = ticker.replace(" ", "-")
            yf_ticker = t_formatted if "." in t_formatted else f"{t_formatted}.ST"
            
            ny_kurs = 0.0
            try:
                aktie = yf.Ticker(yf_ticker)
                # Hämtar 1 års historik för att både få dagens kurs och kunna räkna ut MA200
                hist = aktie.history(period="1y")
                if not hist.empty:
                    ny_kurs = round(float(hist['Close'].iloc[-1]), 2)
                    print(f"✅ {ticker}: {ny_kurs} kr")
                    
                    # Beräkna MA200
                    if len(hist) >= 150:
                        ma200 = round(float(hist['Close'].tail(200).mean()), 2)
                        if ny_kurs < ma200:
                            avvikelse = ((ny_kurs / ma200) - 1) * 100
                            ma200_varningar.append([s, namn, ticker, f"{ny_kurs:.2f}", f"{ma200:.2f}", f"{avvikelse:.1f}%"])
                else:
                    ny_kurs = float(str(row.get("Kurs", "0")).replace("'", "").replace(",", "."))
            except Exception as e:
                print(f"❌ Fel vid hämtning av {ticker}: {e}")
                ny_kurs = float(str(row.get("Kurs", "0")).replace("'", "").replace(",", "."))
                
            totalt_varde_strategi += (antal * ny_kurs)
            kurs_str = f"'{ny_kurs:.2f}"
            rader_att_spara.append([namn, ticker, str(antal), kurs_str])
            
        # Spara tillbaka till fliken
        worksheet.clear()
        worksheet.append_row(["Bolagsnamn", "Ticker", "Antal", "Kurs"])
        if rader_att_spara:
            worksheet.append_rows(rader_att_spara, value_input_option='USER_ENTERED')
            
        strategi_varden[s] = totalt_varde_strategi

    # ==========================================
    # 3. SPARA MA200-VARNINGAR TILL EN EGEN FLIK
    # ==========================================
    print("🚨 Sparar MA200-varningar...")
    try:
        worksheet_warn = sh.worksheet("MA200_Varningar")
    except:
        worksheet_warn = sh.add_worksheet(title="MA200_Varningar", rows="50", cols="6")
        
    worksheet_warn.clear()
    worksheet_warn.append_row(["Strategi", "Bolagsnamn", "Ticker", "Kurs", "MA200", "Avvikelse"])
    if ma200_varningar:
        worksheet_warn.append_rows(ma200_varningar, value_input_option='USER_ENTERED')
    print(f"📊 Hittade {len(ma200_varningar)} stycken aktier under MA200.")

    # ==========================================
    # 4. HÄMTA OMXSPI OCH LOGGA I HISTORIKEN
    # ==========================================
    print("📈 Hämtar dagsaktuellt OMXSPI-index...")
    omx_stangning = 0.0
    try:
        omx = yf.Ticker("^OMXSPI")
        hist_omx = omx.history(period="1d")
        if not hist_omx.empty:
            omx_stangning = round(float(hist_omx['Close'].iloc[-1]), 2)
    except Exception as e:
        print(f"❌ Kunde inte hämta OMXSPI: {e}")

    v_val = strategi_varden.get("Value", 0.0)
    v_utd = strategi_varden.get("Utdelning", 0.0)
    v_mom = strategi_varden.get("Momentum", 0.0)
    total_portfolj = v_val + v_utd + v_mom
    datum_str = datetime.now().strftime("%Y-%m-%d")
    
    worksheet_hist = sh.worksheet("Historik")
    data_hist = worksheet_hist.get_all_values()
    
    found_row = None
    if data_hist:
        for i, row in enumerate(data_hist[1:]):
            if row and row[0] == datum_str:
                found_row = i + 2
                break
                
    if found_row:
        worksheet_hist.update_cell(found_row, 2, f"'{v_val:.2f}")
        worksheet_hist.update_cell(found_row, 3, f"'{v_utd:.2f}")
        worksheet_hist.update_cell(found_row, 4, f"'{v_mom:.2f}")
        worksheet_hist.update_cell(found_row, 5, f"'{total_portfolj:.2f}")
        worksheet_hist.update_cell(found_row, 6, f"'{omx_stangning:.2f}")
    else:
        worksheet_hist.append_row([
            datum_str, 
            f"'{v_val:.2f}", 
            f"'{v_utd:.2f}", 
            f"'{v_mom:.2f}", 
            f"'{total_portfolj:.2f}", 
            f"'{omx_stangning:.2f}"
        ], value_input_option='USER_ENTERED')
        
    print("🎉 Automatiseringen kördes utan problem!")

if __name__ == "__main__":
    kor_automatisk_uppdatering()
