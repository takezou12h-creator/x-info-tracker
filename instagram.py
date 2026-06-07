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
    print("🚀 Instagram収集プログラム（セッション注入版）を開始しました")
    
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
        
        # 💡 セッションID（Cookie）の取得
        session_id = os.environ.get("INSTAGRAM_SESSION_ID")
        
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        # GitHubのブラウザにログイン状態を擬似的に覚えさせる
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
            print("⚠️ 警告: INSTAGRAM_SESSION_ID が設定されていません。ログインなしで続行します。")

        page = context.new_page()

        for username in usernames:
            clean_username = username.replace("https://www.instagram.com/", "").replace("instagram.com/", "").replace("/", "")
            target_url = f"https://www.instagram.com/{clean_username}/"
            
            print(f"🔍 調査開始: @{clean_username}")
            
            try:
                # ログイン状態なので通常URLで堂々と開けます
                page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(5000) # 画面の文字が出揃うのを待つ
                
                # 画面上の「フォロワー」「フォロー中」「投稿」の文字エリアを特定してテキストを引っこ抜く
                # ログイン状態の画面構成に対応したセレクタです
                followers_text = "不明"
                following_text = "不明"
                posts_text = "不明"
                
                try:
                    # 「◯万」や「◯◯人」と書かれた要素を狙い撃ち
                    posts_text = page.locator('header section ul li').nth(0).inner_text()
                    followers_text = page.locator('header section ul li').nth(1).inner_text()
                    following_text = page.locator('header section ul li').nth(2).inner_text()
                    
                    # 不要な文字（フォロワー、投稿など）を削ってすっきりさせる
                    posts_text = posts_text.replace("投稿", "").replace("件", "").strip()
                    followers_text = followers_text.replace("フォロワー", "").replace("人", "").strip()
                    following_text = following_text.replace("フォロー中", "").replace("人", "").strip()
                except Exception as inner_e:
                    print(f" ⚠️ 画面要素の取得に一部失敗: {inner_e}")

                if followers_text != "不明" and followers_text != "":
                    ws.append_row([now_str, clean_username, following_text, followers_text, posts_text])
                    print(f" ✅ Success: {clean_username} (フォロワー: {followers_text}, フォロー中: {following_text}, 投稿: {posts_text})")
                else:
                    print(f" ❌ Failed: {clean_username} (ログイン壁は越えましたが、画面上の文字を取得できませんでした)")

            except Exception as e:
                print(f" ⚠️ 通信エラー: @{clean_username} - {e}")

            page.wait_for_timeout(random.randint(3000, 6000))

        browser.close()
    print("✨ すべてのInstagram処理が終了しました。")

if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True)
    scrape_instagram_to_sheets()
