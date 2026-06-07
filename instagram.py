import os
import json
import datetime
import random
import sys
import re
import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

def scrape_instagram_to_sheets():
    print("🚀 Instagram収集プログラム（セッション注入・安定版）を開始しました")
    
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
        return

    # --- 2. ターゲットの読み込み ---
    input_csv = "targets_instagram.csv"
    if not os.path.exists(input_csv):
        print(f"❌ エラー: {input_csv} が見つかりません。")
        return
    with open(input_csv, 'r') as f:
        usernames = [line.strip() for line in f if line.strip()]
    
    print(f"📋 読み込んだInstagramアカウント数: {len(usernames)} 件")
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # --- 3. Playwright処理 ---
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        
        session_id = os.environ.get("INSTAGRAM_SESSION_ID")
        
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
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
                # domcontentloadedで素早くページを開く
                page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(5000) # データの読み込み時間を十分に確保
                
                # 💡 対策：要素（liなど）ではなく、ページ全体のHTMLテキスト（ソース）を丸ごと取得
                raw_html = page.content()
                
                followers_text = "不明"
                following_text = "不明"
                posts_text = "不明"
                
                # ログイン済みのクリーンなHTML内にあるメタデータテキストから数値を抽出
                # 例: "edge_followed_by":{"count":134257} のような構造、または一般用メタテキストを検索
                meta_match = re.search(r'meta\s+name="description"\s+content="([^"]+)"', raw_html)
                if meta_match:
                    meta_content = meta_match.group(1)
                    print(f" 📄 解析対象テキスト: {meta_content}")
                    
                    # 日本語表記の切り出し
                    f_match = re.search(r'フォロワー([\d.,万KM]+人?)', meta_content)
                    g_match = re.search(r'フォロー中([\d.,万KM]+人?)', meta_content)
                    p_match = re.search(r'投稿([\d.,万KM]+件?)', meta_content)
                    
                    if f_match: followers_text = f_match.group(1).replace('人', '').strip()
                    if g_match: following_text = g_match.group(1).replace('人', '').strip()
                    if p_match: posts_text = p_match.group(1).replace('件', '').strip()

                # 万が一上記で文字が取れなかった場合の「最終バックアップ案（タイトルから抽出）」
                if followers_text == "不明":
                    page_title = page.title()
                    print(f" ℹ️ バックアップ解析（タイトル）: {page_title}")
                    # タイトルに数値が含まれているパターンのパース
                    title_match = re.search(r'([\d.,万KM]+)\s*(?:Followers|フォロワー)', page_title, re.IGNORECASE)
                    if title_match:
                        followers_text = title_match.group(1).strip()

                # 最悪、フォロワー数だけでも画面上の別の場所から文字で掠め取る
                if followers_text == "不明":
                    try:
                        # 画面上の「フォロワー」という文字が含まれる要素のテキストを直接取得
                        followers_text = page.locator('a[href*="/followers/"]').inner_text()
                        followers_text = followers_text.replace("フォロワー", "").replace("人", "").strip()
                    except:
                        pass

                if followers_text != "不明" and followers_text != "":
                    ws.append_row([now_str, clean_username, following_text, followers_text, posts_text])
                    print(f" ✅ Success: {clean_username} (フォロワー: {followers_text}, フォロー中: {following_text}, 投稿: {posts_text})")
                else:
                    print(f" ❌ Failed: {clean_username} (HTMLのパースに失敗しました)")

            except Exception as e:
                print(f" ⚠️ 通信エラー: @{clean_username} - {e}")

            page.wait_for_timeout(random.randint(4000, 7000))

        browser.close()
    print("✨ すべてのInstagram処理が終了しました。")

if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True)
    scrape_instagram_to_sheets()
