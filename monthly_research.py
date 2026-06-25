import os
import json
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
from google import genai
from tavily import TavilyClient

# ==========================================
# 1. KONFIGURERA API:ER
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

def run_research():
    print(f"🔍 Startar månadens Kvant-forskning: {datetime.now().strftime('%Y-%m-%d')}")
    manad_ar = datetime.now().strftime("%B %Y")

    # ==========================================
    # 2. SÖK PÅ INTERNET (TAVILY)
    # ==========================================
    print("🌐 Söker på internet efter kvant-trender...")
    query = f"Quantitative investing latest trends {manad_ar} value dividend momentum factor investing market sentiment"
    
    try:
        search_result = tavily_client.search(query=query, search_depth="advanced", max_results=5)
        kontext = "Här är data jag samlat in från nätet:\n\n"
        for result in search_result['results']:
            kontext += f"Titel: {result['title']}\nInnehåll: {result['content']}\n\n"
    except Exception as e:
        print(f"🚨 Fel vid sökning på internet: {e}")
        return

    # ==========================================
    # 3. ANALYSERA OCH SKRIV (GEMINI) - FALLBACK MOTOR
    # ==========================================
    print("🧠 Skickar data till AI för analys...")
    prompt = f"""
    Du är en professionell analytiker som är expert på systematisk faktorinvestering (Kvant). 
    Jag har gjort en dagsfärsk sökning på nätet om det aktuella marknadsläget ({manad_ar}).
    
    Här är informationen:
    {kontext}
    
    Ditt uppdrag:
    Skriv en sammanfattande analys på flytande svenska. Formatera texten snyggt med Markdown.
    
    Strukturera din text så här:
    1. **Marknaden just nu:** En generell överblick av sentimentet för kvantfonder.
    2. **Value (Värde):** Hur presterar/förväntas värdeaktier prestera enligt källorna?
    3. **Momentum:** Vad säger datan om momentum-faktorn? Finns det risk för krasch eller fortsätter den starkt?
    4. **Utdelning:** Finns det något nämnt om utdelningsstrategier? (Om inte, gör ett kort generellt antagande utifrån ränteläget).
    5. **Slutsats:** Vad bör jag som förvaltare tänka på inför nästa ombalansering?
    
    Var objektiv, professionell och använd emojis för att göra texten lättläst.
    """
    
    # Lista på möjliga modeller. Roboten testar dem uppifrån och ner.
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
            break # Avbryt loopen - vi har vår text!
        except Exception as e:
            print(f"❌ Modellen '{m}' nekades. Testar nästa...")
            
    if not ai_text:
        print("🚨 KATASTROF: Ingen av Googles modeller var tillgängliga. Analysen avbryts.")
        return

    # ==========================================
    # 4. SPARA TILL GOOGLE SHEETS
    # ==========================================
    print("💾 Sparar analysen till Google Sheets...")
    gc = get_gspread_client()
    sh = gc.open_by_url(os.environ["GOOGLE_SHEET_URL"])
    
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
