import os
import json
import datetime
import random
import sys
import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

def scrape_to_sheets():
    print("Step 1: プログラムを開始しました")
    
    # --- 1. Google Sheets APIの認証 ---
    try:
        scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        env_key = os.environ.get("GCP_JSON_KEY")
        if not env_key:
            print("❌ エラー: GCP_JSON_KEY が環境変数に見つかりません。")
            return
            
        info = json.loads(env_key)
        creds = Credentials.from_service_account_info(info, scopes=scopes)
        client = gspread.authorize(creds)
        
        sheet_id = os.environ.get("SPREADSHEET_ID")
        if not sheet_id:
            print("❌ エラー: SPREADSHEET_ID が環境変数に見つかりません。")
            return
            
        sh = client.open_by_key(sheet_id)
        ws = sh.get_worksheet(0) 
        print(f"🎯 スプレッドシート接続成功: {sh.title} / {ws.title}")

    except Exception as e:
        print(f"❌ Google Sheets 接続エラー: {e}")
        # 詳細なエラー情報を出すために例外を発生させて強制終了させる
        raise e

    # --- 2. ターゲットの読み込み ---
    input_csv = "targets.csv"
    if not os.path.exists(input_csv):
        print(f"❌ エラー: {input_csv} が見つかりません。現在のディレクトリのファイル一覧:")
        print(os.listdir("."))
        return
    
    with open(input_csv, 'r') as f:
        usernames = [line.strip() for line in f if line.strip()]
    
    print(f"📋 読み込んだアカウント数: {len(usernames)} 件")
    if not usernames:
        print("⚠️ 調査対象のアカウントがCSVに記述されていません。")
        return

    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # --- 3. Xのスクレイピング ---
    print("Step 2: Playwright を起動します...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        for username in usernames:
            print(f"🔍 調査開始: @{username}")
            current_data = {"followers": None, "following": None, "posts": None}

            def handle_response(res):
                if "UserByScreenName" in res.url and res.status == 200:
                    try:
                        data = res.json()
                        user_result = data.get('data', {}).get('user', {}).get('result', {})
                        
                        if 'legacy' in user_result:
                            u = user_result['legacy']
                        elif 'user' in user_result and 'legacy' in user_result['user']:
                            u = user_result['user']['legacy']
                        else:
                            u = None
                        
                        if u:
                            current_data.update({
                                "followers": u.get('followers_count'),
                                "following": u.get('friends_count'),
                                "posts": u.get('statuses_count')
                            })
                    except Exception as e:
                        print(f" ⚠️ レスポンス解析失敗: {e}")

            page.on("response", handle_response)
            
            try:
                page.goto(f"https://x.com/{username}", wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(5000)
                
                if current_data["followers"] is not None:
                    ws.append_row([
                        now_str, 
                        username, 
                        current_data["following"], 
                        current_data["followers"], 
                        current_data["posts"]
                    ])
                    print(f" ✅ Success: {username} ({current_data['followers']} followers)")
                else:
                    print(f" ❌ Failed: {username} (データが取得できませんでした)")

            except Exception as e:
                print(f" ⚠️ 通信エラー: @{username} - {e}")

            page.remove_listener("response", handle_response)
            page.wait_for_timeout(random.randint(2000, 5000))

        browser.close()

    print("✨ すべての処理が終了しました。")

if __name__ == "__main__":
    # ログが出力バッファに溜まって消えるのを防ぐ設定
    sys.stdout.reconfigure(line_buffering=True)
    scrape_to_sheets()
