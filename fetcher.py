import os
import json
import time
import random
from playwright.sync_api import sync_playwright

RAW_DIR = "raw_data"

def fetch_all_targets(targets):
    os.makedirs(RAW_DIR, exist_ok=True)
    saved_files = []

    url_templates = {
        "x": "https://x.com/{}",
        "instagram": "https://www.instagram.com/{}/",
        "threads": "https://www.threads.net/@{}"
    }

    ig_session_id = os.environ.get("INSTAGRAM_SESSION_ID", "")
    x_auth_token = os.environ.get("X_AUTH_TOKEN", "")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
        )
        
        for i, (platform, username) in enumerate(targets):
            url = url_templates.get(platform, "https://x.com/{}").format(username)
            print(f"🌐 [{i+1}/{len(targets)}] 取得中 [{platform.upper()}]: @{username}")
            
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                locale="ja-JP",
                viewport={"width": 1280, "height": 800}
            )

            # --- ログイン用セッション（Cookie）の注入 ---
            if platform == "instagram" and ig_session_id:
                context.add_cookies([{
                    'name': 'sessionid', 'value': ig_session_id,
                    'domain': '.instagram.com', 'path': '/', 'secure': True, 'httpOnly': True
                }])
            elif platform == "x" and x_auth_token:
                context.add_cookies([{
                    'name': 'auth_token', 'value': x_auth_token,
                    'domain': '.x.com', 'path': '/', 'secure': True, 'httpOnly': True
                }])

            page = context.new_page()
            captured_json = []

            def handle_response(response):
                try:
                    ctype = response.headers.get("content-type", "")
                    if "json" in ctype or "graphql" in response.url or "api/v1" in response.url:
                        captured_json.append(response.json())
                except:
                    pass

            page.on("response", handle_response)

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=40000)
                # ページが完全に描画されるまで少し長めに待機
                page.wait_for_timeout(random.randint(6000, 9000))
                html = page.content()

                filepath = os.path.join(RAW_DIR, f"{platform}_{username}.json")
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump({
                        "platform": platform,
                        "username": username,
                        "html": html,
                        "json_list": captured_json
                    }, f, ensure_ascii=False)
                
                saved_files.append(filepath)
                print(f"  💾 生データ保存完了 (通信傍受: {len(captured_json)}件)")
            except Exception as e:
                print(f"  ❌ 取得エラー (@{username}): {e}")
            finally:
                context.close()

            # 💡 ボット検知回避のためのランダムウェイト（15秒〜30秒）
            sleep_time = random.uniform(15.0, 30.0)
            print(f"  ⏳ 待機中... ({sleep_time:.1f}秒)\n")
            time.sleep(sleep_time)

        browser.close()
    return saved_files
