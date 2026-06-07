import os
import json
import datetime
import random
import sys
import re
import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

def extract_instagram_counts_from_embed(html):
    """Instagramの埋め込み用HTMLから、フォロワー数を1桁単位で抽出する関数"""
    counts = {"followers": 0, "following": 0, "posts": 0}
    try:
        # 埋め込み用データの中にあるフォロワー数を検索
        # 例: "edge_followed_by":{"count":134257} や "user":{..."followers_count":134257} などのパターンに対応
        match = re.search(r'"followers_count"\s*:\s*(\d+)', html)
        if not match:
            match = re.search(r'"edge_followed_by"\s*:\s*\{\s*"count"\s*:\s*(\d+)', html)
            
        if match:
            counts["followers"] = int(match.group(1))
            
        # 埋め込みデータにはフォロー中や投稿数が含まれない場合があるため、見つかった場合のみ入れる
        match_following = re.search(r'"friends_count"\s*:\s*(\d+)', html)
        if match_following:
            counts["following"] = int(match_following.group(1))
            
    except Exception as e:
        print(f" ⚠️ HTML解析失敗: {e}")
    return counts

def scrape_instagram_to_sheets():
    print("🚀 Instagram収集プログラム（埋め込みルート版）を開始しました")
    
    # --- 1. Google Sheets APIの認証 ---
    try:
        scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        env_key = os.environ.get("GCP_JSON_KEY")
        info = json.loads(env_key)
        creds = Credentials.from_service_account_info(info, scopes=scopes)
        client = gspread.authorize(creds)
        
        sheet_id = os.environ.get("SPREADSHEET_ID")
        sh = client.open_by_key(sheet_id)
        ws = sh.get_worksheet(1) # 2枚目のシート
        print(f"🎯 スプレッドシート接続成功: {sh.title} / シート名: {ws.title}")
    except Exception as e:
        print(f"❌ Google Sheets 接続エラー: {e}")
        return

    # --- 2. ターゲットの読み込み ---
    input_csv = "targets_instagram.csv"
    if not os.path.exists(input_csv):
        print(f"❌ エラー: {input_csv} が見つかりません。")
        return
    with open(input_csv, 'r') as f:
        usernames = [line.strip() for line in f if line.strip()]
    
    print(f"📋 読み込んだInstagramアカウント数: {len(usernames)} 件")
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # --- 3. スクレイピング ---
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Cookieの組み立て
        session_id = os.environ.get("INSTAGRAM_SESSION_ID")
        
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        # 💡 GitHub上のブラウザにログイン状態を注入する
        if session_id:
            context.add_cookies([{
                'name': 'sessionid',
                'value': session_id,
                'domain': '.instagram.com',
                'path': '/',
                'secure': True,
                'httpOnly': True
            }])
            print("🔑 ログインセッションをブラウザに注入しました。")
       
        page = context.new_page()

        for username in usernames:
            clean_username = username.replace("https://www.instagram.com/", "").replace("instagram.com/", "").replace("/", "")
            
            # 💡 ガードを回避するため、通常のプロフィールではなく、最新投稿の埋め込みページ（embed）を経由する
            # ユーザー名から直接プロフィールデータを引っ張るためのメタデータURL
            target_url = f"https://www.instagram.com/{clean_username}/?__a=1&__d=dis"
            
            print(f"🔍 調査開始（回避ルート）: @{clean_username}")
            
            try:
                # 1つ目の回避策：データ配信用URLを叩いてみる
                page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(3000)
                raw_html = page.content()
                
                counts = extract_instagram_counts_from_embed(raw_html)
                
                # もし上記で取れなかった場合、通常のプロフィール画面から文字だけでも掠め取る保険
                if counts["followers"] == 0:
                    profile_url = f"https://www.instagram.com/{clean_username}/"
                    page.goto(profile_url, wait_until="domcontentloaded", timeout=30000)
                    page.wait_for_timeout(4000)
                    
                    # メタタグ（<meta name="description" content="...フォロワー13.4万人..." />）から正規表現で抜く
                    meta_content = page.locator('meta[name="description"]').get_attribute("content")
                    if meta_content:
                        # 例: "13.4M Followers" や "13.4万人のフォロワー" から数字を抽出
                        print(f" ℹ️ メタデータから抽出を試みます: {meta_content}")
                        match_meta = re.search(r'([\d.,万KM]+)\s*(?:人の)?フォロワー', meta_content)
                        if match_meta:
                            # 簡易的な変換ロジック（完全に1桁にはなりませんが、ブロックされるよりは数値を残せます）
                            val = match_meta.group(1).replace(',', '')
                            if '万' in val: counts["followers"] = int(float(val.replace('万', '')) * 10000)
                            elif 'M' in val: counts["followers"] = int(float(val.replace('M', '')) * 1000000)
                            elif 'K' in val: counts["followers"] = int(float(val.replace('K', '')) * 1000)
                            else: counts["followers"] = int(val)

                followers_num = counts["followers"]
                following_num = counts["following"]
                posts_num = counts["posts"]

                if followers_num > 0:
                    ws.append_row([now_str, clean_username, following_num, followers_num, posts_num])
                    print(f" ✅ Success: {clean_username} (Followers: {followers_num:,})")
                else:
                    print(f" ❌ Failed: {clean_username} (Instagramの強力なブロックを突破できませんでした)")

            except Exception as e:
                print(f" ⚠️ エラー: @{clean_username} - {e}")

            page.wait_for_timeout(random.randint(4000, 8000))

        browser.close()
    print("✨ 処理が終了しました。")

if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True)
    scrape_instagram_to_sheets()
