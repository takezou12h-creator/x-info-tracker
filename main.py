import os
import json
import datetime
import random
import sys
import re
import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

def extract_x_clean_metrics(html):
    """HTMLからメタデータを探索し、桁数やフォーマットを問わず生数値を抽出する"""
    metrics = {"followers": 0, "following": 0, "posts": 0}
    
    # パターン1: 構造化データ(application/ld+json)の探索
    json_blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL)
    for block in json_blocks:
        try:
            data = json.loads(block.strip())
            # ネストされたデータ構造から探す
            main_entity = data.get("mainEntity", {})
            stats = main_entity.get("interactionStatistic", [])
            
            # もしメインエンティティになければトップレベルを探す
            if not stats: stats = data.get("interactionStatistic", [])
            
            for stat in stats:
                name = stat.get("name", "")
                val = int(stat.get("userInteractionCount", 0))
                if name == "Follows": metrics["followers"] = val
                elif name == "Friends": metrics["following"] = val
                elif name == "Tweets": metrics["posts"] = val
            
            if metrics["followers"] > 0: return metrics
        except: continue

    # パターン2: 直接HTMLから正規表現で生数値をスナイプするバックアップ
    # JSON構造化データがない場合に備え、"userInteractionCount": 12345 を直接狙う
    f_match = re.search(r'"name"\s*:\s*"Follows"\s*,\s*"userInteractionCount"\s*:\s*(\d+)', html)
    g_match = re.search(r'"name"\s*:\s*"Friends"\s*,\s*"userInteractionCount"\s*:\s*(\d+)', html)
    p_match = re.search(r'"name"\s*:\s*"Tweets"\s*,\s*"userInteractionCount"\s*:\s*(\d+)', html)
    
    if f_match: metrics["followers"] = int(f_match.group(1))
    if g_match: metrics["following"] = int(g_match.group(1))
    if p_match: metrics["posts"] = int(p_match.group(1))
    
    return metrics

def scrape_to_sheets():
    print("🚀 X(Twitter)メタデータ強奪版を開始")
    
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
        page = browser.new_page()

        for username in usernames:
            user = username.strip().replace("@", "")
            print(f"🔍 調査中: @{user}")
            try:
                # タイムアウトを少し長めに設定
                page.goto(f"https://x.com/{user}", wait_until="domcontentloaded", timeout=40000)
                # ページ読み込み後のJavaScript実行を待つ
                page.wait_for_timeout(8000) 
                
                html = page.content()
                data = extract_x_clean_metrics(html)
                
                if data["followers"] > 0 or data["following"] > 0:
                    ws.append_row([now_str, user, data["following"], data["followers"], data["posts"]])
                    print(f" ✅ Success: @{user} (F:{data['followers']}, Fg:{data['following']}, P:{data['posts']})")
                else:
                    print(f" ❌ Failed: @{user} - データが見つかりません")
            except Exception as e:
                print(f" ⚠️ エラー: @{user} - {e}")
            
            page.wait_for_timeout(random.randint(5000, 8000))
        browser.close()

if __name__ == "__main__":
    scrape_to_sheets()
