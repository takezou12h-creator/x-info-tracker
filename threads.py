import os
import json
import datetime
import random
import sys
import re
import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

def parse_sns_count(text_val):
    """「13.4万」「134K」などの表記を整数に変換する共通関数"""
    if not text_val or text_val == "不明":
        return 0
    cleaned = text_val.replace(",", "").strip()
    try:
        if '万' in cleaned or 'W' in cleaned or 'w' in cleaned:
            num_part = re.findall(r"[\d\.]+", cleaned)[0]
            return int(float(num_part) * 10000)
        elif 'K' in cleaned or 'k' in cleaned:
            num_part = re.findall(r"[\d\.]+", cleaned)[0]
            return int(float(num_part) * 1000)
        elif 'M' in cleaned or 'm' in cleaned:
            num_part = re.findall(r"[\d\.]+", cleaned)[0]
            return int(float(num_part) * 1000000)
        else:
            num_part = re.findall(r"\d+", cleaned)[0]
            return int(num_part)
    except:
        return 0

def scrape_threads_to_sheets():
    print("🚀 Threads収集プログラムを開始しました")
    
    # --- 1. Google Sheets APIの認証 ---
    try:
        scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        env_key = os.environ.get("GCP_JSON_KEY")
        info = json.loads(env_key)
        creds = Credentials.from_service_account_info(info, scopes=scopes)
        client = gspread.authorize(creds)
        
        sheet_id = os.environ.get("SPREADSHEET_ID")
        sh = client.open_by_key(sheet_id)
        
        # 【重要】インデックス「2」を指定することで、3枚目のシート（Threads用）を取得します
        ws = sh.get_worksheet(2) 
        print(f"🎯 スプレッドシート接続成功: {sh.title} / シート名: {ws.title}")
    except Exception as e:
        print(f"❌ Google Sheets 接続エラー: {e}")
        return

    # --- 2. ターゲットの読み込み ---
    input_csv = "targets_threads.csv"
    if not os.path.exists(input_csv):
        print(f"❌ エラー: {input_csv} が見つかりません。")
        return
    with open(input_csv, 'r') as f:
        usernames = [line.strip() for line in f if line.strip()]
    
    print(f"📋 読み込んだThreadsアカウント数: {len(usernames)} 件")
    now_str = datetime.datetime.now().strftime("%Y-%m-%d")
    
    # --- 3. Playwright処理 ---
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        
        # 💡 ThreadsのセッションIDをそのまま流用します
        session_id = os.environ.get("THREADS_SESSION_ID")
        
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        # Threadsのドメインに対して共通のsessionidを注入してログイン状態にする
        if session_id:
            context.add_cookies([{
                'name': 'sessionid',
                'value': session_id,
                'domain': '.threads.net',
                'path': '/',
                'secure': True,
                'httpOnly': True
            }])
            print("🔑 Threadsのセッションを利用してThreadsにログイン状態を注入しました。")
        else:
            print("⚠️ 警告: THREADS_SESSION_ID が未設定です。")

        page = context.new_page()

        for username in usernames:
            clean_username = username.replace("https://www.threads.net/", "").replace("threads.net/", "").replace("@", "").replace("/", "")
            target_url = f"https://www.threads.net/@{clean_username}"
            
            print(f"🔍 調査開始: @{clean_username}")
            
            try:
                page.goto(target_url, wait_until="networkidle", timeout=30000)
                page.wait_for_timeout(6000) # Threadsは要素の描画が少し遅いため長めに確保
                
                raw_followers = "0"
                
                # Threadsの画面上にある「フォロワー◯人」のエリアを狙い撃ち
                try:
                    # 英語表記・日本語表記の両方に対応
                    followers_element = page.locator('span:has-text("followers"), span:has-text("フォロワー")').first
                    if followers_element.is_visible():
                        raw_text = followers_element.inner_text()
                        # 「1.2万人のフォロワー」や「12.5k followers」から不要な文字を取り除く
                        raw_followers = raw_text.replace("人のフォロワー", "").replace("フォロワー", "").replace("followers", "").strip()
                except:
                    pass

                # 整数に変換
                followers_num = parse_sns_count(raw_followers)

                # Threadsは仕様上、ログイン状態でも他人の「フォロー中」や「投稿数」が画面から隠される場合があるため
                # マーケティングにおいて最重要指標である「フォロワー数」に絞って確実に記録します
                if followers_num > 0:
                    # 3枚目のシートへ追記 (フォロー中と投稿数は一旦0として記録)
                    ws.append_row([now_str, clean_username, 0, followers_num, 0])
                    print(f" ✅ Success: {clean_username} (フォロワー: {followers_num})")
                else:
                    print(f" ❌ Failed: {clean_username} (画面上のフォロワー数を特定できませんでした)")

            except Exception as e:
                print(f" ⚠️ 通信エラー: @{clean_username} - {e}")

            page.wait_for_timeout(random.randint(4000, 7000))

        browser.close()
    print("✨ すべてのThreads処理が終了しました。")

if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True)
    scrape_threads_to_sheets()
