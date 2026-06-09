import os
import json
import datetime
import random
import sys
import re
import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

def scrape_threads_to_sheets():
    print("🚀 Threads収集プログラム（完全汎用・1桁属性狙い撃ち版）を開始しました")
    
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
                # 💡 対策①: ページ移動後、ネットワーク通信が完全に落ち着くまで待つ
                page.goto(target_url, wait_until="networkidle", timeout=30000)
                page.wait_for_timeout(6000) # 1件目の読み込み遅延対策として少し長めに待機
                
                followers_num = 0
                
                # 1. 汎用画面属性スキャン（title属性を狙う）
                try:
                    target_span = page.locator('span:has-text("フォロワー") ~ span[title], span:has-text("followers") ~ span[title], span[title]:has-text("万"), span[title]:has-text("人")').first
                    
                    if target_span.is_visible():
                        title_value = target_span.get_attribute("title")
                        print(f"  🎯 汎用構造から1桁生データを検知: title=\"{title_value}\"")
                        followers_num = int(title_value.replace(",", "").strip())
                    else:
                        # バックアップスキャン
                        all_spans = page.locator('span[title]').all()
                        for s in all_spans:
                            t_val = s.get_attribute("title")
                            if t_val and re.match(r'^[\d,]+$', t_val.strip()):
                                followers_num = int(t_val.replace(",", "").strip())
                                print(f"  🎯 汎用スキャンから生データを特定: title=\"{t_val}\"")
                                break
                except Exception as inner_e:
                    print(f"  ⚠️ 属性抽出エラー(保険ロジックへ移行): {inner_e}")
                
                # 💡 対策②: 万が一画面から取れなかった場合、裏の生HTMLソース(JSON)を直接解剖して完全救済
                if followers_num == 0:
                    raw_html = page.content()
                    # 1桁単位の生データをダイレクトに狙い撃ち
                    meta_match = re.search(r'"edge_followed_by"\s*:\s*\{\s*"count"\s*:\s*(\d+)', raw_html)
                    if not meta_match:
                        # 別パターンのJSONキー名も網羅
                        meta_match = re.search(r'"follower_count"\s*:\s*(\d+)', raw_html)
                        
                    if meta_match:
                        followers_num = int(meta_match.group(1))
                        print(f"  🔥 保険ロジック（生JSONハッキング）により1桁単位の完全救済に成功: {followers_num}")

                if followers_num > 0:
                    ws.append_row([now_str, clean_username, 0, followers_num, 0])
                    print(f" ✅ Success: {clean_username} (フォロワー: {followers_num})")
                    success_count += 1
                else:
                    print(f" ❌ Failed: {clean_username} (1桁数値の特定に失敗しました。非公開または一時的なブロックの可能性があります)")

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
