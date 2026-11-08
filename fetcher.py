import os
import sys
import json
import time
import random
import requests
from playwright.sync_api import sync_playwright

RAW_DIR = "raw_data"

# 💡 検証済みのUser-Agent（絶対に短縮・変更しない）
FX_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)
FX_HEADERS = {"User-Agent": FX_USER_AGENT, "Accept": "application/json"}


def fetch_one_x(session: requests.Session, handle: str):
    """fxtwitter (フォールバックとしてvxtwitter) からXのユーザー情報を取得する"""
    for base, source in (
        ("https://api.fxtwitter.com", "fxtwitter"),
        ("https://api.vxtwitter.com", "vxtwitter"),
    ):
        attempts = 3 if source == "fxtwitter" else 1
        for attempt in range(attempts):
            try:
                resp = session.get(f"{base}/{handle}", headers=FX_HEADERS, timeout=20)
            except requests.RequestException as exc:
                print(f"  ⚠️ [{handle}] {source} 通信エラー: {exc}", file=sys.stderr)
                break

            if resp.status_code == 404:
                print(f"  ❌ [{handle}] {source} HTTP 404 (user_not_found)", file=sys.stderr)
                return None, source, "user_not_found"

            if resp.status_code == 429 or resp.status_code >= 500:
                print(f"  ⚠️ [{handle}] {source} HTTP {resp.status_code} (リトライ {attempt+1}/{attempts})", file=sys.stderr)
                if attempt < attempts - 1:
                    time.sleep(2 * (attempt + 1))
                    continue
                return None, source, "error"

            if resp.status_code != 200:
                print(f"  ⚠️ [{handle}] {source} HTTP {resp.status_code}", file=sys.stderr)
                break

            try:
                data = resp.json()
            except ValueError:
                print(f"  ⚠️ [{handle}] {source} 非JSONレスポンス (Cloudflareブロック等)", file=sys.stderr)
                break

            user = data.get("user") or {}
            if source == "fxtwitter" and "followers" in user:
                print(f"  ✅ [{handle}] {source} HTTP 200 OK")
                return user, source, "ok"
            elif source == "vxtwitter" and "followers_count" in user:
                print(f"  ✅ [{handle}] {source} HTTP 200 OK")
                return user, source, "ok"

            print(f"  ⚠️ [{handle}] {source} JSON内にカウントデータがありません", file=sys.stderr)
            break

    return None, "", "error"


def fetch_all_targets(targets):
    os.makedirs(RAW_DIR, exist_ok=True)
    saved_files = []

    # X と それ以外（Instagram / Threads）にターゲットを分離
    x_targets = [(p, u) for p, u in targets if p in ("x", "twitter", "𝕏")]
    browser_targets = [(p, u) for p, u in targets if p not in ("x", "twitter", "𝕏")]

    # ---------------------------------------------------------
    # 1. X (Twitter) の処理（requests のみ・ブラウザ不要）
    # ---------------------------------------------------------
    if x_targets:
        print(f"🚀 [X-API] fxtwitter経由で {len(x_targets)} 件を取得します（Playwright不使用）")
        with requests.Session() as session:
            for i, (platform, username) in enumerate(x_targets):
                clean_handle = username.strip().lstrip("@")
                print(f"🌐 [{i+1}/{len(x_targets)}] 取得中 [X]: @{clean_handle}")
                user, source, status = fetch_one_x(session, clean_handle)

                filepath = os.path.join(RAW_DIR, f"x_{clean_handle}.json")
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump({
                        "platform": "x",
                        "username": clean_handle,
                        "source": source,
                        "status": status,
                        "user": user or {}
                    }, f, ensure_ascii=False, indent=2)

                saved_files.append(filepath)
                if i < len(x_targets) - 1:
                    time.sleep(1.5)  # APIへの礼儀として1.5秒待機

    # ---------------------------------------------------------
    # 2. Instagram / Threads の処理（既存のPlaywright処理を維持）
    # ---------------------------------------------------------
    if browser_targets:
        url_templates = {
            "instagram": "https://www.instagram.com/{}/",
            "threads": "https://www.threads.net/@{}"
        }
        sleep_ranges = {
            "threads": (3.0, 6.0),
            "instagram": (15.0, 30.0)
        }
        ig_session_id = os.environ.get("INSTAGRAM_SESSION_ID", "")

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
                locale="ja-JP",
                viewport={"width": 1280, "height": 800}
            )
            context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                window.chrome = { runtime: {} };
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
                Object.defineProperty(navigator, 'languages', { get: () => ['ja-JP', 'ja', 'en-US', 'en'] });
            """)

            if ig_session_id:
                context.add_cookies([{
                    'name': 'sessionid', 'value': ig_session_id,
                    'domain': '.instagram.com', 'path': '/', 'secure': True, 'httpOnly': True
                }])
                print("🔑 Instagramログインセッション(Cookie)をセットしました。")

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

            for i, (platform, username) in enumerate(browser_targets):
                captured_json.clear()
                url = url_templates.get(platform, "https://www.instagram.com/{}/").format(username)
                print(f"🌐 [{i+1}/{len(browser_targets)}] 取得中 [{platform.upper()}]: @{username}")

                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=40000)
                    page.wait_for_timeout(random.randint(6000, 9000))
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

                if i < len(browser_targets) - 1:
                    min_s, max_s = sleep_ranges.get(platform, (5.0, 10.0))
                    sleep_time = random.uniform(min_s, max_s)
                    print(f"  ⏳ 待機中... ({sleep_time:.1f}秒)\n")
                    time.sleep(sleep_time)

            context.close()
            browser.close()

    return saved_files
