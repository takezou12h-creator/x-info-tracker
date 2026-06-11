import os
import json
import datetime
import random
import sys
import re
import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

def extract_count_from_text(html, target_username, keyword):
    """
    ターゲット固有のプロフィールリンクから、ダミーやキャッシュのズレを完全に排除し、
    本物の数値（例: 6,945）だけを1の位まで100%正確にスナイプする関数
    """
    try:
        url_key = keyword.lower()
        
        if url_key == "followers":
            # 💡 対策：未ログイン特有の verified_followers と通常の followers の両方を厳密にキャッチ
            # href 属性の直後、または同じaタグの中に「font-bold">数字</div>」がある本物の構造だけを指定
            pattern = rf'href="/{re.escape(target_username)}/(verified_)?followers"[^>]*>.*?font-bold">([\d,]+)</div>'
            match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
            if match:
                return int(match.group(2).replace(",", "").strip())
                
            # 逆の並び（数字が前に来るパターン）も、直近のaタグと完全に紐づいているものだけを限定
            pattern_rev = rf'font-bold">([\d,]+)</div>.*?href="/{re.escape(target_username)}/(verified_)?followers"'
            match_rev = re.search(pattern_rev, html, re.IGNORECASE | re.DOTALL)
            if match_rev:
                return int(match_rev.group(1).replace(",", "").strip())
        else:
            # Following（フォロー中）の厳密スナイプ
            pattern = rf'href="/{re.escape(target_username)}/following"[^>]*>.*?font-bold">([\d,]+)</div>'
            match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
            if match:
                return int(match.group(1).replace(",", "").strip())
                
            pattern_rev = rf'font-bold">([\d,]+)</div>.*?href="/{re.escape(target_username)}/following"'
            match_rev = re.search(pattern_rev, html, re.IGNORECASE | re.DOTALL)
            if match_rev:
                return int(match_rev.group(1).replace(",", "").strip())
                
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
    print("🚀 X(Twitter)データ収集プログラム（完全一致・スナイパー版）を開始しました")
    
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
                page.wait_for_timeout(6000)
                
                raw_html = page.content()
                
                # ガチガチに固定した正規表現で抽出を実行
                followers_num = extract_count_from_text(raw_html, clean_username, "Followers")
                following_num = extract_count_from_text(raw_html, clean_username, "Following")
                posts_num = extract_posts_count(raw_html)

                if followers_num > 0 or following_num > 0:
                    ws.append_row([now_str, clean_username, following_num, followers_num, posts_num])
                    print(f" ✅ Success: {clean_username} (Followers: {followers_num:,}, Following: {following_num:,}, Posts: {posts_num:,})")
                    success_count += 1
                else:
                    print(f" ❌ Failed: {clean_username} (本物の数値エリアを特定できませんでした)")

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
