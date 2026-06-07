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
                
                # --- 1人単位の正確な数値を隠し属性からぶっこ抜く最新ロジック ---
                
                # 1. フォロー数の取得（aタグ全体の title 属性、または内部の文字を狙う）
                following_element = page.locator('a[href$="/following"]').first
                # title属性（例: "277" や "1,234"）を取得、なければ画面の文字
                following_raw = following_element.get_attribute("title") or following_element.inner_text(timeout=5000)
                
                # 2. フォロワー数の取得
                followers_element = page.locator('a[href$="/verified_followers"], a[href$="/followers"]').first
                followers_raw = followers_element.get_attribute("title") or followers_element.inner_text(timeout=5000)
                
                # 「1,234 フォロワー」などの文字列から、純粋な数字とカンマ、万・億だけを綺麗に残す
                following_text = "".join(re.findall(r'[\d,万億KM.]+', following_raw))
                followers_text = "".join(re.findall(r'[\d,万億KM.]+', followers_raw))
                
                # ポスト数はヘッダーの下部から数字だけを抽出
                posts_text = "0"
                try:
                    posts_element = page.locator('header + div div div div div:has-text("ポスト")').last
                    posts_text = "".join(re.findall(r'[\d,]+', posts_element.inner_text()))
                except:
                    pass

                # 数値に変換（カンマを除去してint型にする）
                following_num = convert_str_to_int(following_text)
                followers_num = convert_str_to_int(followers_text)
                posts_num = convert_str_to_int(posts_text)

                if followers_num > 0 or following_num > 0:
                    # スプレッドシートに追記
                    ws.append_row([now_str, username, following_num, followers_num, posts_num])
                    print(f" ✅ Success: {username} (Followers: {followers_num:,}, Following: {following_num:,})")
                else:
                    print(f" ❌ Failed: {username} (数値が正常に取得できませんでした)")

            except Exception as e:
                print(f" ⚠️ 解析エラー: @{username} - {e}")

            page.wait_for_timeout(random.randint(2000, 4000))

        browser.close()
    print("✨ すべての処理が終了しました。")

if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True)
    scrape_to_sheets()
