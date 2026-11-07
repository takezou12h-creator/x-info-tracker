import os
import json
import time
import random
from playwright.sync_api import sync_playwright
from playwright_stealth import stealth_sync

RAW_DIR = "raw_data"

def fetch_all_targets(targets):
    os.makedirs(RAW_DIR, exist_ok=True)
    saved_files = []

    url_templates = {
        "x": "https://x.com/{}",
        "instagram": "https://www.instagram.com/{}/",
        "threads": "https://www.threads.net/@{}"
    }

    # SNSごとのランダム待機時間（秒）の設定：ThreadsやXは短めにして高速化
    sleep_ranges = {
        "threads": (3.0, 6.0),
        "x": (5.0, 10.0),
        "instagram": (20.0, 30.0)
    }

    ig_session_id = os.environ.get("INSTAGRAM_SESSION_ID", "")
    x_auth_token = os.environ.get("X_AUTH_TOKEN", "")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
        )
        
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            locale="ja-JP",
            viewport={"width": 1280, "height": 800}
        )

        # 最初にまとめてログインCookieを注入しておく
        cookies = []
        if ig_session_id:
            cookies.append({'name': 'sessionid', 'value': ig_session_id, 'domain': '.instagram.com', 'path': '/', 'secure': True, 'httpOnly': True})
        if x_auth_token:
            cookies.append({'name': 'auth_token', 'value': x_auth_token, 'domain': '.x.com', 'path': '/', 'secure': True, 'httpOnly': True})
        if cookies:
            context.add_cookies(cookies)
            print("🔑 ログインセッションをブラウザにセットしました。")

        page = context.new_page()
        stealth_sync(page)
        page.goto(url, wait_until="domcontentloaded", timeout=40000)
        captured_json = []

        def handle_response(response):
            try:
                ctype = response.headers.get("content-type", "")
                if "json" in ctype or "graphql" in response.url or "api/v1" in response.url:
                    captured_json.append(response.json())
            except:
                pass

        page.on("response", handle_response)

        for i, (platform, username) in enumerate(targets):
            captured_json.clear() # 前回の通信データをクリア
            url = url_templates.get(platform, "https://x.com/{}").format(username)
            print(f"🌐 [{i+1}/{len(targets)}] 取得中 [{platform.upper()}]: @{username}")

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=40000)
                page.wait_for_timeout(random.randint(4000, 7000))
                html = page.content()

                filepath = os.path.join(RAW_DIR, f"{platform}_{username}.json")
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump({
                        "platform": platform,
                        "username": username,
                        "html": html,
                        "json_list": list(captured_json)
                    }, f, ensure_ascii=False)
                
                saved_files.append(filepath)
                print(f"  💾 保存完了 (通信傍受: {len(captured_json)}件)")
            except Exception as e:
                print(f"  ❌ 取得エラー (@{username}): {e}")

            # 最後の1件以外はランダム待機を入れる
            if i < len(targets) - 1:
                min_s, max_s = sleep_ranges.get(platform, (5.0, 10.0))
                sleep_time = random.uniform(min_s, max_s)
                print(f"  ⏳ 待機中... ({sleep_time:.1f}秒)\n")
                time.sleep(sleep_time)

        context.close()
        browser.close()
    return saved_files
