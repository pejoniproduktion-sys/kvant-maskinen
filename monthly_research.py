import os
import json
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
from google import genai
from tavily import TavilyClient

# ==========================================
# 1. KONFIGURERA API:ER & GOOGLE SHEETS
# ==========================================
tavily_client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
gemini_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

def get_gspread_client():
    creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS"])
    creds = Credentials.from_service_account_info(
        creds_dict, 
        scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    )
    return gspread.authorize(creds)

def hamta_aktuella_innehav(sh):
    print("📂 Hämtar aktuella innehav från Google Sheets för AI-granskning...")
    portfolj_text = ""
    strategier = ["Value", "Utdelning", "Momentum"]
    
    for s in strategier:
        try:
            worksheet = sh.worksheet(f"Innehav_{s}")
            data = worksheet.get_all_records()
            aktier = []
            for row in data:
                ticker = str(row.get("Ticker", "")).strip().upper()
                namn = str(row.get("Bolagsnamn", "")).strip()
                if ticker and ticker != 'KASSA':
                    aktier.append(f"- {namn} ({ticker})")
            
            if aktier:
                portfolj_text += f"\n**Strategi: {s}**\n" + "\n".join(aktier) + "\n"
        except Exception as e:
            print(f"⚠️ Kunde inte hämta innehav för {s}: {e}")
            
    if not portfolj_text.strip():
        return "Inga aktieinnehav hittades i portföljen just nu."
    return portfolj_text

def hamta_malviktning_text(manad):
    if manad in [11, 12, 1]: 
        return "Fokus: Värdestrategi (Value). Målvikt: 50% Value, 30% Utdelning, 20% Momentum. (Motivering: Bästa möjliga miljö för Värdebolag inför och under januari-effekten)."
    elif manad in [2, 3, 4]: 
        return "Fokus: Utdelning & Momentum. Målvikt: 20% Value, 40% Utdelning, 40% Momentum. (Motivering: Utdelningssäsong och kapitalrotation inför X-dagar)."
    elif manad in [5, 6, 7, 8]: 
        return "Fokus: Marknadens Vakuum (Defensivt). Målvikt: 30% Value, 30% Utdelning, 40% Momentum. (Motivering: 'Sell in May and go away', ofta låg likviditet och risk för stökig börs)."
    else: 
        return "Fokus: Momentum. Målvikt: 20% Value, 20% Utdelning, 60% Momentum. (Motivering: Likviditeten är tillbaka efter sommaren, nya starka trender etableras)."

def run_research():
    now = datetime.now()
    manad_siffra = now.month
    manad_ar = now.strftime("%B %Y")
    print(f"🔍 Startar månadens Kvant-forskning: {now.strftime('%Y-%m-%d')}")
    
    gc = get_gspread_client()
    sh = gc.open_by_url(os.environ["GOOGLE_SHEET_URL"])

    # ==========================================
    # 2. HÄMTA PORTFÖLJ, SÄSONG & SÖK PÅ INTERNET
    # ==========================================
    mina_innehav = hamta_aktuella_innehav(sh)
    sasong_text = hamta_malviktning_text(manad_siffra)
    
    print("🌐 Söker på internet efter kvant-trender...")
    query = f"Quantitative investing latest trends {manad_ar} value dividend momentum factor investing market sentiment macroeconomic outlook"
    
    try:
        search_result = tavily_client.search(query=query, search_depth="advanced", max_results=5)
        kontext = "Här är data jag samlat in från nätet:\n\n"
        for result in search_result['results']:
            kontext += f"Titel: {result['title']}\nInnehåll: {result['content']}\n\n"
    except Exception as e:
        print(f"🚨 Fel vid sökning på internet: {e}")
        return

    # ==========================================
    # 3. ANALYSERA OCH SKRIV (GEMINI)
    # ==========================================
    print("🧠 Skickar data och portföljinnehav till AI för analys...")
    prompt = f"""
    Du är en professionell analytiker som är expert på systematisk faktorinvestering (Kvant). 
    Jag har gjort en dagsfärsk sökning på nätet om det aktuella marknadsläget ({manad_ar}).
    
    Här är informationen från nätet:
    {kontext}
    
    Här är min fastslagna säsongsstrategi och målviktning för denna månad:
    {sasong_text}
    
    Här är mina nuvarande aktieinnehav uppdelade per strategi:
    {mina_innehav}
    
    Ditt uppdrag:
    Skriv en djuplodande och sammanfattande analys på flytande svenska. Formatera texten snyggt med Markdown.
    
    Strukturera din text strikt enligt följande rubriker:
    1. **Marknaden just nu:** En generell överblick av sentimentet för kvantfonder och makroläget.
    2. **Säsongsmönster vs. Rådande Makro:** Min förutbestämda säsongsstrategi är: {sasong_text}. Din uppgift är att våga IFRÅGASÄTTA detta mönster. Om din dagsfärska makroanalys pekar på att marknaden befinner sig i ett helt annat läge än vad det historiska säsongsmönstret dikterar, ska du argumentera för varför (och hur) vi bör avvika från strategin och justera vikterna för att passa verkligheten.
    3. **Djävulens Advokat - Portföljgranskning:** Granska mina specifika aktieinnehav nedan utifrån det dagsfärska marknadssentimentet och din bedömning av viktningen i punkt 2. Identifiera svagheter och varna för bolag som inte passar det aktuella klimatet.
    4. **Konkreta Råd (Köp / Sälj / Behåll):** Ge sakliga, professionella råd kring mina specifika innehav utifrån din granskning.
    5. **Slutsats:** Vad bör jag som förvaltare tänka på inför min stundande ombalansering?
    
    Var objektiv, professionell och använd emojis stilfullt för att göra texten pedagogisk och lättläst.
    """
    
    modeller_att_testa = [
        'gemini-2.5-flash',
        'gemini-2.0-flash',
        'gemini-1.5-flash-002',
        'gemini-1.5-flash',
        'gemini-1.5-pro',
        'gemini-pro'
    ]
    
    ai_text = ""
    for m in modeller_att_testa:
        try:
            print(f"⏳ Försöker ansluta till modell: {m}...")
            response = gemini_client.models.generate_content(
                model=m,
                contents=prompt,
            )
            ai_text = response.text
            print(f"✅ Succé! Modellen '{m}' accepterades och genererade analysen.")
            break 
        except Exception as e:
            print(f"❌ Modellen '{m}' nekades. Testar nästa...")
            
    if not ai_text:
        print("🚨 KATASTROF: Ingen av Googles modeller var tillgängliga. Analysen avbryts.")
        return

    # ==========================================
    # 4. SPARA TILL GOOGLE SHEETS
    # ==========================================
    print("💾 Sparar analysen till Google Sheets...")
    
    try:
        worksheet = sh.worksheet("AI_Analys")
    except:
        worksheet = sh.add_worksheet(title="AI_Analys", rows="10", cols="2")
    
    worksheet.clear()
    worksheet.update_cell(1, 1, f"Uppdaterad: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    worksheet.update_cell(2, 1, ai_text)
    
    print("🎉 Forskning klar och sparad!")

if __name__ == "__main__":
    run_research()
