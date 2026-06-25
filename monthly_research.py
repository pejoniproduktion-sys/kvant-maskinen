name: Månadsvis AI-Forskning

on:
  schedule:
    - cron: '0 8 1 * *'
  workflow_dispatch:

jobs:
  ai-research:
    runs-on: ubuntu-latest

    steps:
    - name: Check out kod
      uses: actions/checkout@v4

    - name: Installera Python
      uses: actions/setup-python@v5
      with:
        python-version: '3.11'

    - name: Installera bibliotek
      run: |
        python -m pip install --upgrade pip
        pip install gspread google-auth google-genai tavily-python

    - name: Kor AI-forskning
      env:
        GOOGLE_CREDENTIALS: ${{ secrets.GOOGLE_CREDENTIALS }}
        GOOGLE_SHEET_URL: ${{ secrets.GOOGLE_SHEET_URL }}
        TAVILY_API_KEY: ${{ secrets.TAVILY_API_KEY }}
        GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
      run: python monthly_research.py
