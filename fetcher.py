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

    # 一般的なデスクトップブラウザのふりをするための設定
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1.1 Safari/605.1.15",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0"
    ]

    with sync_playwright() as p:
        # headless=True だとボット判定されやすいSNS対策として引数を追加
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
            ]
        )
        
        for i, (platform, username) in enumerate(targets):
            url = url_templates.get(platform, "https://x.com/{}").format(username)
            print(f"🌐 [{i+1}/{len(targets)}] 取得中 [{platform.upper()}]: @{username}")
            
            context = browser.new_context(
                user_agent=random.choice(user_agents),
                locale="ja-JP",
                timezone_id="Asia/Tokyo",
                viewport={"width": 1920, "height": 1080},
                device_scale_factor=1,
            )
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
                # Instagramなどは少し長めにタイムアウトをとる
                page.goto(url, wait_until="domcontentloaded", timeout=40000)
                
                # 人間らしくランダムに少しスクロールや待機を入れる
                page.wait_for_timeout(random.uniform(3000, 6000))
                
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
                print(f"  💾 保存完了 (JSON通信 {len(captured_json)}件)")
            except Exception as e:
                print(f"  ❌ 取得エラー (@{username}): {e}")
            finally:
                context.close()

            # ⭐ ご要望の「任意のランダムな時間間隔」：アカウントごとに5秒〜12秒ランダムで待機
            sleep_time = random.uniform(5.0, 12.0)
            print(f"  ⏳ 待機中... ({sleep_time:.1f}秒)\n")
            time.sleep(sleep_time)

        browser.close()
    return saved_files
