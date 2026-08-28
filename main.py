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
    """
    agentInteractionStatistic と interactionStatistic の両方に対応し、
    1桁単位の生数値を確実に抜き出す関数
    """
    metrics = {"followers": 0, "following": 0, "posts": 0}
    
    try:
        # 1. パターン: 構造化データ(application/ld+json)の探索
        json_blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL)
        for block in json_blocks:
            try:
                data = json.loads(block.strip())
                # mainEntity または直下から取得
                main_entity = data.get("mainEntity", {})
                
                # 複数のスタッツ格納プロパティをすべてチェック
                stats = []
                for key in ["interactionStatistic", "agentInteractionStatistic"]:
                    if key in main_entity:
                        stats.extend(main_entity.get(key, []))
                    if key in data:
                        stats.extend(data.get(key, []))
                
                for stat in stats:
                    name = stat.get("name", "")
                    val = int(stat.get("userInteractionCount", 0))
                    if name == "Follows": metrics["followers"] = val
                    elif name == "Friends": metrics["following"] = val
                    elif name == "Tweets": metrics["posts"] = val
                
                if metrics["followers"] > 0 or metrics["following"] > 0:
                    return metrics
            except:
                continue

        # 2. パターン: HTML内の agentInteractionStatistic や数値の直接スナイプ（バックアップ）
        # 共有いただいたツリー構造にある属性名や数値の並びをダイレクトにキャプチャ
        f_match = re.search(r'"name"\s*:\s*"Follows"\s*,\s*"userInteractionCount"\s*:\s*(\d+)', html)
        g_match = re.search(r'"name"\s*:\s*"Friends"\s*,\s*"userInteractionCount"\s*:\s*(\d+)', html)
        p_match = re.search(r'"name"\s*:\s*"Tweets"\s*,\s*"userInteractionCount"\s*:\s*(\d+)', html)
        
        if f_match: metrics["followers"] = int(f_match.group(1))
        if g_match: metrics["following"] = int(g_match.group(1))
        if p_match: metrics["posts"] = int(p_match.group(1))

        # 3. パターン: 画面上の要素（例: 画像の759など）を直接拾う最終保険
        if metrics["following"] == 0:
            # followingリンク周辺の数字を探索
            fg_search = re.search(r'href="/[^/]+/following"[^>]*>.*?font-bold">([\d,]+)<', html, re.DOTALL)
            if fg_search:
                metrics["following"] = int(fg_search.group(1).replace(",", ""))

        if metrics["followers"] == 0:
            # followersリンク周辺の数字を探索
            fo_search = re.search(r'href="/[^/]+/(verified_)?followers"[^>]*>.*?font-bold">([\d,]+[KM]?)<', html, re.DOTALL)
            if fo_search:
                val_str = fo_search.group(2).replace(",", "")
                if 'K' in val_str.upper():
                    metrics["followers"] = int(float(val_str.upper().replace('K', '')) * 1000)
                else:
                    metrics["followers"] = int(re.sub(r'\D', '', val_str) or 0)

    except Exception as e:
        print(f"  ⚠️ メタデータ解析エラー: {e}")
        
    return metrics

def scrape_to_sheets():
    print("🚀 X(Twitter)エージェント統計対応版を開始しました")
    
    # 認証
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
        sys.exit(1)
        
    with open(input_csv, 'r') as f:
        usernames = [line.strip() for line in f if line.strip()]
    
    now_str = datetime.datetime.now().strftime("%Y-%m-%d")
    success_count = 0
    
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
            try:
                page.goto(f"https://x.com/{user}", wait_until="domcontentloaded", timeout=40000)
                page.wait_for_timeout(6000) 
                
                html = page.content()
                data = extract_x_clean_metrics(html)
                
                if data["followers"] > 0 or data["following"] > 0:
                    ws.append_row([now_str, user, data["following"], data["followers"], data["posts"]])
                    print(f" ✅ Success: @{user} (F:{data['followers']:,}, Fg:{data['following']:,}, P:{data['posts']:,})")
                    success_count += 1
                else:
                    print(f" ❌ Failed: @{user} - 有効な数値を特定できませんでした")
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
