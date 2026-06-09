import os
import json
import datetime
import random
import sys
import re
import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

def extract_count_from_raw_html(html, key_name):
    """
    Threadsの生HTMLソースコードから特定のカウント数（例: edge_followed_by）の
    1桁単位の生数値を正規表現で直接ぶっこ抜く関数
    """
    # 例: "edge_followed_by":{"count":10457} や "edge_followed_by":{"count": 10457} を狙い撃ち
    pattern = rf'"{key_name}"\s*:\s*\{\s*"count"\s*:\s*(\d+)'
    match = re.search(pattern, html)
    if match:
        return int(match.group(1))
    return 0

def scrape_threads_to_sheets():
    print("🚀 Threads収集プログラム（生ソース直接解剖版）を開始しました")
    
    # --- 1. Google Sheets APIの認証 ---
    try:
        scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        env_key = os.environ.get("GCP_JSON_KEY")
        info = json.loads(env_key)
        creds = Credentials.from_service_account_info(info, scopes=scopes)
        client = gspread.authorize(creds)
        
        sheet_id = os.environ.get("SPREADSHEET_ID")
        sh = client.open_by_key(sheet_id)
        
        # 3枚目のシート
        ws = sh.get_worksheet(2) 
        print(f"🎯 スプレッドシート接続成功: {sh.title} / シート名: {ws.title}")
    except Exception as e:
        print(f"❌ Google Sheets 接続エラー: {e}")
        sys.exit(1)

    # --- 2. ターゲットの読み込み ---
    input_csv = "targets_threads.csv"
    if not os.path.exists(input_csv):
        print(f"❌ エラー: {input_csv} が見つかりません。")
        sys.exit(1)
    with open(input_csv, 'r') as f:
        usernames = [line.strip() for line in f if line.strip()]
    
    print(f"📋 読み込んだThreadsアカウント数: {len(usernames)} 件")
    now_str = datetime.datetime.now().strftime("%Y-%m-%d")
    
    success_count = 0
    
    # --- 3. Playwright処理 ---
    print("Step 2: Playwright を起動します...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        
        # Threads専用のセッションID（Cookie）
        session_id = os.environ.get("THREADS_SESSION_ID")
        
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        # ログイン状態の注入
        if session_id:
            context.add_cookies([{
                'name': 'sessionid',
                'value': session_id,
                'domain': '.threads.net',
                'path': '/',
                'secure': True,
                'httpOnly': True
            }])
            print("🔑 ログインセッションをブラウザに注入しました。")
        else:
            print("⚠️ 警告: THREADS_SESSION_ID が未設定です。")

        page = context.new_page()

        for username in usernames:
            clean_username = username.replace("https://www.threads.net/", "").replace("threads.net/", "").replace("@", "").replace("/", "")
            target_url = f"https://www.threads.net/@{clean_username}"
            
            print(f"🔍 調査開始: @{clean_username}")
            
            try:
                # ページへ移動
                # domcontentloaded（HTML構造の読み込み完了）まででOK
                page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(4000)
                
                # 画面の表示文字ではなく、裏にある「生HTMLソース」を丸ごと取得
                raw_html = page.content()
                
                # 💡 HTML内の JSONデータからダイレクトに1桁単位の生数値を抽出
                # マーケティング上重要なフォロワー数、フォロー数、投稿数を取得
                followers_num = extract_count_from_raw_html(raw_html, "edge_followed_by")
                following_num = extract_count_from_raw_html(raw_html, "edge_follow")
                posts_num = extract_count_from_raw_html(raw_html, "edge_owner_to_timeline_media")

                # もしうまく取れない場合の保険（一般用メタテキストからの抽出）
                if followers_num == 0:
                    try:
                        # 例: <meta property="og:description" content="10.4k Followers, ..."/>
                        meta_text = page.locator('meta[property="og:description"]').get_attribute("content")
                        if meta_text:
                            print(f" ℹ️ メタデータから抽出を試みます: {meta_text}")
                            match = re.search(r'([\d.,万KM]+)\s*Followers', meta_text, re.IGNORECASE)
                            if match:
                                # 簡易的な変換（丸められた数値になります）
                                val = match.group(1).replace(',', '')
                                if '万' in val: followers_num = int(float(val.replace('万', '')) * 10000)
                                elif 'K' in val: followers_num = int(float(val.replace('K', '')) * 1000)
                                else: followers_num = int(val)
                    except:
                        pass

                # スプレッドシートに追記（int型で渡すことでコンマなしの綺麗な数値になります）
                if followers_num > 0 or following_num > 0:
                    # 3枚目のシートへ追記
                    ws.append_row([now_str, clean_username, following_num, followers_num, posts_num])
                    print(f" ✅ Success: {clean_username} (Followers: {followers_num:,}, Following: {following_num:,}, Posts: {posts_num:,})")
                    success_count += 1
                else:
                    print(f" ❌ Failed: {clean_username} (生HTML内に数値が見つかりませんでした)")

            except Exception as e:
                print(f" ⚠️ 解析エラー: @{clean_username} - {e}")

            page.wait_for_timeout(random.randint(4000, 7000))

        browser.close()
        
    # --- 4. 運行チェック（エラー通知用） ---
    print(f"🏁 処理完了: {success_count} / {len(usernames)} 件の取得に成功しました。")
    
    if success_count == 0 and len(usernames) > 0:
        print("❌ 致命的エラー: 全てのアカウントでデータ取得に失敗したため、システムを異常終了します。")
        sys.exit(1)
        
    print("✨ すべてのThreads処理が正常終了しました。")

if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True)
    scrape_threads_to_sheets()
