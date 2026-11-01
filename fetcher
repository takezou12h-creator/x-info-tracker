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

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        
        for platform, username in targets:
            url = url_templates.get(platform, "https://x.com/{}").format(username)
            print(f"🌐 取得中 [{platform.upper()}]: @{username}")
            
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
                locale="ja-JP",
                viewport={"width": 1280, "height": 800}
            )
            page = context.new_page()
            captured_json = []

            # 裏側のAPI通信（GraphQLやJSON）を傍受してリストに溜める
            def handle_response(response):
                try:
                    ctype = response.headers.get("content-type", "")
                    if "json" in ctype or "graphql" in response.url or "api/v1" in response.url:
                        captured_json.append(response.json())
                except:
                    pass

            page.on("response", handle_response)

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                # 通信が完了して数値が読み込まれるまで少し待つ
                page.wait_for_timeout(5000)
                html = page.content()

                # 取得した生データをファイルとして保存（取得と解析の分離）
                filepath = os.path.join(RAW_DIR, f"{platform}_{username}.json")
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump({
                        "platform": platform,
                        "username": username,
                        "html": html,
                        "json_list": captured_json
                    }, f, ensure_ascii=False)
                
                saved_files.append(filepath)
                print(f"  💾 生データ保存完了: {filepath} (JSON通信 {len(captured_json)}件傍受)")
            except Exception as e:
                print(f"  ❌ 取得エラー (@{username}): {e}")
            finally:
                context.close()

            time.sleep(random.uniform(3, 6))

        browser.close()
    return saved_files
