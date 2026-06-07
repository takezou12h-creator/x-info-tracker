import os
import json
import datetime
import random
import sys
import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

def debug_x_response():
    print("🚀 【デバッグモード】Xのレスポンス構造を解読します...")
    
    # ターゲット読み込み
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
    print(f"📋 解析対象アカウント（最初の1件）: @{target_user}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        # レスポンスを監視して中身を解剖する関数
        def handle_response(res):
            if "UserByScreenName" in res.url and res.status == 200:
                print("\n=== 🎯 UserByScreenName の通信をキャッチしました ===")
                try:
                    data = res.json()
                    
                    # 1. 最上位のキーを確認
                    print(f"📦 ルート直下のキー: {list(data.keys())}")
                    
                    if 'data' in data:
                        print(f"📦 data 直下のキー: {list(data['data'].keys())}")
                        if 'user' in data['data']:
                            print(f"📦 user 直下のキー: {list(data['data']['user'].keys())}")
                            if 'result' in data['data']['user']:
                                result_node = data['data']['user']['result']
                                print(f"📦 result 直下のキー: {list(result_node.keys())}")
                                
                                # もし階層が深ければさらにその下も表示
                                if 'user' in result_node:
                                    print(f"📦 result['user'] 直下のキー: {list(result_node['user'].keys())}")
                    
                    # 2. JSONの全容を把握するため、文字列を一部整形して出力
                    raw_json_str = json.dumps(data, ensure_ascii=False)
                    print("\n--- 📝 生データの冒頭500文字 ---")
                    print(raw_json_str[:500])
                    print("--------------------------------")
                    
                    # 3. 特定のキーワードがどこに含まれているか全探索
                    print("\n🔎 キーワードの生存確認:")
                    print(f" ・'followers_count' の有無: {'followers_count' in raw_json_str}")
                    print(f" ・'legacy' の有無: {'legacy' in raw_json_str}")
                    print(f" ・'rest_id' の有無: {'rest_id' in raw_json_str}")
                    print("==================================================\n")
                    
                except Exception as e:
                    print(f"❌ JSONの解析中にエラー: {e}")

        page.on("response", handle_response)
        
        try:
            page.goto(f"https://x.com/{target_user}", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(7000) # 通信を確実に待つために少し長めに待機
        except Exception as e:
            print(f"⚠️ ページ遷移エラー: {e}")
            
        browser.close()
    print("🏁 デバッグ用の検証が終了しました。")

if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True)
    debug_x_response()
