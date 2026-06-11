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
    HTMLのメタデータ(ld+json)から、Xの仕掛けた丸め（Kや万）や700のダミートラップを
    100%無効化し、1桁単位の完全な生数値を辞書型でぶっこ抜く関数
    """
    metrics = {"followers": 0, "following": 0, "posts": 0}
    
    try:
        # HTML内に埋め込まれているプロフィール用の構造化JSONデータをすべて抽出
        json_blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL)
        
        for block in json_blocks:
            try:
                data = json.loads(block.strip())
                
                # interactionStatistic というキーが入っているブロックがプロフィールの証拠
                stats = data.get("mainEntity", {}).get("interactionStatistic", [])
                if not stats and isinstance(data, dict):
                    # 階層が浅いパターンの保険
                    stats = data.get("interactionStatistic", [])
                
                if stats:
                    for stat in stats:
                        stat_name = stat.get("name", "")
                        count_val = int(stat.get("userInteractionCount", 0))
                        
                        if stat_name == "Follows":
                            metrics["followers"] = count_val
                        elif stat_name == "Friends":
                            metrics["following"] = count_val
                        elif stat_name == "Tweets":
                            metrics["posts"] = count_val
                    
                    # 1つでも正常にデータが抜けたら確定させて戻す
                    if metrics["followers"] > 0 or metrics["following"] > 0:
                        return metrics
            except:
                continue
                
        # 💡 万が一上記で見落とした場合の超・最終バックアップ（文字列からダイレクトに抜き取る）
        if metrics["followers"] == 0:
            f_match = re.search(r'"name"\s*:\s*"Follows"\s*,\s*"userInteractionCount"\s*:\s*(\d+)', html)
            g_match = re.search(r'"name"\s*:\s*"Friends"\s*,\s*"userInteractionCount"\s*:\s*(\d+)', html)
            p_match = re.search(r'"name"\s*:\s*"Tweets"\s*,\s*"userInteractionCount"\s*:\s*(\d+)', html)
            
            if f_match: metrics["followers"] = int(f_match.group(1))
            if g_match: metrics["following"] = int(g_match.group(1))
            if p_match: metrics["posts"] = int(p_match.group(1))

    except Exception as e:
        print(f"  ⚠️ メタデータ解析中に予期せぬエラー: {e}")
        
    return metrics

def scrape_to_sheets():
    print("🚀 X(Twitter)データ収集プログラム（裏データ直接強奪版）を開始しました")
    
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
        print(f"🎯 スプレッドシート接続成功: {sh.title} / シート名: {ws.title}")
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
    
    # 💡 日付フォーマットの完全統一 (YYYY-MM-DD)
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
                page.wait_for_timeout(6000) # 生成待機
                
                raw_html = page.content()
                
                # 改良した1桁生データデコーダーを実行
                data = extract_x_clean_metrics(raw_html)
                
                followers_num = data["followers"]
                following_num = data["following"]
                posts_num = data["posts"]

                if followers_num > 0 or following_num > 0:
                    ws.append_row([now_str, clean_username, following_num, followers_num, posts_num])
                    print(f" ✅ Success: {clean_username} (Followers: {followers_num:,}, Following: {following_num:,}, Posts: {posts_num:,})")
                    success_count += 1
                else:
                    print(f" ❌ Failed: {clean_username} (裏データ内に数値を特定できませんでした)")

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
