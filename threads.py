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
    """「13.4万」「134K」「1万人」などの表記を整数に変換する共通関数"""
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
    print("🚀 Threads収集プログラム（スマホ画面位置最適化版）を開始しました")
    
    # --- 1. Google Sheets APIの認証 ---
    try:
        scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        env_key = os.environ.get("GCP_JSON_KEY")
        info = json.loads(env_key)
        creds = Credentials.from_service_account_info(info, scopes=scopes)
        client = gspread.authorize(creds)
        
        sheet_id = os.environ.get("SPREADSHEET_ID")
        sh = client.open_by_key(sheet_id)
        ws = sh.get_worksheet(2) # 3枚目のシート
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
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    success_count = 0
    
    # --- 3. Playwright処理 ---
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        session_id = os.environ.get("THREADS_SESSION_ID")
        
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        if session_id:
            context.add_cookies([{
                'name': 'sessionid',
                'value': session_id,
                'domain': '.threads.net',
                'path': '/',
                'secure': True,
                'httpOnly': True
            }])
            print("🔑 独自のセッションを利用してThreadsにログイン状態を注入しました。")
        else:
            print("⚠️ 警告: THREADS_SESSION_ID が未設定です。")

        page = context.new_page()

        for username in usernames:
            clean_username = username.replace("https://www.threads.net/", "").replace("threads.net/", "").replace("@", "").replace("/", "")
            target_url = f"https://www.threads.net/@{clean_username}"
            
            print(f"🔍 調査開始: @{clean_username}")
            
            try:
                page.goto(target_url, wait_until="networkidle", timeout=30000)
                page.wait_for_timeout(6000)
                
                raw_followers = "0"
                
                # 💡 対策：赤枠の位置（フォロワー数の独立したテキストエリア）を複数のパターンで網羅
                try:
                    # パターンA: 画面上の「フォロワー」という文字が含まれるすべての要素をリストアップ
                    elements = page.locator('*:has-text("followers"), *:has-text("フォロワー")').all()
                    
                    for el in elements:
                        if el.is_visible():
                            text = el.inner_text()
                            # 🔴 重要：自己紹介文（30万人超え💪のような余計な文字）を含まない、純粋なフォロワー行だけを選別
                            # 「人のフォロワー」「フォロワー」「followers」の直前に数字がある形を綺麗にキャッチします
                            if ("フォロワー" in text or "followers" in text) and "総フォロワー" not in text and "💪" not in text:
                                # 不要な文字を削ぎ落とす
                                cleaned_text = text.replace("人のフォロワー", "").replace("フォロワー", "").replace("followers", "").replace("人", "").strip()
                                # 数字や「万」「K」などのSNS数値表記が含まれているか確認
                                if re.search(r'[\d万KMkm\.]+', cleaned_text):
                                    raw_followers = cleaned_text
                                    print(f"  🎯 赤枠エリアから正しい表記を特定: {text.strip()}")
                                    break
                except Exception as inner_e:
                    print(f"  ⚠️ 要素のスキャン中にエラー: {inner_e}")

                # 整数に変換
                followers_num = parse_sns_count(raw_followers)

                if followers_num > 0:
                    ws.append_row([now_str, clean_username, 0, followers_num, 0])
                    print(f" ✅ Success: {clean_username} (フォロワー: {followers_num})")
                    success_count += 1
                else:
                    print(f" ❌ Failed: {clean_username} (画面上のフォロワー数を特定できませんでした)")

            except Exception as e:
                print(f" ⚠️ 通信エラー: @{clean_username} - {e}")

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
