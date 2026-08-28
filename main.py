import os
import json
import datetime
import random
import sys
import re
import gspread
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
    print("🚀 X(Twitter) 要素完全待機・直撃版を開始しました")
    
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
                page.goto(f"https://x.com/{user}", wait_until="commit", timeout=40000)
                
                # 💡 決定的な修正：プロフィール欄の描画が完了する（要素が出現する）まで最大15秒間しっかり待機する
                try:
                    page.wait_for_selector('a[href*="/following"]', timeout=15000)
                except:
                    print(" ⚠️ 要素の出現待機がタイムアウトしましたが、続行します...")
                
                # 追加の安定化ウェイト
                page.wait_for_timeout(3000)
                
                html = page.content()
                
                # 1. 画像のツリー構造からピンポイントで「following」の数値を抜く
                fg_match = re.search(r'href="/{}/following"[^>]*>.*?font-bold">([^<]+)<'.format(re.escape(user)), html, re.DOTALL)
                if fg_match:
                    following_num = parse_count(fg_match.group(1))

                # 2. 画像のツリー構造からピンポイントで「followers」の数値を抜く
                fo_match = re.search(r'href="/{}/(verified_)?followers"[^>]*>.*?font-bold">([^<]+)<'.format(re.escape(user)), html, re.DOTALL)
                if fo_match:
                    followers_num = parse_count(fo_match.group(2))

                # 3. ポスト数の取得
                match_p = re.search(r'([\d.,万KMkm]+)[^<]*posts', html, re.IGNORECASE)
                if match_p:
                    posts_num = parse_count(match_p.group(1))

                # 万が一のバックアップ（JSONデータからの抽出）
                if followers_num == 0 or following_num == 0:
                    json_blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL)
                    for block in json_blocks:
                        try:
                            data = json.loads(block.strip())
                            stats = []
                            for key in ["interactionStatistic", "agentInteractionStatistic"]:
                                if key in data.get("mainEntity", {}):
                                    stats.extend(data["mainEntity"][key])
                                if key in data:
                                    stats.extend(data[key])
                            for stat in stats:
                                name = stat.get("name", "")
                                val = int(stat.get("userInteractionCount", 0))
                                if name == "Follows" and followers_num == 0: followers_num = val
                                elif name == "Friends" and following_num == 0: following_num = val
                                elif name == "Tweets" and posts_num == 0: posts_num = val
                        except:
                            continue

                # 書き込み判定
                if followers_num > 0 or following_num > 0:
                    ws.append_row([now_str, user, following_num, followers_num, posts_num])
                    print(f" ✅ Success: @{user} (F:{followers_num:,}, Fg:{following_num:,}, P:{posts_num:,})")
                    success_count += 1
                else:
                    print(f" ❌ Failed: @{user} - HTMLは取得できましたが数値を特定できませんでした")

            except Exception as e:
                print(f" ⚠️ エラー: @{user} - {e}")
            
            page.wait_for_timeout(4000)
            
        browser.close()
        
    print(f"\n🏁 処理完了: {success_count} / {len(usernames)} 件の取得に成功しました。")
    if success_count == 0:
        sys.exit(1)

if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True)
    scrape_to_sheets()
