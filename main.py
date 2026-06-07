import os
import json
import datetime
import random
import sys
import re
import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

def extract_count_from_html(html, key_name):
    """HTMLソースから特定のカウント数（例: followers_count）の数値を正確に抜き出す関数"""
    # 例: "followers_count":78841 や "followers_count": 78841 を狙い撃ち
    pattern = rf'"{key_name}"\s*:\s*(\d+)'
    match = re.search(pattern, html)
    if match:
        return int(match.group(1))
    return 0

def scrape_to_sheets():
    print("Step 1: プログラムを開始しました")
    
    # --- 1. Google Sheets APIの認証 ---
    try:
        scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        env_key = os.environ.get("GCP_JSON_KEY")
        info = json.loads(env_key)
        creds = Credentials.from_service_account_info(info, scopes=scopes)
        client = gspread.authorize(creds)
        
        sheet_id = os.environ.get("SPREADSHEET_ID")
        sh = client.open_by_key(sheet_id)
        ws = sh.get_worksheet(0) 
        print(f"🎯 スプレッドシート接続成功: {sh.title} / {ws.title}")
    except Exception as e:
        print(f"❌ Google Sheets 接続エラー: {e}")
        return

    # --- 2. ターゲットの読み込み ---
    input_csv = "targets.csv"
    if not os.path.exists(input_csv):
        print(f"❌ エラー: {input_csv} が見つかりません。")
        return
    with open(input_csv, 'r') as f:
        usernames = [line.strip() for line in f if line.strip()]
    
    print(f"📋 読み込んだアカウント数: {len(usernames)} 件")
    now_str = datetime.datetime.now().strftime("%Y-%m-%d")
    
    # --- 3. Xのスクレイピング（生ソース直接解剖版） ---
    print("Step 2: Playwright を起動します...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        for username in usernames:
            print(f"🔍 調査開始: @{username}")
            
            try:
                # ページへ移動してHTMLソースが生成されるのを待つ
                page.goto(f"https://x.com/{username}", wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(4000)
                
                # 画面の表示文字ではなく、裏にある「生HTMLソース」を丸ごと取得
                raw_html = page.content()
                
                # HTML内の INITIAL_STATE からダイレクトに数値を抽出
                followers_num = extract_count_from_html(raw_html, "followers_count")
                following_num = extract_count_from_html(raw_html, "friends_count")
                posts_num = extract_count_from_html(raw_html, "statuses_count")

                # もしうまく取れない場合の保険（別キー名のパターン）
                if followers_num == 0:
                    followers_num = extract_count_from_html(raw_html, "followersCount")
                if following_num == 0:
                    following_num = extract_count_from_html(raw_html, "friendsCount")

                if followers_num > 0 or following_num > 0:
                    # スプレッドシートに追記
                    ws.append_row([now_str, username, following_num, followers_num, posts_num])
                    print(f" ✅ Success: {username} (Followers: {followers_num:,}, Following: {following_num:,}, Posts: {posts_num:,})")
                else:
                    print(f" ❌ Failed: {username} (生HTML内に数値が見つかりませんでした)")

            except Exception as e:
                print(f" ⚠️ 解析エラー: @{username} - {e}")

            page.wait_for_timeout(random.randint(2000, 4000))

        browser.close()
    print("✨ すべての処理が終了しました。")

if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True)
    scrape_to_sheets()
