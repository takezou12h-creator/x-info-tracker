import os
import json
import datetime
import random
import sys
import re
import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

def extract_from_meta_tags(html, target_username):
    """
    Xが絶対に隠せないヘッドタグ内のメタ情報（og:title や description等）を解析し、
    テキスト内に埋め込まれているフォロワー数などの数値を強力にキャプチャする関数
    """
    metrics = {"followers": 0, "following": 0, "posts": 0}
    try:
        # 1. ページタイトル（例: "アカウント名 (@username) on X"）から存在確認
        title_match = re.search(r'<meta property="og:title" content="([^"]+)"', html)
        if not title_match:
            return metrics

        # 2. 本文やスクリプト全体から、おなじみの interactionStatistic や数値を直接探す
        # （JSONブロックがなくても、テキスト全体から数値を正規表現で広範囲に拾う）
        
        # フォロワー数のパターン（複数の記述方法に対応）
        # 例: "userInteractionCount":22615 や、画面上の数値の塊
        f_patterns = [
            r'"name"\s*:\s*"Follows"\s*,\s*"userInteractionCount"\s*:\s*(\d+)',
            r'followers[^<]*?>\s*([\d,.]+K?M?)\s*<',
            r'href="/{}/verified_followers"[^>]*>.*?font-bold">([^<]+)<'.format(re.escape(target_username)),
            r'href="/{}/followers"[^>]*>.*?font-bold">([^<]+)<'.format(re.escape(target_username))
        ]
        
        for pat in f_patterns:
            m = re.search(pat, html, re.IGNORECASE | re.DOTALL)
            if m:
                val_str = m.group(1).replace(",", "")
                if 'K' in val_str.upper():
                    metrics["followers"] = int(float(val_str.upper().replace('K', '')) * 1000)
                else:
                    metrics["followers"] = int(re.sub(r'\D', '', val_str) or 0)
                if metrics["followers"] > 0:
                    break

        # フォロー中のパターン
        g_patterns = [
            r'"name"\s*:\s*"Friends"\s*,\s*"userInteractionCount"\s*:\s*(\d+)',
            r'href="/{}/following"[^>]*>.*?font-bold">([^<]+)<'.format(re.escape(target_username))
        ]
        for pat in g_patterns:
            m = re.search(pat, html, re.IGNORECASE | re.DOTALL)
            if m:
                val_str = m.group(1).replace(",", "")
                metrics["following"] = int(re.sub(r'\D', '', val_str) or 0)
                if metrics["following"] > 0:
                    break

        # ポスト数のパターン
        p_match = re.search(r'([\d.,万KMkm]+)[^<]*posts', html, re.IGNORECASE)
        if p_match:
            val = p_match.group(1).replace(",", "").upper().strip()
            if 'K' in val: metrics["posts"] = int(float(val.replace('K', '')) * 1000)
            elif 'M' in val: metrics["posts"] = int(float(val.replace('M', '')) * 1000000)
            else: metrics["posts"] = int(float(re.sub(r'[^\d.]', '', val) or 0))

    except Exception as e:
        print(f"  ⚠️ 解析エラー: {e}")
        
    return metrics

def scrape_to_sheets():
    print("🚀 X(Twitter)ヘッダー監視・多重キャプチャ版を開始")
    
    # 認証
    creds = Credentials.from_service_account_info(
        json.loads(os.environ["GCP_JSON_KEY"]), 
        scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    )
    ws = gspread.authorize(creds).open_by_key(os.environ["SPREADSHEET_ID"]).get_worksheet(0)

    usernames = [l.strip() for l in open("targets.csv") if l.strip()]
    now_str = datetime.datetime.now().strftime("%Y-%m-%d")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # 本物の人間らしいブラウザ設定（モバイルではなく通常のChromeに偽装）
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        page = context.new_page()

        for username in usernames:
            user = username.strip().replace("@", "")
            print(f"🔍 調査中: @{user}")
            try:
                page.goto(f"https://x.com/{user}", wait_until="domcontentloaded", timeout=40000)
                page.wait_for_timeout(6000) 
                
                html = page.content()
                data = extract_from_meta_tags(html, user)
                
                if data["followers"] > 0 or data["following"] > 0:
                    ws.append_row([now_str, user, data["following"], data["followers"], data["posts"]])
                    print(f" ✅ Success: @{user} (F:{data['followers']}, Fg:{data['following']}, P:{data['posts']})")
                else:
                    print(f" ❌ Failed: @{user} - 有効な数値を特定できませんでした")
            except Exception as e:
                print(f" ⚠️ エラー: @{user} - {e}")
            
            page.wait_for_timeout(random.randint(4000, 7000))
        browser.close()

if __name__ == "__main__":
    scrape_to_sheets()
