import os
import json
import datetime
import random
import sys
import re
import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

def extract_instagram_counts(html):
    """Instagramの生HTMLから、フォロワー数、フォロー数、投稿数を1桁単位で抽出する関数"""
    counts = {"followers": 0, "following": 0, "posts": 0}
    try:
        # 1. フォロワー数の抽出
        followers_match = re.search(r'"edge_followed_by"\s*:\s*\{\s*"count"\s*:\s*(\d+)', html)
        if followers_match:
            counts["followers"] = int(followers_match.group(1))
            
        # 2. フォロー中の抽出
        following_match = re.search(r'"edge_follow"\s*:\s*\{\s*"count"\s*:\s*(\d+)', html)
        if following_match:
            counts["following"] = int(following_match.group(1))
            
        # 3. 投稿数の抽出
        posts_match = re.search(r'"edge_owner_to_timeline_media"\s*:\s*\{\s*"count"\s*:\s*(\d+)', html)
        if posts_match:
            counts["posts"] = int(posts_match.group(1))
            
    except Exception as e:
        print(f" ⚠️ InstagramのHTML解析に失敗: {e}")
        
    return counts

def scrape_instagram_to_sheets():
    print("🚀 Instagram収集プログラムを開始しました")
    
    # --- 1. Google Sheets APIの認証 ---
    try:
        scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        env_key = os.environ.get("GCP_JSON_KEY")
        info = json.loads(env_key)
        creds = Credentials.from_service_account_info(info, scopes=scopes)
        client = gspread.authorize(creds)
        
        sheet_id = os.environ.get("SPREADSHEET_ID")
        sh = client.open_by_key(sheet_id)
        
        # 【重要】インデックス「1」を指定することで、2枚目のシートを取得します
        ws = sh.get_worksheet(1) 
        print(f"🎯 スプレッドシート接続成功: {sh.title} / シート名: {ws.title}")
    except Exception as e:
        print(f"❌ Google Sheets 接続エラー: {e}")
        return

    # --- 2. ターゲット（Instagram専用CSV）の読み込み ---
    input_csv = "targets_instagram.csv"
    if not os.path.exists(input_csv):
        print(f"❌ エラー: {input_csv} が見つかりません。")
        return
    with open(input_csv, 'r') as f:
        usernames = [line.strip() for line in f if line.strip()]
    
    print(f"📋 読み込んだInstagramアカウント数: {len(usernames)} 件")
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # --- 3. Playwrightブラウザの起動とスクレイピング ---
    print("⏳ Playwright を起動中...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        for username in usernames:
            # URL形式で書かれていてもユーザー名だけを純粋に抽出する整形処理
            clean_username = username.replace("https://www.instagram.com/", "").replace("instagram.com/", "").replace("/", "")
            target_url = f"https://www.instagram.com/{clean_username}/"
            
            print(f"🔍 調査開始: @{clean_username}")
            
            try:
                page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(5000) # Instagramは読み込みが重いため少し長めに待機
                
                raw_html = page.content()
                counts = extract_instagram_counts(raw_html)
                
                followers_num = counts["followers"]
                following_num = counts["following"]
                posts_num = counts["posts"]

                if followers_num > 0 or following_num > 0:
                    # 2枚目のシートに追記
                    ws.append_row([now_str, clean_username, following_num, followers_num, posts_num])
                    print(f" ✅ Success: {clean_username} (Followers: {followers_num:,}, Following: {following_num:,}, Posts: {posts_num:,})")
                else:
                    print(f" ❌ Failed: {clean_username} (生HTML内に数値が見つかりませんでした。一時的なブロックの可能性があります)")

            except Exception as e:
                print(f" ⚠️ 解析エラー: @{clean_username} - {e}")

            # 連続アクセス対策のランダムウェイト（少し長め）
            page.wait_for_timeout(random.randint(3000, 7000))

        browser.close()
    print("✨ 全すべてのInstagram処理が終了しました。")

if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True)
    scrape_instagram_to_sheets()
