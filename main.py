import os
import json
import datetime
import random
import sys
import re
import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

def scrape_to_sheets():
    print("🚀 X(Twitter) HTMLデバッグ版を開始しました")
    
    try:
        creds = Credentials.from_service_account_info(
            json.loads(os.environ["GCP_JSON_KEY"]), 
            scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        )
        ws = gspread.authorize(creds).open_by_key(os.environ["SPREADSHEET_ID"]).get_worksheet(0)
    except Exception as e:
        print(f"❌ スプレッドシート接続エラー: {e}")
        sys.exit(1)

    with open("targets.csv", 'r') as f:
        usernames = [line.strip() for line in f if line.strip()]
    
    now_str = datetime.datetime.now().strftime("%Y-%m-%d")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        page = context.new_page()

        for username in usernames:
            user = username.strip().replace("@", "")
            print(f"\n🔍 調査中: @{user}")
            try:
                page.goto(f"https://x.com/{user}", wait_until="domcontentloaded", timeout=40000)
                page.wait_for_timeout(6000)
                
                html = page.content()
                
                print(html)

            except Exception as e:
                print(f" ⚠️ エラー: @{user} - {e}")
            
            page.wait_for_timeout(3000)
            
        browser.close()

if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True)
    scrape_to_sheets()
