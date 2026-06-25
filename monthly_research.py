import os
import json
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
import google.generativeai as genai
from tavily import TavilyClient

# ==========================================
# 1. KONFIGURERA API:ER
# ==========================================
tavily_client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
genai.configure(api_key=os.environ["GEMINI_API_KEY"])

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
    # Vi söker specifikt på akademiska termer och faktor-investering
    query = f"Quantitative investing latest trends {manad_ar} value dividend momentum factor investing market sentiment"
    
    # Hämtar de 5 bästa djupgående artiklarna/rapporterna
    search_result = tavily_client.search(query=query, search_depth="advanced", max_results=5)
    
    # Sammanställ sökresultaten till en lång textsträng som AI:n kan läsa
    kontext = "Här är data jag samlat in från nätet:\n\n"
    for result in search_result['results']:
        kontext += f"Titel: {result['title']}\nInnehåll: {result['content']}\n\n"

    # ==========================================
    # 3. ANALYSERA OCH SKRIV (GEMINI)
    # ==========================================
    print("🧠 Skickar data till AI för analys...")
    model = genai.GenerativeModel('gemini-1.5-flash')
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
    
    response = model.generate_content(prompt)
    ai_text = response.text

    # ==========================================
    # 4. SPARA TILL GOOGLE SHEETS
    # ==========================================
    print("💾 Sparar analysen till Google Sheets...")
    gc = get_gspread_client()
    sh = gc.open_by_url(os.environ["GOOGLE_SHEET_URL"])
    
    # Skapa fliken om den inte redan finns
    try:
        worksheet = sh.worksheet("AI_Analys")
    except:
        worksheet = sh.add_worksheet(title="AI_Analys", rows="10", cols="2")
    
    # Rensa fliken och skriv in det nya
    worksheet.clear()
    worksheet.update_cell(1, 1, f"Uppdaterad: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    worksheet.update_cell(2, 1, ai_text)
    
    print("🎉 Forskning klar och sparad!")

if __name__ == "__main__":
    run_research()
