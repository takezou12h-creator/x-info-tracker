import sys
from fetcher import fetch_all_targets
from parser import parse_saved_file
from writer import write_to_spreadsheet

def load_targets(csv_path="targets.csv", target_platform=None):
    targets = []
    with open(csv_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip().replace("@", "") for p in line.split(",")]
            platform = parts[0].lower() if len(parts) >= 2 else "x"
            username = parts[1] if len(parts) >= 2 else parts[0]

            if target_platform and platform != target_platform.lower():
                continue
            targets.append((platform, username))
    return targets

def main():
    # 引数の受け取り (例: python main.py x AIkikue)
    target_platform = sys.argv[1] if len(sys.argv) > 1 else None
    target_username = sys.argv[2] if len(sys.argv) > 2 else None

    # 💡 ユーザー名が指定されている場合は「デバッグモード（1件のみ実行）」
    if target_platform and target_username:
        print(f"🛠 [DEBUG MODE] 単一アカウントのテスト実行: {target_platform.upper()} / @{target_username}")
        targets = [(target_platform.lower(), target_username)]
        label = "DEBUG"
    else:
        label = target_platform.upper() if target_platform else "ALL"
        print(f"🚀 [{label}] SNSフォロワー集計を開始します")
        targets = load_targets(target_platform=target_platform)

    print(f"📋 対象アカウント数: {len(targets)}件\n")
    if not targets:
        print("⚠️ 対象のアカウントがありません。")
        return

    # Step 1: 取得
    saved_files = fetch_all_targets(targets)

    # Step 2: 解析
    print("\n🔍 保存データの解析を開始します...")
    valid_results = []
    for filepath in saved_files:
        res = parse_saved_file(filepath)
        if res["followers"] > 0 or res["following"] > 0:
            print(f"  ✅ [{res['platform'].upper()}] @{res['username']} -> フォロー:{res['following']:,} / フォロワー:{res['followers']:,} / 投稿:{res['posts']:,}")
            valid_results.append(res)
        else:
            print(f"  ❌ [{res['platform'].upper()}] @{res['username']} -> 数値の取得に失敗しました")

    # Step 3: 記録
    print("\n📊 スプレッドシートへの書き込みを開始します...")
    if valid_results:
        write_to_spreadsheet(valid_results)
    else:
        print(f"❌ [{label}] 有効なデータが0件のため、書き込みをスキップしました。")
        sys.exit(1)

if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True)
    main()
