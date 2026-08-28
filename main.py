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
    url = f"https://x.com/{username}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "ja,en-US;q=0.9,en;q=0.7",
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

def extract_metrics_from_huge_html(html, username):
    """ 25万文字のHTMLのあらゆる場所からフォロワー・フォロー・ポスト数を執念で探し出す関数 """
    metrics = {"followers": 0, "following": 0, "posts": 0}
    
    try:
        # 1. 構造化データ（ld+json）の全探索（キー名や階層を問わず、数字を総当たりで拾う）
        json_blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL)
        for block in json_blocks:
            try:
                data = json.loads(block.strip())
                # ブロック内のすべてのテキストや数値を再帰的、あるいは雑に総ざらいする
                block_str = json.dumps(data)
                
                # "Follows" や "Friends" の直後にある数値を探す
                f_m = re.search(r'"name"\s*:\s*"Follows"\s*,\s*"userInteractionCount"\s*:\s*(\d+)', block_str)
                if f_m: metrics["followers"] = int(f_m.group(1))
                
                g_m = re.search(r'"name"\s*:\s*"Friends"\s*,\s*"userInteractionCount"\s*:\s*(\d+)', block_str)
                if g_m: metrics["following"] = int(g_m.group(1))
                
                p_m = re.search(r'"name"\s*:\s*"Tweets"\s*,\s*"userInteractionCount"\s*:\s*(\d+)', block_str)
                if p_m: metrics["posts"] = int(p_m.group(1))
            except:
                continue

        # 2. HTMLの画面表示用タグ（リンクやfont-bold）からの直接スナイプ
        # フォロワー数（verified_followers または followers のリンク周辺を狙う）
        if metrics["followers"] == 0:
            patterns_f = [
                r'href="/{}/(verified_)?followers"[^>]*>.*?font-bold">([^<]+)<'.format(re.escape(username)),
                r'href="/{}/(verified_)?followers"[^>]*>.*?text-subtext1[^>]*>([^<]+)<'.format(re.escape(username)),
                r'followers"[^>]*>.*?([0-9.,]+[KM]?)'
            ]
            for p in patterns_f:
                m = re.search(p, html, re.IGNORECASE | re.DOTALL)
                if m:
                    val = parse_count(m.group(2) if len(m.groups()) >= 2 else m.group(1))
                    if val > 0:
                        metrics["followers"] = val
                        break

        # フォロー中（following のリンク周辺を狙う）
        if metrics["following"] == 0:
            patterns_g = [
                r'href="/{}/following"[^>]*>.*?font-bold">([^<]+)<'.format(re.escape(username)),
                r'href="/{}/following"[^>]*>.*?text-subtext1[^>]*>([^<]+)<'.format(re.escape(username))
            ]
            for p in patterns_g:
                m = re.search(p, html, re.IGNORECASE | re.DOTALL)
                if m:
                    val = parse_count(m.group(1))
                    if val > 0:
                        metrics["following"] = val
                        break

        # ポスト数の取得
        if metrics["posts"] == 0:
            match_p = re.search(r'([\d.,万KMkm]+)[^<]*posts', html, re.IGNORECASE)
            if match_p:
                metrics["posts"] = parse_count(match_p.group(1))

        # 3. 最終奥義：もしそれでも見つからない場合、HTML全体から「数字 + K/万」や「コンマ付き数字」で
        # フォロワーらしい妥当な数値の塊を片っ端から候補にする（保険）
        
    except Exception as e:
        print(f"  ⚠️ 解析中エラー: {e}")
        
    return metrics

def scrape_to_sheets():
    print("🚀 X(Twitter) 25万文字完全攻略版を開始しました")
    
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
        if len(html) < 1000:
            print(f" ❌ 取得失敗")
            continue
            
        data = extract_metrics_from_huge_html(html, user)
        
        followers_num = data["followers"]
        following_num = data["following"]
        posts_num = data["posts"]

        if followers_num > 0 or following_num > 0:
            ws.append_row([now_str, user, following_num, followers_num, posts_num])
            print(f" ✅ 成功: @{user} (F:{followers_num:,}, Fg:{following_num:,}, P:{posts_num:,})")
            success_count += 1
        else:
            print(f" ❌ 抽出失敗: @{user} - 25万文字から数値をヒットさせられませんでした")
            
        import time
        time.sleep(random.uniform(3, 6))

    print(f"\n🏁 処理完了: {success_count} / {len(usernames)} 件の取得に成功しました。")
    if success_count == 0:
        sys.exit(1)

if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True)
    scrape_to_sheets()
