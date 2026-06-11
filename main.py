import os
import json
import datetime
import random
import sys
import re
import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

def extract_x_profile_data(html, target_username):
    """
    提供された最新のXのHTMLから window.__INITIAL_STATE__ を検出し、
    指定されたユーザーの1桁単位の正確な生データを辞書型でぶっこ抜く関数
    """
    profile_data = {"followers": 0, "following": 0, "posts": 0}
    
    try:
        # 1. HTML内から window.__INITIAL_STATE__ = { ... }; の中身を抽出
        state_match = re.search(r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\});', html, re.DOTALL)
        if not state_match:
            # 別の記述パターン（スペースなし等）もカバー
            state_match = re.search(r'__INITIAL_STATE__\s*=\s*(\{.*?\});', html, re.DOTALL)
            
        if state_match:
            json_text = state_match.group(1)
            # JSONとしてPythonで扱えるようにロード
            state_data = json.loads(json_text)
            
            # 最新のHTML構造の users -> entities の中を大捜索
            users_entities = state_data.get("entities", {}).get("users", {}).get("entities", {})
            
            # 隠されているユーザーデータの中から、screen_name がターゲットと一致するものを特定
            for user_id, user_info in users_entities.items():
                screen_name = user_info.get("screen_name", "").lower()
                
                if screen_name == target_username.lower():
                    # 1桁単位のリアルな生数値をダイレクトに奪取！
                    profile_data["followers"] = int(user_info.get("followers_count", 0))
                    profile_data["following"] = int(user_info.get("friends_count", 0))
                    profile_data["posts"] = int(user_info.get("statuses_count", 0))
                    print(f"  🔥 最新のINITIAL_STATEのデコードに成功しました。内部ID: {user_id}")
                    return profile_data
                    
        # 2. 【バックアップ保険】もし上記で見つからなかった場合、文字列から直接力技で探す
        if profile_data["followers"] == 0:
            f_match = re.search(r'"screen_name"\s*:\s*"' + re.escape(target_username) + r'".*?"followers_count"\s*:\s*(\d+)', html, re.IGNORECASE | re.DOTALL)
            g_match = re.search(r'"screen_name"\s*:\s*"' + re.escape(target_username) + r'".*?"friends_count"\s*:\s*(\d+)', html, re.IGNORECASE | re.DOTALL)
            p_match = re.search(r'"screen_name"\s*:\s*"' + re.escape(target_username) + r'".*?"statuses_count"\s*:\s*(\d+)', html, re.IGNORECASE | re.DOTALL)
            
            if f_match: profile_data["followers"] = int(f_match.group(1))
            if g_match: profile_data["following"] = int(g_match.group(1))
            if p_match: profile_data["posts"] = int(p_match.group(1))
            
    except Exception as e:
        print(f"  ⚠️ HTMLデータのハッキング中にエラーが発生しました: {e}")
        
    return profile_data

def scrape_to_sheets():
    print("🚀 X(Twitter)データ収集プログラム（完全汎用・JSON解剖版）を開始しました")
    
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
    
    # 日付フォーマットの完全統一 (YYYY-MM-DD)
    now_str = datetime.datetime.now().strftime("%Y-%m-%d")
    
    success_count = 0
    
    # --- 3. Xのスクレイピング処理 ---
    print("Step 2: Playwright を起動します...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        for username in usernames:
            clean_username = username.strip().replace("@", "")
            print(f"🔍 調査開始: @{clean_username}")
            
            try:
                # ページへ移動してHTMLソースの生成を待つ
                page.goto(f"https://x.com/{clean_username}", wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(5000) # 生成時間を十分に確保
                
                # 裏にある「生HTMLソース」を取得
                raw_html = page.content()
                
                # 💡 対策：抽出ロジックを最新のJSON構造に完全変更
                data = extract_x_profile_data(raw_html, clean_username)
                
                followers_num = data["followers"]
                following_num = data["following"]
                posts_num = data["posts"]

                if followers_num > 0 or following_num > 0:
                    # スプレッドシートに追記
                    ws.append_row([now_str, clean_username, following_num, followers_num, posts_num])
                    print(f" ✅ Success: {clean_username} (Followers: {followers_num:,}, Following: {following_num:,}, Posts: {posts_num:,})")
                    success_count += 1
                else:
                    print(f" ❌ Failed: {clean_username} (生HTML内のデータ構造から数値を特定できませんでした)")

            except Exception as e:
                print(f" ⚠️ 解析エラー: @{clean_username} - {e}")

            page.wait_for_timeout(random.randint(3000, 6000))

        browser.close()
        
    # --- 4. 運行チェック（エラー通知連動用） ---
    print(f"🏁 処理完了: {success_count} / {len(usernames)} 件の取得に成功しました。")
    
    if success_count == 0 and len(usernames) > 0:
        print("❌ 致命的エラー: 全てのアカウントでデータ取得に失敗したため、システムを異常終了します。")
        sys.exit(1)
        
    print("✨ すべてのXデータ処理が正常終了しました。")

if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True)
    scrape_to_sheets()
