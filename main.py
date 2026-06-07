import os
import json
import datetime
import random
import sys
import re
import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

def convert_str_to_int(val_str):
    """「1.2万」や「2.3億」、「1,234」などの文字列を純粋な数値に変換する関数"""
    if not val_str:
        return 0
    val_str = val_str.replace(',', '').strip()
    try:
        if '万' in val_str:
            num = float(val_str.replace('万', ''))
            return int(num * 10000)
        elif '億' in val_str:
            num = float(val_str.replace('億', ''))
            return int(num * 100000000)
        elif 'K' in val_str:
            num = float(val_str.replace('K', ''))
            return int(num * 1000)
        elif 'M' in val_str:
            num = float(val_str.replace('M', ''))
            return int(num * 1000000)
        return int(val_str)
    except:
        return 0

def scrape_to_sheets():
    print("Step 1: プログラムを開始しました")
    
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
        return

    # --- 2. ターゲットの読み込み ---
    input_csv = "targets.csv"
    if not os.path.exists(input_csv):
        print(f"❌ エラー: {input_csv} が見つかりません。")
        return
    with open(input_csv, 'r') as f:
        usernames = [line.strip() for line in f if line.strip()]
    
    print(f"📋 読み込んだアカウント数: {len(usernames)} 件")
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # --- 3. Xのスクレイピング（画面要素直接取得版） ---
    print("Step 2: Playwright を起動します...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()

        for username in usernames:
            print(f"🔍 調査開始: @{username}")
            
            try:
                # ページへ移動
                page.goto(f"https://x.com/{username}", wait_until="domcontentloaded", timeout=30000)
                # 画面がしっかりレンダリングされるのを待つ
                page.wait_for_timeout(5000)
                
                # HTMLのテキスト全体から「フォロー中」「フォロワー」の直前にある数字を抽出する最新の指定方法
                # クラス名や裏の通信に依存しないため、非常に頑丈です
                following_text = page.locator('a[href$="/following"] span').first.inner_text(timeout=5000)
                followers_text = page.locator('a[href$="/verified_followers"] span, a[href$="/followers"] span').first.inner_text(timeout=5000)
                
                # ポスト数は、画面上の「ポスト」や「件のポスト」の文字列から抽出を試みる
                posts_text = "0"
                try:
                    # ユーザー名のパズル下部などの「◯件のポスト」というエリアを狙う
                    posts_element = page.locator('header + div div div div div:has-text("ポスト")').last
                    posts_text = re.sub(r'\D', '', posts_element.inner_text())
                except:
                    pass

                # 数値に変換
                following_num = convert_str_to_int(following_text)
                followers_num = convert_str_to_int(followers_text)
                posts_num = convert_str_to_int(posts_text)

                if followers_num > 0 or following_num > 0:
                    # スプレッドシートに追記
                    ws.append_row([now_str, username, following_num, followers_num, posts_num])
                    print(f" ✅ Success: {username} (Followers: {followers_num}, Following: {following_num})")
                else:
                    print(f" ❌ Failed: {username} (画面上の数値が0または取得不可)")

            except Exception as e:
                print(f" ⚠️ 解析エラー: @{username} - {e}")

            page.wait_for_timeout(random.randint(2000, 4000))

        browser.close()
    print("✨ すべての処理が終了しました。")

if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True)
    scrape_to_sheets()
