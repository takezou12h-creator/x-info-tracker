import os
import sys
from playwright.sync_api import sync_playwright

def capture_x_html():
    print("🚀 【HTML解析モード】現在のXの構造をファイルに書き出します...")
    
    input_csv = "targets.csv"
    if not os.path.exists(input_csv):
        print("❌ targets.csv が見つかりません。")
        return
    
    with open(input_csv, 'r') as f:
        usernames = [line.strip() for line in f if line.strip()]
        
    if not usernames:
        print("❌ アカウントリストが空です。")
        return
        
    target_user = usernames[0]
    print(f"📋 ターゲットアカウント: @{target_user}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()
        
        try:
            # ページへ移動
            page.goto(f"https://x.com/{target_user}", wait_until="domcontentloaded", timeout=30000)
            print("⏳ 画面のレンダリング完了まで10秒間待機します...")
            page.wait_for_timeout(10000) # 確実に数値を読み込ませるために長めに待機
            
            # 現在の画面のHTMLを丸ごと取得
            html_content = page.content()
            
            # ファイルに書き出し
            output_file = "x_page.html"
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(html_content)
                
            print(f"💾 正常に生HTMLを保存しました: {output_file} (サイズ: {len(html_content)} バイト)")
            
        except Exception as e:
            print(f"❌ エラーが発生しました: {e}")
            
        browser.close()
    print("🏁 HTMLのキャッチ処理が終了しました。")

if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True)
    capture_x_html()
