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
    """
    「13.4万」「134K」「1,505」のようなSNS特有の表記を
    計算可能な「純粋な整数（int）」に変換する関数
    """
    if not text_val or text_val == "不明":
        return 0
    
    # 基本的なクリーニング（コンマ、空白、前後の余計な文字を削除）
    cleaned = text_val.replace(",", "").strip()
    
    try:
        # 1. 「万」または「W」の処理 (例: 13.4万 -> 134000)
        if '万' in cleaned or 'W' in cleaned or 'w' in cleaned:
            num_part = re.findall(r"[\d\.]+", cleaned)[0]
            return int(float(num_part) * 10000)
        
        # 2. 「K」または「k」の処理 (例: 134K -> 134000)
        elif 'K' in cleaned or 'k' in cleaned:
            num_part = re.findall(r"[\d\.]+", cleaned)[0]
            return int(float(num_part) * 1000)
        
        # 3. 「M']または「m」の処理 (例: 1.2M -> 1200000)
        elif 'M' in cleaned or 'm' in cleaned:
            num_part = re.findall(r"[\d\.]+", cleaned)[0]
            return int(float(num_part) * 1000000)
        
        # 4. 通常の数字のみの場合 (例: 1505)
        else:
            num_part = re.findall(r"\d+", cleaned)[0]
            return int(num_part)
            
    except Exception as e:
        print(f" ⚠️ 数値変換エラー ({text_val}): {e}")
        return 0

def scrape_instagram_to_sheets():
    print("🚀 Instagram収集プログラム（エラー通知連動版）を開始しました")
    
    # --- 1. Google Sheets APIの認証 ---
    try:
        scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        env_key = os.environ.get("GCP_JSON_KEY")
        info = json.loads(env_key)
        creds = Credentials.from_service_account_info(info, scopes=scopes)
        client = gspread.authorize(creds)
        
        sheet_id = os.environ.get("SPREADSHEET_ID")
        sh = client.open_by_key(sheet_id)
        ws = sh.get_worksheet(1) # 2枚目のシート
        print(f"🎯 スプレッドシート接続成功: {sh.title} / シート名: {ws.title}")
    except Exception as e:
        print(f"❌ Google Sheets 接続エラー: {e}")
        sys.exit(1) # 💡 初期エラーのため、即座にエラー落ちさせて通知する

    # --- 2. ターゲットの読み込み ---
    input_csv = "targets_instagram.csv"
    if not os.path.exists(input_csv):
        print(f"❌ エラー: {input_csv} が見つかりません。")
        sys.exit(1) # 💡 設定ファイル不在のためエラー落ち
    with open(input_csv, 'r') as f:
        usernames = [line.strip() for line in f if line.strip()]
    
    print(f"📋 読み込んだInstagramアカウント数: {len(usernames)} 件")
    now_str = datetime.datetime.now().strftime("%Y-%m-%d")
    
    # 成功件数をトラックする変数
    success_count = 0
    
    # --- 3. Playwright処理 ---
    with sync_playwright() as p:
        # 💡 ステルス性を上げるため、Chromiumの起動引数を追加
        browser = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        
        session_id = os.environ.get("INSTAGRAM_SESSION_ID")
        
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="ja-JP", # 💡 日本からのアクセスに偽装
            viewport={"width": 1280, "height": 800}
        )
        
        if session_id:
            context.add_cookies([{
                'name': 'sessionid',
                'value': session_id,
                'domain': '.instagram.com',
                'path': '/',
                'secure': True,
                'httpOnly': True
            }])
            print("🔑 ログインセッションをブラウザに注入しました。")
        else:
            print("⚠️ 警告: INSTAGRAM_SESSION_ID が設定されていません。")

        page = context.new_page()

        for username in usernames:
            clean_username = username.replace("https://www.instagram.com/", "").replace("instagram.com/", "").replace("/", "")
            target_url = f"https://www.instagram.com/{clean_username}/"
            
            print(f"🔍 調査開始: @{clean_username}")
            
            try:
                page.goto(target_url, wait_until="domcontentloaded", timeout=40000)
                page.wait_for_timeout(random.randint(6000, 9000)) # 💡 読み込み完了後、少し長めに待つ
                
                raw_followers = "0"
                raw_following = "0"
                raw_posts = "0"
                
                # (以降、要素抽出と書き込みロジックはそのまま維持)
                # ...
                
            except Exception as e:
                print(f" ⚠️ 通信エラー: @{clean_username} - {e}")

            # 💡 次のアカウントへ行く前のインターバルを「15秒〜30秒の間でランダム」に延長
            # これによりスクレイピング検知の網をすり抜けます
            interval = random.randint(15000, 30000)
            page.wait_for_timeout(interval)

        browser.close()
        
    # --- 4. 運行チェック（エラー通知連動用） ---
    print(f"🏁 処理完了: {success_count} / {len(usernames)} 件の取得に成功しました。")
    
    # 💡 取得件数が0かつ、ターゲットが1件以上存在する場合はシステムを異常終了（エラーコード1）にする
    if success_count == 0 and len(usernames) > 0:
        print("❌ 致命的エラー: 全てのアカウントでデータ取得に失敗したため、システムを異常終了します。")
        sys.exit(1)
        
    print("✨ すべてのInstagram処理が正常終了しました。")

if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True)
    scrape_instagram_to_sheets()
