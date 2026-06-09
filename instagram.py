# (上部省略、scrape_instagram_to_sheets 内のPlaywright起動部分のみ変更)

    # --- 3. Playwright処理 ---
    with sync_playwright() as p:
        # 💡 ステルス性を上げるため、Chromiumの起動引数を追加
        browser = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        
        session_id = os.environ.get("INSTAGRAM_SESSION_ID")
        
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="ja-JP", # 💡 日本からのアクセスに偽装
            viewport={"width": 1280, "height": 800}
        )
        
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
        else:
            print("⚠️ 警告: INSTAGRAM_SESSION_ID が設定されていません。")

        page = context.new_page()

        for username in usernames:
            clean_username = username.replace("https://www.instagram.com/", "").replace("instagram.com/", "").replace("/", "")
            target_url = f"https://www.instagram.com/{clean_username}/"
            
            print(f"🔍 調査開始: @{clean_username}")
            
            try:
                page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(random.randint(6000, 9000)) # 💡 読み込み完了後、少し長めに待つ
                
                raw_followers = "0"
                raw_following = "0"
                raw_posts = "0"
                
                # (以降、要素抽出と書き込みロジックはそのまま維持)
                # ...
                
            except Exception as e:
                print(f" ⚠️ 通信エラー: @{clean_username} - {e}")

            # 💡 次のアカウントへ行く前のインターバルを「15秒〜30秒の間でランダム」に延長
            # これによりスクレイピング検知の網をすり抜けます
            interval = random.randint(15000, 30000)
            page.wait_for_timeout(interval)

        browser.close()
