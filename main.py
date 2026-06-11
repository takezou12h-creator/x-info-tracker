import os
import json
import datetime
import random
import sys
import re
import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

def extract_count_from_text(html, keyword):
    """
    HTML内のテキストから、Following や Followers の直前にある
    コンマ付きの数値（例: 6,945）を正確に抜き出す関数
    """
    try:
        # 例: >6,945</div><div[^>]*>Followers を狙い撃ちする最高精度の正規表現
        pattern = rf'font-bold">([\d,]+)</div>[^<]*<div[^>]*>{keyword}</div>'
        match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
        if match:
            # コンマを消して整数に変換
            cleaned_num = match.group(1).replace(",", "").strip()
            return int(cleaned_num)
            
        # 保険パターン：さらに広い範囲で検索
        pattern_fallback = rf'([\d,]+)[^<]*{keyword}'
        match_fb = re.search(pattern_fallback, html, re.IGNORECASE)
        if match_fb:
            cleaned_num = match_fb.group(1).replace(",", "").strip()
            if cleaned_num.isdigit():
                return int(cleaned_num)
    except Exception as e:
        print(f"  ⚠️ テキスト解析中に微細なエラー: {e}")
    return 0

def extract_posts_count(html):
    """HTML上部の 16.8K posts のような丸められた表記から大まかな数値を拾う関数"""
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
    print("🚀 X(Twitter)データ収集プログラム（HTMLダイレクト奪取版）を開始しました")
    
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
                # 通信が完全に落ち着くまで待つ
                page.goto(f"https://x.com/{clean_username}", wait_until="networkidle", timeout=30000)
                page.wait_for_timeout(5000)
                
                raw_html = page.content()
                
                # 💡 発見したリンクエリアの剥き出し文字から数値を直接抽出
                followers_num = extract_count_from_text(raw_html, "Followers")
                following_num = extract_count_from_text(raw_html, "Following")
                posts_num = extract_posts_count(raw_html)

                if followers_num > 0 or following_num > 0:
                    ws.append_row([now_str, clean_username, following_num, followers_num, posts_num])
                    print(f" ✅ Success: {clean_username} (Followers: {followers_num:,}, Following: {following_num:,}, Posts: {posts_num:,})")
                    success_count += 1
                else:
                    print(f" ❌ Failed: {clean_username} (画面上の数値を特定できませんでした)")

            except Exception as e:
                print(f" ⚠️ 通信エラーまたはタイムアウト: @{clean_username} - {e}")

            page.wait_for_timeout(random.randint(4000, 7000))

        browser.close()
        
    print(f"\n🏁 処理完了: {success_count} / {len(usernames)} 件の取得に成功しました。")
    if success_count == 0:
        sys.exit(1)

if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True)
    scrape_to_sheets()
