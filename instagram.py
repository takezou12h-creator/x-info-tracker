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
    print("🚀 Instagram簡易収集プログラム（メタタグ版）を開始しました")
    
    # --- 1. Google Sheets APIの認証 ---
    try:
        scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        env_key = os.environ.get("GCP_JSON_KEY")
        info = json.loads(env_key)
        creds = Credentials.from_service_account_info(info, scopes=scopes)
        client = gspread.authorize(creds)
        
        sheet_id = os.environ.get("SPREADSHEET_ID")
        sh = client.open_by_key(sheet_id)
        ws = sh.get_worksheet(1) # 2枚目のシートを指定
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
    
    # --- 3. Playwrightでメタデータのみを高速抽出 ---
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        for username in usernames:
            clean_username = username.replace("https://www.instagram.com/", "").replace("instagram.com/", "").replace("/", "")
            target_url = f"https://www.instagram.com/{clean_username}/"
            
            print(f"🔍 調査開始: @{clean_username}")
            
            try:
                # domcontentloaded（HTML構造の読み込み完了）の時点で即処理に入るため、超高速です
                page.goto(target_url, wait_until="domcontentloaded", timeout=20000)
                
                # Googleなどのロボット向けに公開されている description メタタグを狙い撃ち
                meta_element = page.locator('meta[name="description"]')
                meta_content = meta_element.get_attribute("content")
                
                if meta_content:
                    print(f" 📄 キャッチしたメタテキスト: {meta_content}")
                    
                    # 日本語表記パターンから「フォロワー」「フォロー中」「投稿」を抽出
                    followers_match = re.search(r'フォロワー([\d.,万KM]+人?)', meta_content)
                    following_match = re.search(r'フォロー中([\d.,万KM]+人?)', meta_content)
                    posts_match = re.search(r'投稿([\d.,万KM]+件?)', meta_content)
                    
                    # 英語表記パターンの場合の保険
                    if not followers_match:
                        followers_match = re.search(r'([\d.,万KM]+)\s*Followers', meta_content, re.IGNORECASE)
                    if not following_match:
                        following_match = re.search(r'([\d.,万KM]+)\s*Following', meta_content, re.IGNORECASE)
                    if not posts_match:
                        posts_match = re.search(r'([\d.,万KM]+)\s*Posts', meta_content, re.IGNORECASE)

                    # テキストとしてそのままスプレッドシートに記録（例: "13.4万人"、"242人"）
                    f_val = followers_match.group(1).replace('人', '').strip() if followers_match else "不明"
                    g_val = following_match.group(1).replace('人', '').strip() if following_match else "不明"
                    p_val = posts_match.group(1).replace('件', '').strip() if posts_match else "不明"

                    # スプレッドシートの2枚目（インスタ用シート）に格納
                    ws.append_row([now_str, clean_username, g_val, f_val, p_val])
                    print(f" ✅ Success: {clean_username} (フォロワー: {f_val}, フォロー中: {g_val}, 投稿: {p_val})")
                else:
                    print(f" ❌ Failed: {clean_username} (メタデータが空でした)")

            except Exception as e:
                print(f" ⚠️ 通信エラー: @{clean_username} - {e}")

            # 念のための待機
            page.wait_for_timeout(random.randint(2000, 4000))

        browser.close()
    print("✨ すべてのInstagram処理が終了しました。")

if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True)
    scrape_instagram_to_sheets()
