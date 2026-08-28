import os
import json
import datetime
import random
import sys
import re
import gspread
import requests
from google.oauth2.service_account import Credentials

def fetch_x_html(username):
    """
    Playwrightを一切使わず、完璧なブラウザヘッダーを偽装したrequestsで
    Xの生HTMLをダイレクトに強奪する関数
    """
    url = f"https://x.com/{username}"
    
    # 人間のブラウザが送るものと全く同じ偽装ヘッダー
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Sec-Ch-Ua": '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        return response.text
    except Exception as e:
        print(f"  ⚠️ 通信例外: {e}")
        return ""

def parse_count(text):
    if not text: return 0
    cleaned = text.replace(",", "").upper().strip()
    try:
        if 'K' in cleaned: return int(float(cleaned.replace('K', '')) * 1000)
        elif 'M' in cleaned: return int(float(cleaned.replace('M', '')) * 1000000)
        elif '万' in cleaned: return int(float(cleaned.replace('万', '')) * 10000)
        else: return int(re.sub(r'\D', '', cleaned) or 0)
    except:
        return 0

def scrape_to_sheets():
    print("🚀 X(Twitter) requests直撃・超高速版を開始しました")
    
    try:
        creds = Credentials.from_service_account_info(
            json.loads(os.environ["GCP_JSON_KEY"]), 
            scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        )
        ws = gspread.authorize(creds).open_by_key(os.environ["SPREADSHEET_ID"]).get_worksheet(0)
    except Exception as e:
        print(f"❌ スプレッドシート接続エラー: {e}")
        sys.exit(1)

    with open("targets.csv", 'r') as f:
        usernames = [line.strip() for line in f if line.strip()]
    
    now_str = datetime.datetime.now().strftime("%Y-%m-%d")
    success_count = 0

    for username in usernames:
        user = username.strip().replace("@", "")
        print(f"\n🔍 調査中: @{user}")
        
        html = fetch_x_html(user)
        
        # デバッグ：HTMLが正しく取れているかチェック
        if len(html) < 1000 or "html" not in html.lower():
            print(f" ❌ 判定: 有効なHTMLを取得できませんでした（長さ: {len(html)}文字）")
            continue
            
        print(f" ✅ 判定: HTML取得成功（長さ: {len(html)}文字）")
        
        followers_num = 0
        following_num = 0
        posts_num = 0

        # JSONデータ（ld+json）から抽出を試みる
        json_blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL)
        for block in json_blocks:
            try:
                data = json.loads(block.strip())
                stats = []
                main_entity = data.get("mainEntity", {})
                for key in ["interactionStatistic", "agentInteractionStatistic"]:
                    if key in main_entity: stats.extend(main_entity[key])
                    if key in data: stats.extend(data[key])
                
                for stat in stats:
                    name = stat.get("name", "")
                    val = int(stat.get("userInteractionCount", 0))
                    if name == "Follows": followers_num = val
                    elif name == "Friends": following_num = val
                    elif name == "Tweets": posts_num = val
            except:
                continue

        # 保険：正規表現での直接スナイプ
        if followers_num == 0:
            m_f = re.search(r'"name"\s*:\s*"Follows"\s*,\s*"userInteractionCount"\s*:\s*(\d+)', html)
            if m_f: followers_num = int(m_f.group(1))
            
        if following_num == 0:
            m_g = re.search(r'"name"\s*:\s*"Friends"\s*,\s*"userInteractionCount"\s*:\s*(\d+)', html)
            if m_g: following_num = int(m_g.group(1))

        match_p = re.search(r'([\d.,万KMkm]+)[^<]*posts', html, re.IGNORECASE)
        if match_p and posts_num == 0:
            posts_num = parse_count(match_p.group(1))

        if followers_num > 0 or following_num > 0:
            ws.append_row([now_str, user, following_num, followers_num, posts_num])
            print(f" ✅ 記録成功: @{user} (F:{followers_num:,}, Fg:{following_num:,}, P:{posts_num:,})")
            success_count += 1
        else:
            print(f" ❌ 抽出失敗: @{user} - HTMLは取れましたが数値を特定できませんでした")
            
        import time
        time.sleep(random.uniform(3, 6))

    print(f"\n🏁 処理完了: {success_count} / {len(usernames)} 件の取得に成功しました。")
    if success_count == 0:
        sys.exit(1)

if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True)
    scrape_to_sheets()
