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
    print("🚀 Instagram収集プログラム（画面文字ピンポイント抽出版）を開始しました")
    
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
                # ページを完全に読み込む
                page.goto(target_url, wait_until="networkidle", timeout=30000)
                page.wait_for_timeout(5000) # 念のため追加で待機
                
                followers_text = "不明"
                following_text = "不明"
                posts_text = "不明"
                
                # 💡 対策：画面上の「フォロワー」「following」という文字列を含む要素を直接指定
                # 英語環境・日本語環境のどちらでもヒットするように両方のキーワードで対応します
                try:
                    # 1. フォロワー数の取得
                    followers_element = page.locator('a[href*="/followers/"], span:has-text("followers"), span:has-text("フォロワー")').first
                    if followers_element.is_visible():
                        raw_f = followers_element.inner_text()
                        # 「13.4万 フォロワー」や「13.4M followers」から純粋な数値部分だけを抽出
                        followers_text = raw_f.replace("フォロワー", "").replace("followers", "").replace("人", "").strip()
                except Exception as e:
                    print(f"  ⚠️ フォロワー数取得エラー: {e}")
                    
                try:
                    # 2. フォロー中の取得
                    following_element = page.locator('a[href*="/following/"], span:has-text("following"), span:has-text("フォロー中")').first
                    if following_element.is_visible():
                        raw_g = following_element.inner_text()
                        following_text = raw_g.replace("フォロー中", "").replace("following", "").replace("人", "").strip()
                except Exception as e:
                    print(f"  ⚠️ フォロー中取得エラー: {e}")
                    
                try:
                    # 3. 投稿数の取得
                    posts_element = page.locator('span:has-text("posts"), li:has-text("投稿")').first
                    if posts_element.is_visible():
                        raw_p = posts_element.inner_text()
                        posts_text = raw_p.replace("投稿", "").replace("posts", "").replace("件", "").strip()
                except Exception as e:
                    print(f"  ⚠️ 投稿数取得エラー: {e}")

                # スプレッドシートへ書き込み
                if followers_text != "不明" and followers_text != "":
                    ws.append_row([now_str, clean_username, following_text, followers_text, posts_text])
                    print(f" ✅ Success: {clean_username} (フォロワー: {followers_text}, フォロー中: {following_text}, 投稿: {posts_text})")
                else:
                    print(f" ❌ Failed: {clean_username} (画面上の要素から文字を取得できませんでした)")

            except Exception as e:
                print(f" ⚠️ 通信エラー: @{clean_username} - {e}")

            page.wait_for_timeout(random.randint(4000, 7000))

        browser.close()
    print("✨ すべてのInstagram処理が終了しました。")

if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True)
    scrape_instagram_to_sheets()
