import os
import json
import datetime
import random
import sys
import re
import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

def extract_count_simple(html, keyword):
    """
    複雑なタグ判定をすべて捨て、keyword（followers や following）の
    「直前」にある数字の塊を最もシンプルに強奪する関数
    """
    try:
        # 💡 XのHTML構造上、「数字 </div></div>... <div>フォロワー</div>」という並びになっています。
        # この「数字」から「キーワード」までの間にある不要なタグをすべて無視して数字だけを狙います。
        pattern = rf'([\d,]+)[^<]*<div[^>]*>[^<]*{keyword}[^<]*</div>'
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            return int(match.group(1).replace(",", "").strip())
            
        # 保険パターン：キーワードが先に来る構造用
        pattern_rev = rf'{keyword}[^<]*</div>[^<]*<div[^>]*>([\d,]+)</div>'
        match_rev = re.search(pattern_rev, html, re.IGNORECASE)
        if match_rev:
            return int(match_rev.group(1).replace(",", "").strip())
            
    except:
        pass
    return 0

def extract_posts_count(html):
    try:
        match = re.search(r'([\d.,万KMkm]+)[^<]*posts', html, re.IGNORECASE)
        if match:
            val = match.group(1).replace(",", "").upper().strip()
            if 'K' in val: return int(float(val.replace('K', '')) * 1000)
            if 'M' in val: return int(float(val.replace('M', '')) * 1000000)
            if '万' in val: return int(float(val.replace('万', '')) * 10000)
            return int(float(val))
    except:
        pass
    return 0

def scrape_to_sheets():
    print("🚀 X(Twitter)データ収集プログラム（シンプル抽出版）を開始しました")
    
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
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()

        for username in usernames:
            clean_username = username.strip().replace("@", "")
            print(f"🔍 調査開始: @{clean_username}")
            
            try:
                page.goto(f"https://x.com/{clean_username}", wait_until="networkidle", timeout=30000)
                page.wait_for_timeout(6000)
                
                raw_html = page.content()
                
                # 最もシンプルに、html全体からキーワードの直前にある数字を引っこ抜く
                followers_num = extract_count_simple(raw_html, "Followers")
                following_num = extract_count_simple(raw_html, "Following")
                posts_num = extract_posts_count(raw_html)

                # どちらかが取れていれば書き込み
                if followers_num > 0 or following_num > 0:
                    ws.append_row([now_str, clean_username, following_num, followers_num, posts_num])
                    print(f" ✅ Success: {clean_username} (Followers: {followers_num:,}, Following: {following_num:,}, Posts: {posts_num:,})")
                    success_count += 1
                else:
                    # 保険：カタカナ環境（フォロワー）でレンダリングされた場合をカバー
                    followers_num = extract_count_simple(raw_html, "フォロワー")
                    following_num = extract_count_simple(raw_html, "フォロー中")
                    if followers_num > 0 or following_num > 0:
                        ws.append_row([now_str, clean_username, following_num, followers_num, posts_num])
                        print(f" ✅ Success(JA): {clean_username} (Followers: {followers_num:,}, Following: {following_num:,}, Posts: {posts_num:,})")
                        success_count += 1
                    else:
                        print(f" ❌ Failed: {clean_username}")

            except Exception as e:
                print(f" ⚠️ エラーまたはタイムアウト: @{clean_username} - {e}")

            page.wait_for_timeout(random.randint(4000, 7000))

        browser.close()
        
    print(f"\n🏁 処理完了: {success_count} / {len(usernames)} 件の取得に成功しました。")

if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True)
    scrape_to_sheets()
