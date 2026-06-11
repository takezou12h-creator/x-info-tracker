import os
import json
import datetime
import random
import sys
import re
import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

def parse_clean_number(text_value):
    """『6,945』や『277』のような文字列から、純粋な数値だけを抽出する安全な共通関数"""
    if not text_value:
        return 0
    try:
        # 数字とコンマとピリオド以外をすべて消去
        cleaned = re.sub(r'[^0-9\.,]', '', text_value)
        cleaned = cleaned.replace(",", "").replace(".", "").strip()
        return int(cleaned) if cleaned else 0
    except:
        return 0

def scrape_to_sheets():
    print("🚀 X(Twitter)データ収集プログラム（要素スナイプ・最終安定版）を開始しました")
    
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
        sys.exit(1)

    # --- 2. ターゲットの読み込み ---
    input_csv = "targets.csv"
    if not os.path.exists(input_csv):
        print(f"❌ エラー: {input_csv} が見つかりません。")
        sys.exit(1)
    with open(input_csv, 'r') as f:
        usernames = [line.strip() for line in f if line.strip()]
    
    print(f"📋 読み込んだアカウント数: {len(usernames)} 件")
    
    now_str = datetime.datetime.now().strftime("%Y-%m-%d")
    success_count = 0
    
    # --- 3. Xのスクレイピング処理 ---
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()

        for username in usernames:
            clean_username = username.strip().replace("@", "")
            print(f"🔍 調査開始: @{clean_username}")
            
            followers_num = 0
            following_num = 0
            posts_num = 0
            
            try:
                page.goto(f"https://x.com/{clean_username}", wait_until="networkidle", timeout=30000)
                page.wait_for_timeout(6000) # レンダリング完了までしっかりと待機
                
                # 💡 新ロジック: 画面上の特定のaタグ要素（リンク）を直接捕まえにいく
                # 1. フォロワー数（通常または認証フォロワーのリンク要素をすべてスキャン）
                follower_elements = page.query_selector_all(f'a[href^="/{clean_username}/followers"], a[href^="/{clean_username}/verified_followers"]')
                for elem in follower_elements:
                    text = elem.inner_text()
                    if text:
                        # 内部にダミーの700が紛れ込むのを防ぐため、より詳細な「font-bold」部分があればそちらを優先
                        bold_elem = elem.query_selector('.font-bold')
                        val_str = bold_elem.inner_text() if bold_elem else text
                        val = parse_clean_number(val_str)
                        if val > 0 and val != 700:
                            followers_num = val
                            break
                        elif val > 0: # 700しか見つからない場合の保険
                            followers_num = val

                # 2. フォロー中（followingのリンク要素を直接捕まえる）
                following_element = page.query_selector(f'a[href="/{clean_username}/following"]')
                if following_element:
                    text = following_element.inner_text()
                    bold_elem = following_element.query_selector('.font-bold')
                    val_str = bold_elem.inner_text() if bold_elem else text
                    following_num = parse_clean_number(val_str)

                # 3. ポスト数（上部の件数テキストを保険として取得）
                raw_html = page.content()
                match = re.search(r'([\d.,万KMkm]+)[^<]*posts', raw_html, re.IGNORECASE)
                if match:
                    val = match.group(1).replace(",", "").upper().strip()
                    if 'K' in val: posts_num = int(float(val.replace('K', '')) * 1000)
                    elif 'M' in val: posts_num = int(float(val.replace('M', '')) * 1000000)
                    elif '万' in val: posts_num = int(float(val.replace('万', '')) * 10000)
                    else: posts_num = int(float(val))

                # 最低限どちらかが取れていれば書き込み
                if followers_num > 0 or following_num > 0:
                    ws.append_row([now_str, clean_username, following_num, followers_num, posts_num])
                    print(f" ✅ Success: {clean_username} (Followers: {followers_num:,}, Following: {following_num:,}, Posts: {posts_num:,})")
                    success_count += 1
                else:
                    print(f" ❌ Failed: {clean_username} (画面上から数値を検出できませんでした)")

            except Exception as e:
                print(f" ⚠️ エラーまたはタイムアウト: @{clean_username} - {e}")

            page.wait_for_timeout(random.randint(4000, 7000))

        browser.close()
        
    print(f"\n🏁 処理完了: {success_count} / {len(usernames)} 件の取得に成功しました。")
    if success_count == 0:
        sys.exit(1)

if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True)
    scrape_to_sheets()
