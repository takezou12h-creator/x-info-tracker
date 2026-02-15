import os
import json
import datetime
import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

def scrape_to_sheets():
    # 1. Google Sheets APIの認証
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    # GitHub SecretsからJSONキーを取得
    env_key = os.environ.get("GCP_JSON_KEY")
    if not env_key:
        print("Error: GCP_JSON_KEY not found")
        return
    
    info = json.loads(env_key)
    creds = Credentials.from_service_account_info(info, scopes=scopes)
    client = gspread.authorize(creds)
    
    # スプレッドシートを開く
    sheet_id = os.environ.get("SPREADSHEET_ID")
    sh = client.open_by_key(sheet_id)
    # 「総合」シートを選択（なければ作成）
    try:
        ws = sh.worksheet("総合")
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title="総合", rows="100", cols="20")
        ws.append_row(["日付", "ユーザー名", "フォロー数", "フォロワー数", "ポスト数"])

    # 2. Xのスクレイピング（前回のロジックを流用）
    results = []
    now_str = datetime.datetime.now().strftime("%Y-%m-%d")
    
    with open("targets.csv", 'r') as f:
        usernames = [line.strip() for line in f if line.strip()]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 ...")
        page = context.new_page()

        for username in usernames:
            current_data = {"followers": None, "following": None, "posts": None}
            def handle_response(res):
                if "UserByScreenName" in res.url and res.status == 200:
                    try:
                        data = res.json()
                        u = data['data']['user']['result']['legacy']
                        current_data.update({"followers": u['followers_count'], "following": u['friends_count'], "posts": u['statuses_count']})
                    except: pass

            page.on("response", handle_response)
            try:
                page.goto(f"https://x.com/{username}", wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(5000)
                if current_data["followers"] is not None:
                    # シートに1行ずつ直接追加
                    ws.append_row([now_str, username, current_data["following"], current_data["followers"], current_data["posts"]])
                    print(f"✅ Success: {username}")
            except:
                print(f"❌ Failed: {username}")
            page.remove_listener("response", handle_response)
        browser.close()

if __name__ == "__main__":
    scrape_to_sheets()
