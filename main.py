import os
import json
import datetime
import random
import sys
import re
import gspread
from google.oauth2.service_accountCredentials import Credentials if False else None # プレースホルダー回避
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

def parse_count(text):
    """ '22.6K' や '6,945'、 '759' などの文字列を純粋な整数に変換 """
    if not text:
        return 0
    cleaned = text.replace(",", "").upper().strip()
    try:
        if 'K' in cleaned:
            return int(float(cleaned.replace('K', '')) * 1000)
        elif 'M' in cleaned:
            return int(float(cleaned.replace('M', '')) * 1000000)
        elif '万' in cleaned:
            return int(float(cleaned.replace('万', '')) * 10000)
        else:
            return int(re.sub(r'\D', '', cleaned) or 0)
    except:
        return 0

def scrape_to_sheets():
    print("🚀 X(Twitter) 画面要素直撃・最終完全版を開始しました")
    
    # --- 1. 認証 ---
    try:
        creds = Credentials.from_service_account_info(
            json.loads(os.environ["GCP_JSON_KEY"]), 
            scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        )
        ws = gspread.authorize(creds).open_by_key(os.environ["SPREADSHEET_ID"]).get_worksheet(0)
    except Exception as e:
        print(f"❌ スプレッドシート接続エラー: {e}")
        sys.exit(1)

    input_csv = "targets.csv"
    if not os.path.exists(input_csv):
        print(f"❌ targets.csv が見つかりません")
        sys.exit(1)
        
    with open(input_csv, 'r') as f:
        usernames = [line.strip() for line in f if line.strip()]
    
    now_str = datetime.datetime.now().strftime("%Y-%m-%d")
    success_count = 0
    
    # --- 2. Playwright 実行 ---
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        page = context.new_page()

        for username in usernames:
            user = username.strip().replace("@", "")
            print(f"🔍 調査中: @{user}")
            
            followers_num = 0
            following_num = 0
            posts_num = 0
            
            try:
                # ページへ移動
                page.goto(f"https://x.com/{user}", wait_until="domcontentloaded", timeout=40000)
                page.wait_for_timeout(6000) # レンダリング待機
                
                # 💡【極秘テクニック】画面上のフォロワー・フォローリンクを直接特定してテキストを奪う
                # 画像のツリー構造にあった href="/username/verified_followers" または /followers を狙う
                
                # 1. フォロワー数の取得
                follower_selectors = [
                    f'a[href="/{user}/verified_followers"] .font-bold',
                    f'a[href="/{user}/followers"] .font-bold',
                    f'a[href*="/followers"] .font-bold'
                ]
                for sel in follower_selectors:
                    elem = page.query_selector(sel)
                    if elem:
                        text = elem.inner_text()
                        if text:
                            followers_num = parse_count(text)
                            if followers_num > 0:
                                break
                
                # 2. フォロー数の取得
                following_selector = f'a[href="/{user}/following"] .font-bold'
                elem_fg = page.query_selector(following_selector)
                if elem_fg:
                    text_fg = elem_fg.inner_text()
                    if text_fg:
                        following_num = parse_count(text_fg)

                # 3. ポスト数の取得（HTML全体から検索）
                html = page.content()
                match_p = re.search(r'([\d.,万KMkm]+)[^<]*posts', html, re.IGNORECASE)
                if match_p:
                    posts_num = parse_count(match_p.group(1))

                # 万が一Playwrightの要素取得で0だった場合の保険（HTML全体からの正規表現フォールバック）
                if followers_num == 0:
                    match_f = re.search(r'href="/{}/(verified_)?followers"[^>]*>.*?font-bold">([^<]+)<'.format(re.escape(user)), html, re.DOTALL)
                    if match_f:
                        followers_num = parse_count(match_f.group(2))

                if following_num == 0:
                    match_g = re.search(r'href="/{}/following"[^>]*>.*?font-bold">([^<]+)<'.format(re.escape(user)), html, re.DOTALL)
                    if match_g:
                        following_num = parse_count(match_g.group(2))

                # 書き込み判定
                if followers_num > 0 or following_num > 0:
                    ws.append_row([now_str, user, following_num, followers_num, posts_num])
                    print(f" ✅ Success: @{user} (F:{followers_num:,}, Fg:{following_num:,}, P:{posts_num:,})")
                    success_count += 1
                else:
                    print(f" ❌ Failed: @{user} - 画面上の数値を特定できませんでした")

            except Exception as e:
                print(f" ⚠️ エラー: @{user} - {e}")
            
            page.wait_for_timeout(random.randint(4000, 7000))
            
        browser.close()
        
    print(f"\n🏁 処理完了: {success_count} / {len(usernames)} 件の取得に成功しました。")
    if success_count == 0:
        sys.exit(1)

if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True)
    scrape_to_sheets()
