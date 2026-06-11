import os
import json
import datetime
import random
import sys
import re
import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright
import pprint

def extract_x_profile_data(html, target_username):
    """
    HTMLを徹底解剖し、進捗をすべてprint出力して原因を特定するデバッグ関数
    """
    profile_data = {"followers": 0, "following": 0, "posts": 0}
    
    # 🔍 【検証1】そもそもHTMLの文字数がどれくらいあるかチェック
    print(f"  [DEBUG] 取得したHTMLの総文字数: {len(html)} 文字")
    pprint.pprint(html)
    try:
        # 1. INITIAL_STATE のテキスト抽出テスト
        state_match = re.search(r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\});', html, re.DOTALL)
        if not state_match:
            state_match = re.search(r'__INITIAL_STATE__\s*=\s*(\{.*?\});', html, re.DOTALL)
            
        if not state_match:
            print("  [DEBUG] ❌ 致命的: HTML内から 'window.__INITIAL_STATE__' の文字列を検出できませんでした。")
        else:
            json_text = state_match.group(1)
            print(f"  [DEBUG] ⭕️ INITIAL_STATEの文字列を検出 (頭50文字): {json_text[:50]}...")
            
            # JSON変換テスト
            try:
                state_data = json.loads(json_text)
                print("  [DEBUG] ⭕️ JSONのパース（辞書型への変換）に成功しました。")
                
                # 階層の掘り下げテスト
                entities = state_data.get("entities", {})
                users = entities.get("users", {})
                users_entities = users.get("entities", {})
                
                print(f"  [DEBUG] entities内にあるユーザーデータの件数: {len(users_entities)} 件")
                
                if len(users_entities) > 0:
                    print(f"  [DEBUG] 内部に存在するアカウントID一覧: {list(users_entities.keys())}")
                    
                    # ターゲットの一致確認
                    found_flag = False
                    for user_id, user_info in users_entities.items():
                        screen_name = user_info.get("screen_name", "")
                        print(f"    - 見つかったアカウント: @{screen_name} (ID: {user_id})")
                        
                        if screen_name.lower() == target_username.lower():
                            profile_data["followers"] = int(user_info.get("followers_count", 0))
                            profile_data["following"] = int(user_info.get("friends_count", 0))
                            profile_data["posts"] = int(user_info.get("statuses_count", 0))
                            print(f"    🌟 一致するターゲットを発見! -> フォロワー: {profile_data['followers']}")
                            found_flag = True
                            return profile_data
                    
                    if not found_flag:
                        print(f"  [DEBUG] ❌ ロードされたユーザーデータの中に、探している @{target_username} は含まれていませんでした。")
                else:
                    print("  [DEBUG] ⚠️ users -> entities の中身が空っぽです。未ログイン制限の可能性があります。")
                    
            except Exception as json_e:
                print(f"  [DEBUG] ❌ JSONデコードエラー: {json_e}")

        # 2. 力技の文字列検索（正規表現）テスト
        print("  [DEBUG] 🔄 保険ロジック（文字列からの直接検索）をテストします...")
        f_match = re.search(r'"screen_name"\s*:\s*"' + re.escape(target_username) + r'".*?"followers_count"\s*:\s*(\d+)', html, re.IGNORECASE | re.DOTALL)
        if f_match:
            print(f"  [DEBUG] ⭕️ 文字列からフォロワー数を発見: {f_match.group(1)}")
            profile_data["followers"] = int(f_match.group(1))
            
            g_match = re.search(r'"screen_name"\s*:\s*"' + re.escape(target_username) + r'".*?"friends_count"\s*:\s*(\d+)', html, re.IGNORECASE | re.DOTALL)
            p_match = re.search(r'"screen_name"\s*:\s*"' + re.escape(target_username) + r'".*?"statuses_count"\s*:\s*(\d+)', html, re.IGNORECASE | re.DOTALL)
            if g_match: profile_data["following"] = int(g_match.group(1))
            if p_match: profile_data["posts"] = int(p_match.group(1))
        else:
            print(f"  [DEBUG] ❌ 文字列検索でも @{target_username} のデータは見つかりませんでした。")
            
    except Exception as e:
        print(f"  [DEBUG] ❌ デバッグ中に予期せぬ例外: {e}")
        
    return profile_data

def scrape_to_sheets():
    print("🚀 Xデータ収集プログラム（検証デバッグ版）を開始しました")
    
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
        # ステルス性を最大にするために少し偽装を追加
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()

        for username in usernames:
            clean_username = username.strip().replace("@", "")
            print(f"\n🔍 調査開始: @{clean_username}")
            
            try:
                # domcontentloaded より確実な networkidle（通信が完全に落ち着くまで）を試す
                page.goto(f"https://x.com/{clean_username}", wait_until="networkidle", timeout=30000)
                page.wait_for_timeout(5000)
                
                raw_html = page.content()
                
                # デバッグ解析の実行
                data = extract_x_profile_data(raw_html, clean_username)
                
                followers_num = data["followers"]
                following_num = data["following"]
                posts_num = data["posts"]

                if followers_num > 0 or following_num > 0:
                    ws.append_row([now_str, clean_username, following_num, followers_num, posts_num])
                    print(f" ✅ Success: {clean_username} (Followers: {followers_num:,})")
                    success_count += 1
                else:
                    print(f" ❌ Failed: {clean_username}")

            except Exception as e:
                print(f" ⚠️ 通信エラーまたはタイムアウト: @{clean_username} - {e}")

            page.wait_for_timeout(random.randint(3000, 6000))

        browser.close()
        
    print(f"\n🏁 処理完了: {success_count} / {len(usernames)} 件成功")
    if success_count == 0:
        sys.exit(1)

if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True)
    scrape_to_sheets()
